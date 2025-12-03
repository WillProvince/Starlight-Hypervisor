"""
VM deployment handlers.

This module provides HTTP request handlers for deploying VMs from remote URLs
and managing repository configurations.
"""

import os
import json
import shutil
import logging
import asyncio
import aiohttp
import libvirt
import time
from aiohttp import web
from xml.etree import ElementTree as ET

from ..config_loader import (
    get_vm_storage_path, get_default_pool_name,
    get_network_mode, get_bridge_name, get_nat_network_name,
    get_config_file_path
)
from ..utils.libvirt_connection import get_connection, get_domain_by_name
from ..utils.file_operations import decompress_xz_file, extract_tar_xz_rootfs
from ..models.vm import set_vm_metadata
from ..models.lxc import set_lxc_metadata
from ..storage.volume import create_storage_volume

logger = logging.getLogger(__name__)

# Download progress tracking dictionary (initialized from download_handlers via main.py)
download_progress = {}


def update_download_status(vm_name, status, message=None, progress=None, total=None):
    """Helper function to update download progress with timestamp."""
    if vm_name not in download_progress:
        download_progress[vm_name] = {}
    
    download_progress[vm_name]['status'] = status
    download_progress[vm_name]['timestamp'] = time.time()
    
    if message is not None:
        download_progress[vm_name]['message'] = message
    if progress is not None:
        download_progress[vm_name]['progress'] = progress
    if total is not None:
        download_progress[vm_name]['total'] = total


def load_repositories_config():
    """Loads the repositories configuration from JSON file."""
    try:
        # Try new path first, then legacy
        repositories_path = get_config_file_path('repositories')
        legacy_path = get_config_file_path('repositories', use_legacy=True)
        
        config_path = repositories_path if os.path.exists(repositories_path) else legacy_path
        
        if not os.path.exists(config_path):
            logger.warning(f"Repository config not found at {config_path}")
            return {"repositories": []}
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config
    except Exception as e:
        logger.error(f"Error loading repositories config: {e}")
        return {"repositories": []}


def save_repositories_config(config):
    """Saves the repositories configuration to JSON file."""
    try:
        repositories_path = get_config_file_path('repositories')
        os.makedirs(os.path.dirname(repositories_path), exist_ok=True)
        with open(repositories_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving repositories config: {e}")
        return False


async def fetch_repository_apps(repo_url):
    """Fetches apps from a single repository URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(repo_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                # GitHub raw URLs return text/plain, so read as text and parse manually
                text = await resp.text()
                data = json.loads(text)
                return data.get('apps', [])
    except Exception as e:
        logger.error(f"Error fetching apps from {repo_url}: {e}")
        return None


async def deploy_vm_from_url(request):
    """
    Fetches a VM/LXC XML definition from a remote URL, defines it in libvirt, 
    and then starts it. Optionally downloads a cloud image to use as the base disk.
    Supports both VMs and LXC containers based on 'type' field.
    """
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({'status': 'error', 'message': 'Invalid JSON body.'}, status=400)

    logger.info(f"Deploy request body: {json.dumps(data, indent=2)}")

    xml_url = data.get('xml_url')
    vm_name = data.get('vm_name')
    disk_size_gb = data.get('disk_size_gb')
    iso_path = data.get('iso_path')
    cloud_image_url = data.get('cloud_image_url')
    
    # Check for image_source structure (from repo.json format)
    if not cloud_image_url:
        image_source = data.get('image_source')
        logger.info(f"Checking image_source: {image_source}")
        if image_source and isinstance(image_source, dict):
            cloud_image_url = image_source.get('url')
            logger.info(f"Extracted URL from image_source: {cloud_image_url}")
    
    deploy_type = data.get('type', 'vm')  # 'vm' or 'lxc'
    icon_url = data.get('icon')
    app_name = data.get('app_name')
    
    logger.info(f"Deploy request received - Name: {vm_name}, Type: {deploy_type}, XML URL: {xml_url}, Image URL: {cloud_image_url}, Icon: {icon_url}")

    if not all([xml_url, vm_name, disk_size_gb]):
        return web.json_response({'status': 'error', 'message': 'Missing XML URL, VM name, or required disk size.'}, status=400)
    
    # Validate that LXC containers have a rootfs source
    if deploy_type == 'lxc' and not cloud_image_url and not iso_path:
        logger.warning(f"LXC container {vm_name} being deployed without rootfs image - it will be empty!")
    
    # Connect to appropriate libvirt instance based on type
    conn_type = 'lxc' if deploy_type == 'lxc' else 'qemu'
    conn = get_connection(conn_type)
    if not conn:
        return web.json_response({'status': 'error', 'message': f'Could not connect to libvirt ({conn_type}).'}, status=500)
    
    if get_domain_by_name(conn, vm_name):
        conn.close()
        return web.json_response({'status': 'error', 'message': f'{"Container" if deploy_type == "lxc" else "VM"} named {vm_name} already exists.'}, status=409)

    # 1. Fetch the XML from the remote URL
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(xml_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to fetch XML from {xml_url}. Status: {resp.status}")
                xml_config = await resp.text()
    except Exception as e:
        conn.close()
        return web.json_response({'status': 'error', 'message': f'Remote XML fetch error: {e}'}, status=500)
        
    # 2. Create the disk/rootfs - either empty or download a cloud image/rootfs
    disk_path = None
    rootfs_path = None
    try:
        if cloud_image_url:
            # Initialize download progress tracking
            update_download_status(vm_name, 'downloading', 'Starting download...', progress=0, total=0)
            
            # Check if URL points to a compressed file
            is_tar_xz = cloud_image_url.endswith('.tar.xz')
            is_xz = cloud_image_url.endswith('.xz') and not is_tar_xz
            
            # Get storage path dynamically
            storage_path = get_vm_storage_path()
            
            # For LXC containers with tar.xz rootfs
            if deploy_type == 'lxc' and is_tar_xz:
                rootfs_path = f"{storage_path}/{vm_name}-rootfs"
                download_path = f"{storage_path}/{vm_name}-rootfs.tar.xz"
                
                logger.info(f"Downloading LXC rootfs from {cloud_image_url} to {download_path}")
                
                # Download the rootfs tarball with progress tracking
                async with aiohttp.ClientSession() as session:
                    async with session.get(cloud_image_url, timeout=aiohttp.ClientTimeout(total=1200)) as resp:
                        if resp.status != 200:
                            raise Exception(f"Failed to download rootfs. Status: {resp.status}")
                        
                        total_size = resp.content_length or 0
                        download_progress[vm_name]['total'] = total_size
                        downloaded = 0
                        
                        # Stream download to disk
                        with open(download_path, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(65536):  # 64KB chunks
                                f.write(chunk)
                                downloaded += len(chunk)
                                download_progress[vm_name]['progress'] = downloaded
                                if total_size > 0:
                                    percent = int((downloaded / total_size) * 100)
                                    download_progress[vm_name]['message'] = f'Downloading: {percent}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)'
                
                logger.info(f"Rootfs tarball downloaded successfully.")
                
                # Extract the tar.xz rootfs
                update_download_status(vm_name, 'extracting', 'Extracting rootfs...')
                logger.info(f"Extracting {download_path} to {rootfs_path}")
                
                # Run extraction in executor to avoid blocking
                loop = asyncio.get_event_loop()
                try:
                    await loop.run_in_executor(None, extract_tar_xz_rootfs, download_path, rootfs_path)
                except Exception as e:
                    # Cleanup on extraction failure
                    logger.error(f"Extraction failed for {vm_name}: {e}")
                    if os.path.exists(download_path):
                        os.remove(download_path)
                    if os.path.exists(rootfs_path):
                        shutil.rmtree(rootfs_path)
                    raise Exception(f"Failed to extract rootfs: {e}")
                
                # Remove tarball after successful extraction
                os.remove(download_path)
                logger.info(f"Extraction complete. Removed {download_path}")
                
                # Verify rootfs exists and has content
                if not os.path.exists(rootfs_path):
                    raise Exception(f"Rootfs extraction failed: directory not found at {rootfs_path}")
                
                # Check that rootfs has the expected structure
                required_paths = [os.path.join(rootfs_path, d) for d in ['bin', 'etc', 'sbin']]
                missing_paths = [p for p in required_paths if not os.path.exists(p)]
                if len(missing_paths) == len(required_paths):
                    raise Exception(f"Rootfs extraction appears incomplete - missing core directories")
                
                # Check for init binary location (important for LXC)
                init_paths = ['/sbin/init', '/bin/init', '/lib/systemd/systemd', '/init']
                found_init = None
                for init_path in init_paths:
                    full_init_path = os.path.join(rootfs_path, init_path.lstrip('/'))
                    if os.path.exists(full_init_path):
                        found_init = init_path
                        logger.info(f"Found init at {init_path} in rootfs")
                        break
                
                if not found_init:
                    logger.warning(f"No init found in rootfs at standard locations. Container may fail to start.")
                
                update_download_status(vm_name, 'completed', 'Rootfs ready')
                logger.info(f"Rootfs preparation complete for {vm_name}")
                
                disk_path = rootfs_path  # Set disk_path to rootfs for XML injection
                
            # For VMs with qcow2 images
            else:
                # Download cloud image and use it as the base disk
                disk_path = f"{storage_path}/{vm_name}.qcow2"
                download_path = f"{disk_path}.xz" if is_xz else disk_path
                
                logger.info(f"Downloading cloud image from {cloud_image_url} to {download_path}")
                
                # Download the image with progress tracking
                async with aiohttp.ClientSession() as session:
                    async with session.get(cloud_image_url, timeout=aiohttp.ClientTimeout(total=1200)) as resp:
                        if resp.status != 200:
                            raise Exception(f"Failed to download cloud image. Status: {resp.status}")
                        
                        total_size = resp.content_length or 0
                        download_progress[vm_name]['total'] = total_size
                        downloaded = 0
                        
                        # Stream download to disk
                        with open(download_path, 'wb') as f:
                            async for chunk in resp.content.iter_chunked(65536):  # 64KB chunks
                                f.write(chunk)
                                downloaded += len(chunk)
                                download_progress[vm_name]['progress'] = downloaded
                                if total_size > 0:
                                    percent = int((downloaded / total_size) * 100)
                                    download_progress[vm_name]['message'] = f'Downloading: {percent}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)'
                    
                        logger.info(f"Cloud image downloaded successfully.")
                        
                        # Decompress if needed (run in executor to avoid blocking)
                        if is_xz:
                            update_download_status(vm_name, 'decompressing', 'Decompressing image...')
                            logger.info(f"Decompressing {download_path} to {disk_path}")
                            
                            # Run decompression in a thread to avoid blocking the event loop
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, decompress_xz_file, download_path, disk_path)
                            
                            # Remove compressed file
                            os.remove(download_path)
                            logger.info(f"Decompression complete. Removed {download_path}")
                            
                            # Verify decompressed file exists and is valid
                            if not os.path.exists(disk_path):
                                raise Exception(f"Decompression failed: output file not found at {disk_path}")
                            
                            file_size = os.path.getsize(disk_path)
                            logger.info(f"Decompressed file size: {file_size / (1024*1024):.2f} MB")
                            
                            # Check file format - might need conversion from raw to qcow2
                            update_download_status(vm_name, 'checking', 'Verifying image format...')
                            logger.info(f"Checking image format of {disk_path}")
                            
                            # Check what format the file is
                            check_process = await asyncio.create_subprocess_exec(
                                'qemu-img', 'info', disk_path,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            stdout, stderr = await check_process.communicate()
                            
                            if check_process.returncode == 0:
                                format_info = stdout.decode()
                                logger.info(f"Image format info: {format_info}")
                                
                                # If it's a raw image, convert to qcow2
                                if 'file format: raw' in format_info:
                                    logger.info(f"Converting raw image to qcow2 format...")
                                    download_progress[vm_name]['message'] = 'Converting to qcow2 format...'
                                    
                                    temp_path = f"{disk_path}.raw"
                                    os.rename(disk_path, temp_path)
                                    
                                    convert_process = await asyncio.create_subprocess_exec(
                                        'qemu-img', 'convert', '-f', 'raw', '-O', 'qcow2', temp_path, disk_path,
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE
                                    )
                                    convert_stdout, convert_stderr = await convert_process.communicate()
                                    
                                    if convert_process.returncode != 0:
                                        error_msg = convert_stderr.decode() if convert_stderr else "Unknown error"
                                        raise Exception(f"Failed to convert image to qcow2: {error_msg}")
                                    
                                    # Remove raw file
                                    os.remove(temp_path)
                                    logger.info(f"Successfully converted to qcow2 format")
                            else:
                                logger.warning(f"Could not check image format: {stderr.decode()}")
                
                update_download_status(vm_name, 'resizing', 'Checking disk size...')
                logger.info(f"Checking current disk size for {disk_path}")
                
                # Get current disk size
                info_process = await asyncio.create_subprocess_exec(
                    'qemu-img', 'info', '--output=json', disk_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                info_stdout, info_stderr = await info_process.communicate()
                
                if info_process.returncode == 0:
                    import json as json_module
                    disk_info = json_module.loads(info_stdout.decode())
                    current_size_bytes = disk_info.get('virtual-size', 0)
                    current_size_gb = current_size_bytes / (1024**3)
                    target_size_gb = float(disk_size_gb)
                    
                    logger.info(f"Current disk size: {current_size_gb:.2f}GB, Target: {target_size_gb}GB")
                    
                    if current_size_gb < target_size_gb:
                        # Need to grow the disk
                        download_progress[vm_name]['message'] = f'Expanding disk from {current_size_gb:.1f}GB to {target_size_gb}GB...'
                        logger.info(f"Growing disk to {target_size_gb}GB")
                        
                        process = await asyncio.create_subprocess_exec(
                            'qemu-img', 'resize', disk_path, f'{disk_size_gb}G',
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await process.communicate()
                        
                        if process.returncode != 0:
                            error_msg = stderr.decode() if stderr else "Unknown error"
                            raise Exception(f"Failed to resize cloud image: {error_msg}")
                        
                        logger.info(f"Disk expanded successfully to {disk_size_gb}GB")
                    elif current_size_gb > target_size_gb:
                        # Image is already larger than requested - use current size
                        logger.info(f"Image is already {current_size_gb:.2f}GB, which is larger than requested {target_size_gb}GB. Using current size.")
                        download_progress[vm_name]['message'] = f'Using existing disk size ({current_size_gb:.1f}GB)'
                    else:
                        logger.info(f"Disk is already at target size {target_size_gb}GB")
                        download_progress[vm_name]['message'] = 'Disk size is correct'
                else:
                    # If we can't get info, try to resize anyway
                    logger.warning(f"Could not check disk size, attempting resize anyway")
                    download_progress[vm_name]['message'] = 'Resizing disk...'
                    
                    process = await asyncio.create_subprocess_exec(
                        'qemu-img', 'resize', disk_path, f'{disk_size_gb}G',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode != 0:
                        error_msg = stderr.decode() if stderr else "Unknown error"
                        # Don't fail if it's just a size issue
                        if "shrink" in error_msg.lower():
                            logger.warning(f"Image is larger than target size, using existing size")
                            download_progress[vm_name]['message'] = 'Using existing disk size'
                        else:
                            raise Exception(f"Failed to resize cloud image: {error_msg}")
                    
                    update_download_status(vm_name, 'completed', 'Image ready')
                    logger.info(f"Image preparation complete for {vm_name}")
                    
        else:
            # Create empty disk for ISO installation (VMs) or empty rootfs (LXC)
            storage_path = get_vm_storage_path()
            if deploy_type == 'lxc':
                # Create empty rootfs directory for LXC
                rootfs_path = f"{storage_path}/{vm_name}-rootfs"
                os.makedirs(rootfs_path, exist_ok=True)
                disk_path = rootfs_path
                logger.info(f"Created empty rootfs directory at {rootfs_path}")
            else:
                # Create empty disk for VM
                disk_path = create_storage_volume(conn, vm_name, disk_size_gb)
            
    except Exception as e:
        if vm_name in download_progress:
            update_download_status(vm_name, 'error', str(e))
        conn.close()
        return web.json_response({'status': 'error', 'message': f'Disk creation failed: {e}'}, status=500)

    # Parse and modify the XML to inject the specific disk path and network configuration
    try:
        root = ET.fromstring(xml_config)
        
        # Ensure the name matches the new VM name
        name_element = root.find('name')
        if name_element is not None:
            name_element.text = vm_name
        
        # Handle disk/filesystem path injection based on type
        if deploy_type == 'lxc':
            # For LXC, update the filesystem source directory
            filesystem_element = root.find("./devices/filesystem[@type='mount']")
            if filesystem_element is not None:
                source_element = filesystem_element.find('source')
                if source_element is None:
                    source_element = ET.SubElement(filesystem_element, 'source')
                source_element.set('dir', disk_path)
                logger.info(f"Updated LXC rootfs path to {disk_path}")
            else:
                raise Exception("Remote LXC XML missing filesystem mount definition.")
            
            # Check and update init path if needed (for Alpine and other non-systemd distros)
            if cloud_image_url and cloud_image_url.endswith('.tar.xz'):
                # Detect init path in the extracted rootfs
                init_paths = ['/sbin/init', '/bin/init', '/lib/systemd/systemd', '/init']
                found_init = None
                for init_path in init_paths:
                    full_init_path = os.path.join(disk_path, init_path.lstrip('/'))
                    if os.path.exists(full_init_path):
                        found_init = init_path
                        break
                
                # Update init path in XML if we found one
                if found_init:
                    init_element = root.find('./os/init')
                    if init_element is not None:
                        init_element.text = found_init
                        logger.info(f"Updated LXC init path to {found_init}")
                    else:
                        # Add init element if not present
                        os_element = root.find('os')
                        if os_element is not None:
                            init_element = ET.SubElement(os_element, 'init')
                            init_element.text = found_init
                            logger.info(f"Added LXC init path: {found_init}")
        else:
            # For VMs, find the first disk that is a 'file' and is a 'disk' device
            disk_element = root.find("./devices/disk[@type='file'][@device='disk']")
            if disk_element is None:
                raise Exception("Remote VM XML missing a main disk definition to modify.")
            
            # Update the <source file='...'/> path
            source_element = disk_element.find('source')
            if source_element is None:
                source_element = ET.SubElement(disk_element, 'source')
            source_element.set('file', disk_path)
        
        # Update network interface to use current network configuration (loaded dynamically)
        network_mode = get_network_mode()
        bridge_name = get_bridge_name()
        nat_network_name = get_nat_network_name()
        
        devices = root.find('devices')
        if devices is not None:
            # Find and remove existing network interfaces
            for interface in devices.findall('interface'):
                devices.remove(interface)
            
            # Add new interface with correct network configuration
            if network_mode == 'bridge':
                # Create bridge interface - points directly to bridge device
                interface = ET.SubElement(devices, 'interface', type='bridge')
                ET.SubElement(interface, 'source', bridge=bridge_name)
                ET.SubElement(interface, 'model', type='virtio')
                logger.info(f"Configured VM {vm_name} with bridge device: {bridge_name}")
            else:
                # Create NAT interface - uses libvirt network
                interface = ET.SubElement(devices, 'interface', type='network')
                ET.SubElement(interface, 'source', network=nat_network_name)
                ET.SubElement(interface, 'model', type='virtio')
                logger.info(f"Configured VM {vm_name} with NAT network: {nat_network_name}")
        
        # If ISO path provided, add CD-ROM device
        if iso_path and os.path.exists(iso_path):
            devices = root.find('devices')
            
            # Add CD-ROM disk
            cdrom = ET.SubElement(devices, 'disk', type='file', device='cdrom')
            ET.SubElement(cdrom, 'driver', name='qemu', type='raw')
            ET.SubElement(cdrom, 'source', file=iso_path)
            ET.SubElement(cdrom, 'target', dev='hdc', bus='sata')
            ET.SubElement(cdrom, 'readonly')
            
            # Update boot order to boot from CD first
            os_element = root.find('os')
            if os_element is not None:
                # Remove existing boot entries
                for boot in os_element.findall('boot'):
                    os_element.remove(boot)
                # Add CD boot first, then HD
                ET.SubElement(os_element, 'boot', dev='cdrom')
                ET.SubElement(os_element, 'boot', dev='hd')
        
        # Add security label to disable AppArmor
        seclabel = ET.SubElement(root, 'seclabel')
        seclabel.set('type', 'none')
        seclabel.set('model', 'apparmor')
        
        # Convert back to string
        final_xml = ET.tostring(root, encoding='unicode')
        
    except Exception as e:
        # Cleanup the disk if we fail XML modification
        logger.error(f"XML modification error for {vm_name}: {e}")
        if vm_name in download_progress:
            update_download_status(vm_name, 'error', f'XML modification failed: {e}')
        try:
            if os.path.exists(disk_path):
                os.remove(disk_path)
        except:
            pass
        try:
            pool_name = get_default_pool_name()
            pool = conn.storagePoolLookupByName(pool_name)
            vol = pool.storageVolLookupByName(f"{vm_name}.qcow2")
            if vol: vol.delete(0)
        except:
            pass
        conn.close()
        return web.json_response({'status': 'error', 'message': f'XML modification error: {e}. Disk creation rolled back.'}, status=500)

    # 3. Define and Start the domain
    try:
        logger.info(f"Defining VM {vm_name} in libvirt...")
        domain = conn.defineXML(final_xml)
        if domain is None:
            raise Exception("Libvirt failed to define the domain from the modified XML.")
        
        logger.info(f"Starting VM {vm_name}...")
        domain.create()
        
        # Store metadata with type information and icon
        metadata = {'type': deploy_type}
        if icon_url:
            metadata['icon'] = icon_url
        if app_name:
            metadata['app_name'] = app_name
        
        if deploy_type == 'lxc':
            metadata['description'] = f'LXC container: {vm_name}'
            set_lxc_metadata(vm_name, metadata)
        else:
            set_vm_metadata(vm_name, metadata)
        
        # Clean up download progress on success
        if vm_name in download_progress:
            del download_progress[vm_name]
        
        conn.close()
        entity_type = "Container" if deploy_type == 'lxc' else "VM"
        logger.info(f"{entity_type} {vm_name} successfully deployed and started")
        
        if cloud_image_url:
            return web.json_response({'status': 'success', 'message': f'{entity_type} {vm_name} deployed from cloud image and started with a {disk_size_gb}GB disk.'})
        elif iso_path:
            return web.json_response({'status': 'success', 'message': f'{entity_type} {vm_name} created with installation ISO. Complete installation via VNC console.'})
        else:
            return web.json_response({'status': 'success', 'message': f'{entity_type} {vm_name} deployed with empty disk. Attach an ISO or image to install an OS.'})
        
    except libvirt.libvirtError as e:
        # Better error handling - don't try to delete things that might not exist
        error_message = str(e)
        logger.error(f"Libvirt error for {vm_name}: {error_message}")
        if vm_name in download_progress:
            update_download_status(vm_name, 'error', f'VM creation failed: {error_message}')
        conn.close()
        return web.json_response({'status': 'error', 'message': f'Libvirt operation failed during deployment: {error_message}'}, status=500)
    except Exception as e:
        logger.error(f"Unexpected error for {vm_name}: {e}")
        if vm_name in download_progress:
            update_download_status(vm_name, 'error', str(e))
        conn.close()
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)
