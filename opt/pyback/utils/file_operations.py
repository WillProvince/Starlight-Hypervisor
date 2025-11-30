"""
File operations utilities.

This module provides functions for file compression, extraction, and name sanitization.
"""

import os
import re
import lzma
import tarfile
import logging

logger = logging.getLogger(__name__)


def sanitize_vm_name(name):
    """Sanitizes VM name for filesystem use.
    
    Args:
        name: VM name to sanitize
        
    Returns:
        sanitized VM name safe for filesystem use
    """
    # Convert to lowercase
    name = name.lower()
    # Replace spaces and special chars with hyphens
    name = re.sub(r'[^a-z0-9-]', '-', name)
    # Remove multiple consecutive hyphens
    name = re.sub(r'-+', '-', name)
    # Remove leading/trailing hyphens
    name = name.strip('-')
    # Ensure it's not empty
    if not name:
        name = 'vm'
    return name


def decompress_xz_file(source_path, dest_path):
    """Decompresses an .xz file. Runs in executor to avoid blocking.
    
    Args:
        source_path: path to compressed .xz file
        dest_path: path for decompressed output
    """
    with lzma.open(source_path, 'rb') as compressed:
        with open(dest_path, 'wb') as decompressed:
            while True:
                chunk = compressed.read(65536)
                if not chunk:
                    break
                decompressed.write(chunk)


def extract_tar_xz_rootfs(source_path, dest_dir):
    """Extracts a .tar.xz rootfs archive to a directory. Runs in executor to avoid blocking.
    
    Args:
        source_path: path to .tar.xz archive
        dest_dir: destination directory for extraction
        
    Raises:
        Exception: if extraction fails or verification shows incomplete extraction
    """
    # Ensure destination directory exists
    os.makedirs(dest_dir, exist_ok=True)
    
    try:
        # Extract the tar.xz file
        logger.info(f"Starting extraction of {source_path} to {dest_dir}")
        
        with tarfile.open(source_path, 'r:xz') as tar:
            # Get list of members for verification
            members = tar.getmembers()
            logger.info(f"Archive contains {len(members)} files/directories")
            
            # Extract all members - handle Python 3.12+ filter requirements
            try:
                # Python 3.12+ - use 'tar' filter which allows absolute links (needed for LXC rootfs)
                # This is less restrictive than 'data' but still safe for container rootfs
                tar.extractall(path=dest_dir, filter='tar')
                logger.info(f"Extracted using 'tar' filter (Python 3.12+)")
            except TypeError:
                # Older Python versions don't have the filter parameter
                tar.extractall(path=dest_dir)
                logger.info(f"Extracted without filter (Python < 3.12)")
            except Exception as filter_error:
                # If 'tar' filter fails, try fully unsafe for LXC containers
                logger.warning(f"Filter extraction failed: {filter_error}, trying unsafe extraction")
                try:
                    tar.extractall(path=dest_dir, filter='fully_trusted')
                    logger.info(f"Extracted using 'fully_trusted' filter")
                except:
                    # Last resort for older Python 3.12 versions
                    tar.extractall(path=dest_dir, filter=lambda member, path: member)
                    logger.info(f"Extracted using custom filter")
            
            logger.info(f"Successfully extracted {len(members)} files from {source_path} to {dest_dir}")
        
        # Verify extraction by checking for common directories
        expected_dirs = ['bin', 'etc', 'lib', 'sbin', 'usr']
        found_dirs = []
        for d in expected_dirs:
            check_path = os.path.join(dest_dir, d)
            if os.path.exists(check_path):
                found_dirs.append(d)
        
        logger.info(f"Extraction verification: Found directories {found_dirs} in rootfs")
        
        if not found_dirs:
            raise Exception("Extraction appears incomplete - no standard directories found in rootfs")
            
    except Exception as e:
        logger.error(f"Failed to extract tar.xz rootfs: {e}")
        raise Exception(f"Rootfs extraction failed: {e}")
