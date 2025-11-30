"""
VM action handlers.

This module provides HTTP request handlers for VM actions such as
start, stop, destroy, and delete operations.
"""

import os
import shutil
import logging
import libvirt
from aiohttp import web

from ..config_loader import get_default_pool_name, get_vm_storage_path
from ..utils.libvirt_connection import get_connection, get_domain_by_name
from ..models.lxc import get_lxc_metadata, load_lxc_metadata, save_lxc_metadata

logger = logging.getLogger(__name__)


async def vm_action(request):
    """Performs an action (start, stop, destroy, delete/undefine) on a VM or LXC container."""
    name = request.match_info.get('name')
    action = request.match_info.get('action')
    
    # Try to find the domain in either QEMU or LXC connections
    # First, check LXC metadata to determine type
    lxc_metadata = get_lxc_metadata(name)
    is_lxc = lxc_metadata.get('type') == 'lxc'
    
    # Try the appropriate connection first based on metadata
    conn = None
    domain = None
    conn_type = 'lxc' if is_lxc else 'qemu'
    
    conn = get_connection(conn_type)
    if conn:
        domain = get_domain_by_name(conn, name)
    
    # If not found and we checked QEMU, try LXC
    if not domain and conn_type == 'qemu':
        if conn:
            conn.close()
        conn = get_connection('lxc')
        if conn:
            domain = get_domain_by_name(conn, name)
            conn_type = 'lxc' if domain else 'qemu'
    
    # If not found and we checked LXC, try QEMU
    if not domain and conn_type == 'lxc':
        if conn:
            conn.close()
        conn = get_connection('qemu')
        if conn:
            domain = get_domain_by_name(conn, name)
            conn_type = 'qemu' if domain else 'lxc'
    
    if not conn:
        return web.json_response({'status': 'error', 'message': 'Could not connect to libvirt.'}, status=500)
    
    if not domain:
        conn.close()
        return web.json_response({'status': 'error', 'message': f'VM/Container named {name} not found.'}, status=404)

    try:
        entity_type = "Container" if conn_type == 'lxc' else "VM"
        
        if action == 'start':
            domain.create() 
            message = f'{entity_type} {name} started.'
        elif action == 'stop':
            domain.shutdown() 
            message = f'{entity_type} {name} received graceful shutdown request.'
        elif action == 'destroy':
            domain.destroy() 
            message = f'{entity_type} {name} force stopped (destroyed).'
        elif action == 'delete':
            if domain.isActive():
                domain.destroy()
            
            message = ""
            
            # Get storage configuration dynamically
            storage_path = get_vm_storage_path()
            pool_name = get_default_pool_name()
            
            # Handle storage cleanup based on type
            if conn_type == 'lxc':
                # For LXC containers, delete the rootfs directory
                rootfs_path = f"{storage_path}/{name}-rootfs"
                try:
                    if os.path.exists(rootfs_path):
                        shutil.rmtree(rootfs_path)
                        message += f' Associated rootfs directory {rootfs_path} also deleted.'
                        logger.info(f"Deleted LXC rootfs at {rootfs_path}")
                    else:
                        message += f' Note: Rootfs directory not found at {rootfs_path}.'
                except Exception as e:
                    message += f' Warning: Could not delete rootfs directory: {e}'
                    logger.warning(f"Failed to delete LXC rootfs at {rootfs_path}: {e}")
                
                # Remove from LXC metadata
                try:
                    lxc_metadata = load_lxc_metadata()
                    if name in lxc_metadata:
                        del lxc_metadata[name]
                        save_lxc_metadata(lxc_metadata)
                        logger.info(f"Removed {name} from LXC metadata")
                except Exception as e:
                    logger.warning(f"Failed to update LXC metadata: {e}")
            else:
                # For VMs, delete the qcow2 disk volume
                try:
                    pool = conn.storagePoolLookupByName(pool_name)
                    disk_filename = f"{name}.qcow2"
                    vol = pool.storageVolLookupByName(disk_filename)
                    if vol:
                        vol.delete(0) 
                        message += f' Associated disk {disk_filename} also deleted.'
                except libvirt.libvirtError:
                    message += f' Note: Could not find/delete disk volume for {name}.qcow2.'
            
            # Undefine the domain
            try:
                # Try to undefine with NVRAM and other managed files (for VMs)
                if conn_type == 'qemu':
                    undefine_flags = (libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE | 
                                     libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA | 
                                     libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
                    domain.undefineFlags(undefine_flags)
                else:
                    # For LXC, use simpler undefine
                    domain.undefine()
            except libvirt.libvirtError:
                # Fallback to regular undefine if flags not supported
                domain.undefine()
            
            message = f'{entity_type} {name} configuration permanently removed (undefined). ' + message
            
        else:
            conn.close()
            return web.json_response({'status': 'error', 'message': f'Invalid action: {action}'}, status=400)

        conn.close()
        return web.json_response({'status': 'success', 'message': message})

    except libvirt.libvirtError as e:
        conn.close()
        return web.json_response({'status': 'error', 'message': f'Libvirt operation failed: {e}'}, status=500)
