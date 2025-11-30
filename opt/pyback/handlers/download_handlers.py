"""
Download progress tracking handlers.

This module provides HTTP request handlers for tracking download progress
and managing orphaned containers.
"""

import os
import shutil
import logging
import libvirt
from aiohttp import web

from ..config_loader import get_vm_storage_path
from ..utils.libvirt_connection import get_connection
from ..models.lxc import get_lxc_metadata

logger = logging.getLogger(__name__)

# Download progress tracking dictionary (shared with vm_deployment module via main.py)
download_progress = {}


async def get_download_progress(request):
    """Returns the current download progress for a VM."""
    vm_name = request.match_info.get('vm_name')
    
    if vm_name in download_progress:
        return web.json_response({'status': 'success', 'progress': download_progress[vm_name]})
    else:
        return web.json_response({'status': 'error', 'message': 'No download in progress for this VM'}, status=404)


async def get_all_downloads(request):
    """Returns all current download progresses."""
    return web.json_response({'status': 'success', 'downloads': download_progress})


async def get_deployment_logs(request):
    """Returns recent deployment logs for debugging."""
    # Return last 100 lines of logs (stored in memory)
    # For now, just return download progress and any stored errors
    return web.json_response({
        'status': 'success', 
        'downloads': download_progress,
        'message': 'Check server console for detailed logs'
    })


async def cleanup_orphaned_containers(request):
    """Finds and optionally removes orphaned LXC containers that failed during installation."""
    try:
        data = await request.json()
    except:
        data = {}
    
    action = data.get('action', 'list')  # 'list' or 'cleanup'
    container_name = data.get('name')  # Optional: specific container to cleanup
    
    orphaned = []
    
    # Check LXC connection for containers
    lxc_conn = get_connection('lxc')
    if lxc_conn:
        try:
            containers = lxc_conn.listAllDomains(libvirt.VIR_CONNECT_LIST_DOMAINS_ACTIVE | libvirt.VIR_CONNECT_LIST_DOMAINS_INACTIVE)
            
            for container in containers:
                name = container.name()
                
                # Check if this container has metadata (properly installed)
                lxc_metadata = get_lxc_metadata(name)
                if not lxc_metadata or 'type' not in lxc_metadata:
                    # This is an orphaned container
                    orphaned.append({
                        'name': name,
                        'state': container.isActive(),
                        'id': container.ID() if container.isActive() else None
                    })
                    
                    # If cleanup action and matches the name (or no specific name given)
                    if action == 'cleanup' and (not container_name or container_name == name):
                        try:
                            # Stop if running
                            if container.isActive():
                                container.destroy()
                                logger.info(f"Stopped orphaned container {name}")
                            
                            # Undefine
                            container.undefine()
                            logger.info(f"Undefined orphaned container {name}")
                            
                            # Try to delete rootfs
                            storage_path = get_vm_storage_path()
                            rootfs_path = f"{storage_path}/{name}-rootfs"
                            if os.path.exists(rootfs_path):
                                shutil.rmtree(rootfs_path)
                                logger.info(f"Deleted orphaned rootfs at {rootfs_path}")
                        except Exception as e:
                            logger.error(f"Failed to cleanup {name}: {e}")
            
            lxc_conn.close()
        except Exception as e:
            logger.error(f"Error checking LXC containers: {e}")
            if lxc_conn:
                lxc_conn.close()
    
    if action == 'cleanup':
        return web.json_response({
            'status': 'success',
            'message': f'Cleaned up {len(orphaned)} orphaned container(s)',
            'cleaned': orphaned
        })
    else:
        return web.json_response({
            'status': 'success',
            'orphaned_containers': orphaned
        })
