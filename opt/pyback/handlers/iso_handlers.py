"""
ISO Management API handlers.

This module provides HTTP request handlers for ISO file management including
listing, uploading, downloading, and deleting ISO files.
"""

import os
import logging
import asyncio
import aiohttp
from pathlib import Path
from aiohttp import web
from urllib.parse import urlparse

from ..config_loader import get_iso_storage_path
from ..handlers.download_handlers import download_progress
from ..utils.libvirt_connection import get_connection
import libvirt

logger = logging.getLogger(__name__)


async def _cleanup_progress_entry(key: str, delay: int = 10):
    """
    Remove progress entry after delay.
    
    Args:
        key: Progress entry key to remove
        delay: Delay in seconds before cleanup (default: 10)
    """
    try:
        await asyncio.sleep(delay)
        if key in download_progress:
            del download_progress[key]
            logger.info(f"Cleaned up progress entry: {key}")
    except Exception as e:
        logger.error(f"Error cleaning up progress entry {key}: {e}")


def validate_download_url(url: str) -> bool:
    """
    Validate URL to prevent SSRF attacks.
    
    Args:
        url: URL to validate
        
    Returns:
        bool: True if URL is safe, False otherwise
    """
    try:
        parsed = urlparse(url)
        
        # Only allow HTTP and HTTPS protocols
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Block common private IP ranges and localhost
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Block localhost variations
        if hostname.lower() in ('localhost', '127.0.0.1', '::1', '0.0.0.0'):
            return False
        
        # Block private IP ranges (simple check)
        if hostname.startswith('10.') or hostname.startswith('192.168.') or hostname.startswith('172.'):
            # More precise check for 172.16.0.0/12
            if hostname.startswith('172.'):
                parts = hostname.split('.')
                if len(parts) >= 2:
                    try:
                        second_octet = int(parts[1])
                        if 16 <= second_octet <= 31:
                            return False
                    except ValueError:
                        pass
                else:
                    return False
            else:
                return False
        
        # Block link-local addresses
        if hostname.startswith('169.254.'):
            return False
        
        return True
    except Exception:
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        str: Sanitized filename
    """
    # Remove any path components
    filename = os.path.basename(filename)
    # Keep only safe characters: alphanumeric, hyphens, underscores, and dots
    filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    # Remove leading dots to prevent hidden files
    filename = filename.lstrip('.')
    # Ensure filename is not empty after sanitization
    if not filename or filename in ('.', '..'):
        raise ValueError("Invalid filename after sanitization")
    return filename


def is_iso_in_use(iso_path: str) -> bool:
    """
    Check if an ISO file is currently in use by any VM.
    
    Args:
        iso_path: Full path to the ISO file
        
    Returns:
        bool: True if ISO is in use, False otherwise
    """
    conn = get_connection('qemu')
    if not conn:
        return False
    
    try:
        domains = conn.listAllDomains(
            libvirt.VIR_CONNECT_LIST_DOMAINS_ACTIVE | 
            libvirt.VIR_CONNECT_LIST_DOMAINS_INACTIVE
        )
        
        for domain in domains:
            xml_desc = domain.XMLDesc(0)
            # Simple check if the ISO path appears in the VM's XML
            if iso_path in xml_desc:
                conn.close()
                return True
        
        conn.close()
        return False
    except Exception as e:
        logger.error(f"Error checking if ISO is in use: {e}")
        if conn:
            conn.close()
        return False


async def list_isos(request):
    """
    List all ISO files in the ISO storage directory.
    
    Returns JSON with list of ISOs including filename, size, and date.
    """
    iso_storage_path = get_iso_storage_path()
    
    # Ensure directory exists
    Path(iso_storage_path).mkdir(parents=True, exist_ok=True)
    
    isos = []
    
    try:
        for entry in os.scandir(iso_storage_path):
            if entry.is_file() and entry.name.lower().endswith('.iso'):
                stat = entry.stat()
                isos.append({
                    'filename': entry.name,
                    'size': stat.st_size,
                    'size_mb': round(stat.st_size / (1024 * 1024), 2),
                    'modified': stat.st_mtime,
                    'path': entry.path
                })
        
        # Sort by modification time (newest first)
        isos.sort(key=lambda x: x['modified'], reverse=True)
        
        return web.json_response({
            'status': 'success',
            'isos': isos
        })
    except Exception as e:
        logger.error(f"Error listing ISOs: {e}")
        return web.json_response({
            'status': 'error',
            'message': f'Failed to list ISOs: {str(e)}'
        }, status=500)


async def upload_iso(request):
    """
    Upload an ISO file with chunked upload support.
    
    Handles multipart/form-data uploads and supports large files.
    Progress updates are visible in real-time even though upload is synchronous.
    """
    logger.info("ISO upload request received")
    iso_storage_path = get_iso_storage_path()
    
    # Ensure directory exists
    Path(iso_storage_path).mkdir(parents=True, exist_ok=True)
    
    upload_key = None
    file_path = None
    
    try:
        logger.info("Reading multipart data...")
        reader = await request.multipart()
        
        field = await reader.next()
        if field is None:
            logger.error("No file field in multipart data")
            return web.json_response({
                'status': 'error',
                'message': 'No file provided'
            }, status=400)
        
        # Get filename from field
        filename = field.filename
        logger.info(f"Upload field filename: {filename}")
        if not filename:
            logger.error("No filename in field")
            return web.json_response({
                'status': 'error',
                'message': 'No filename provided'
            }, status=400)
        
        # Sanitize and validate filename
        try:
            filename = sanitize_filename(filename)
            logger.info(f"Sanitized filename: {filename}")
        except ValueError as e:
            logger.error(f"Filename sanitization failed: {e}")
            return web.json_response({
                'status': 'error',
                'message': f'Invalid filename: {str(e)}'
            }, status=400)
        
        if not filename.lower().endswith('.iso'):
            logger.error(f"File doesn't have .iso extension: {filename}")
            return web.json_response({
                'status': 'error',
                'message': 'File must have .iso extension'
            }, status=400)
        
        # Build full path
        file_path = os.path.join(iso_storage_path, filename)
        logger.info(f"Target path: {file_path}")
        
        # Check if file already exists
        if os.path.exists(file_path):
            logger.warning(f"File already exists: {filename}")
            return web.json_response({
                'status': 'error',
                'message': f'File {filename} already exists'
            }, status=409)
        
        # Get file size from Content-Length header if available
        content_length = request.headers.get('Content-Length')
        try:
            total_size = int(content_length) if content_length else 0
        except (ValueError, TypeError):
            total_size = 0  # Invalid Content-Length, proceed without size info
        
        # Initialize progress tracking
        upload_key = f"iso_upload_{filename}"
        download_progress[upload_key] = {
            'status': 'uploading',
            'progress': 0,
            'total': total_size,
            'message': f'Uploading {filename}',
            'vm_name': filename
        }
        logger.info(f"Progress tracking initialized with key: {upload_key}, total_size: {total_size}")
        
        # Process upload synchronously with progress updates
        # The frontend will see progress updates via polling while this runs
        bytes_written = 0
        logger.info(f"Starting file write to {file_path}")
        with open(file_path, 'wb') as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)
                
                # Update progress - frontend can see these updates via polling
                download_progress[upload_key]['progress'] = bytes_written
                if total_size > 0:
                    progress = int((bytes_written / total_size) * 100)
                    download_progress[upload_key]['message'] = f'Uploading {filename}'
                else:
                    mb_written = bytes_written / (1024 * 1024)
                    download_progress[upload_key]['message'] = f'Uploading {filename} ({mb_written:.1f} MB)'
        
        # Set file permissions
        os.chmod(file_path, 0o644)
        
        # Mark upload as complete
        download_progress[upload_key]['status'] = 'completed'
        download_progress[upload_key]['progress'] = bytes_written
        download_progress[upload_key]['message'] = f'Upload complete: {filename}'
        
        # Schedule cleanup of progress entry
        asyncio.create_task(_cleanup_progress_entry(upload_key))
        
        logger.info(f"ISO uploaded successfully: {filename} ({bytes_written} bytes)")
        
        return web.json_response({
            'status': 'success',
            'message': f'ISO {filename} uploaded successfully',
            'filename': filename,
            'size': bytes_written
        })
        
    except Exception as e:
        logger.error(f"Error uploading ISO: {e}")
        
        # Clean up partial upload
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as cleanup_error:
                logger.error(f"Failed to clean up partial upload {file_path}: {cleanup_error}")
        
        # Mark upload as error
        if upload_key and upload_key in download_progress:
            download_progress[upload_key]['status'] = 'error'
            download_progress[upload_key]['message'] = f'Upload failed: {str(e)}'
            
            # Schedule cleanup of error entry
            asyncio.create_task(_cleanup_progress_entry(upload_key))
        
        return web.json_response({
            'status': 'error',
            'message': f'Failed to upload ISO: {str(e)}'
        }, status=500)


async def download_iso(request):
    """
    Download an ISO file from a URL.
    
    Accepts URL and filename, downloads to ISO storage path.
    """
    try:
        data = await request.json()
    except Exception:
        return web.json_response({
            'status': 'error',
            'message': 'Invalid JSON body'
        }, status=400)
    
    url = data.get('url')
    filename = data.get('filename')
    
    if not url or not filename:
        return web.json_response({
            'status': 'error',
            'message': 'URL and filename are required'
        }, status=400)
    
    # Validate URL to prevent SSRF attacks
    if not validate_download_url(url):
        return web.json_response({
            'status': 'error',
            'message': 'Invalid URL. Only HTTP/HTTPS URLs to public addresses are allowed.'
        }, status=400)
    
    # Sanitize filename
    try:
        filename = sanitize_filename(filename)
    except ValueError as e:
        return web.json_response({
            'status': 'error',
            'message': f'Invalid filename: {str(e)}'
        }, status=400)
    
    if not filename.lower().endswith('.iso'):
        filename += '.iso'
    
    iso_storage_path = get_iso_storage_path()
    
    # Ensure directory exists
    Path(iso_storage_path).mkdir(parents=True, exist_ok=True)
    
    file_path = os.path.join(iso_storage_path, filename)
    
    # Check if file already exists
    if os.path.exists(file_path):
        return web.json_response({
            'status': 'error',
            'message': f'File {filename} already exists'
        }, status=409)
    
    # Initialize progress tracking
    download_key = f"iso_download_{filename}"
    download_progress[download_key] = {
        'status': 'downloading',
        'progress': 0,
        'total': 0,
        'message': f'Downloading {filename}',
        'vm_name': filename
    }
    
    # Start download in background
    asyncio.create_task(_download_iso_background(url, file_path, filename, download_key))
    
    return web.json_response({
        'status': 'success',
        'message': f'Download started for {filename}',
        'download_key': download_key
    })


async def _download_iso_background(url: str, file_path: str, filename: str, download_key: str):
    """
    Background task for downloading ISO from URL.
    
    Args:
        url: URL to download from
        file_path: Local file path to save to
        filename: Name of the file
        download_key: Key for progress tracking
    """
    try:
        timeout = aiohttp.ClientTimeout(total=3600)  # 1 hour timeout
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}: {response.reason}")
                
                total_size = int(response.headers.get('Content-Length', 0))
                download_progress[download_key]['total'] = total_size
                
                bytes_downloaded = 0
                
                with open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Update progress
                        download_progress[download_key]['progress'] = bytes_downloaded
                        if total_size > 0:
                            progress = int((bytes_downloaded / total_size) * 100)
                            download_progress[download_key]['message'] = f'Downloading {filename}'
                        else:
                            mb_downloaded = bytes_downloaded / (1024 * 1024)
                            download_progress[download_key]['message'] = f'Downloading {filename} ({mb_downloaded:.1f} MB)'
        
        # Set file permissions
        os.chmod(file_path, 0o644)
        
        # Mark download as complete
        download_progress[download_key]['status'] = 'completed'
        download_progress[download_key]['progress'] = bytes_downloaded
        download_progress[download_key]['message'] = f'Download complete: {filename}'
        
        # Schedule cleanup of progress entry
        asyncio.create_task(_cleanup_progress_entry(download_key))
        
        logger.info(f"ISO downloaded successfully: {filename} ({bytes_downloaded} bytes)")
        
    except Exception as e:
        logger.error(f"Error downloading ISO: {e}")
        
        # Clean up partial download
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as cleanup_error:
                logger.error(f"Failed to clean up partial download {file_path}: {cleanup_error}")
        
        # Mark download as error
        download_progress[download_key]['status'] = 'error'
        download_progress[download_key]['message'] = f'Download failed: {str(e)}'
        
        # Schedule cleanup of error entry
        asyncio.create_task(_cleanup_progress_entry(download_key))


async def delete_iso(request):
    """
    Delete an ISO file.
    
    Validates that the ISO is not in use by any VM before deletion.
    """
    filename = request.match_info.get('filename')
    
    if not filename:
        return web.json_response({
            'status': 'error',
            'message': 'Filename is required'
        }, status=400)
    
    # Sanitize filename
    try:
        filename = sanitize_filename(filename)
    except ValueError as e:
        return web.json_response({
            'status': 'error',
            'message': f'Invalid filename: {str(e)}'
        }, status=400)
    
    iso_storage_path = get_iso_storage_path()
    file_path = os.path.join(iso_storage_path, filename)
    
    # Check if file exists
    if not os.path.exists(file_path):
        return web.json_response({
            'status': 'error',
            'message': f'ISO file {filename} not found'
        }, status=404)
    
    # Check if ISO is in use
    if is_iso_in_use(file_path):
        return web.json_response({
            'status': 'error',
            'message': f'ISO {filename} is currently in use by a VM and cannot be deleted'
        }, status=409)
    
    try:
        os.remove(file_path)
        logger.info(f"ISO deleted successfully: {filename}")
        
        return web.json_response({
            'status': 'success',
            'message': f'ISO {filename} deleted successfully'
        })
    except Exception as e:
        logger.error(f"Error deleting ISO: {e}")
        return web.json_response({
            'status': 'error',
            'message': f'Failed to delete ISO: {str(e)}'
        }, status=500)


async def get_iso_storage_info(request):
    """
    Get storage information for the ISO directory.
    
    Returns total, used, and available space, plus number of ISOs.
    """
    iso_storage_path = get_iso_storage_path()
    
    try:
        # Ensure directory exists
        Path(iso_storage_path).mkdir(parents=True, exist_ok=True)
        
        # Get filesystem stats
        stat = os.statvfs(iso_storage_path)
        
        # Calculate sizes in bytes
        total_space = stat.f_blocks * stat.f_frsize
        available_space = stat.f_bavail * stat.f_frsize
        used_space = total_space - available_space
        
        # Count ISOs
        iso_count = sum(1 for entry in os.scandir(iso_storage_path) 
                       if entry.is_file() and entry.name.lower().endswith('.iso'))
        
        return web.json_response({
            'status': 'success',
            'total_space': total_space,
            'used_space': used_space,
            'available_space': available_space,
            'total_space_gb': round(total_space / (1024**3), 2),
            'used_space_gb': round(used_space / (1024**3), 2),
            'available_space_gb': round(available_space / (1024**3), 2),
            'iso_count': iso_count,
            'storage_path': iso_storage_path
        })
    except Exception as e:
        logger.error(f"Error getting storage info: {e}")
        return web.json_response({
            'status': 'error',
            'message': f'Failed to get storage info: {str(e)}'
        }, status=500)
