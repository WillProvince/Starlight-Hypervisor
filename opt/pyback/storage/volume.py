"""
Storage volume creation and management.

This module provides functions for creating and managing libvirt storage volumes.
"""

import os
import logging
import libvirt
from ..config_loader import get_vm_storage_path, get_default_pool_name
from .pool import ensure_storage_pool

logger = logging.getLogger(__name__)


def create_storage_volume(conn, name, size_gb):
    """Creates a qcow2 storage volume in the default pool.
    
    Args:
        conn: libvirt connection object
        name: volume name (without extension)
        size_gb: size in gigabytes
        
    Returns:
        str: path to created disk
        
    Raises:
        Exception: if pool not found, not running, volume exists, or creation fails
    """
    # Get configuration dynamically
    pool_name = get_default_pool_name()
    storage_path = get_vm_storage_path()
    
    # Ensure storage pool exists and is running (creates if necessary)
    try:
        pool = ensure_storage_pool(conn, pool_name, storage_path)
    except Exception as e:
        raise Exception(f"Disk creation failed: {e}")

    size_bytes = size_gb * 1024 * 1024 * 1024
    disk_filename = f"{name}.qcow2"
    disk_path = f"{storage_path}/{disk_filename}"
    
    # Check if a volume with this name already exists
    try:
        pool.storageVolLookupByName(disk_filename)
        raise Exception(f"Disk volume '{disk_filename}' already exists in pool.")
    except libvirt.libvirtError as e:
        # Only proceed if volume doesn't exist
        if e.get_error_code() != libvirt.VIR_ERR_NO_STORAGE_VOL:
            raise e
            
    # Define the volume XML
    from textwrap import dedent
    vol_xml = dedent(f"""
        <volume>
          <name>{disk_filename}</name>
          <capacity unit='bytes'>{size_bytes}</capacity>
          <allocation unit='bytes'>0</allocation>
          <target>
            <path>{disk_path}</path>
            <format type='qcow2'/>
            <permissions>
              <mode>0644</mode>
              <owner>107</owner>
              <group>107</group>
            </permissions>
          </target>
        </volume>
    """).strip()
    
    vol = pool.createXML(vol_xml, 0)
    if vol is None:
        raise Exception("Libvirt failed to create storage volume (returned None).")
    
    if not os.path.exists(disk_path):
        raise Exception(f"Disk creation failed silently! Libvirt reported success, but file not found at {disk_path}. Check permissions/SELinux on host.")
        
    return disk_path
