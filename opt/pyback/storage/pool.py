"""
Storage pool creation and management.

This module provides functions for creating and managing libvirt storage pools.
"""

import os
import logging
import libvirt
from textwrap import dedent

logger = logging.getLogger(__name__)


def create_storage_pool(conn, pool_name, storage_path):
    """Creates a directory-based storage pool.
    
    Args:
        conn: libvirt connection object
        pool_name: name for the storage pool
        storage_path: directory path for the pool
        
    Returns:
        libvirt storage pool object
        
    Raises:
        Exception: if pool creation fails
    """
    # Ensure the storage directory exists with proper permissions
    try:
        os.makedirs(storage_path, mode=0o755, exist_ok=True)
    except Exception as e:
        raise Exception(f"Failed to create storage directory {storage_path}: {e}")
    
    # Define the pool XML for a directory-based pool
    pool_xml = dedent(f"""
        <pool type='dir'>
          <name>{pool_name}</name>
          <target>
            <path>{storage_path}</path>
            <permissions>
              <mode>0755</mode>
            </permissions>
          </target>
        </pool>
    """).strip()
    
    try:
        pool = conn.storagePoolDefineXML(pool_xml, 0)
        if pool is None:
            raise Exception(f"Failed to define storage pool '{pool_name}'")
        
        logger.info(f"Storage pool '{pool_name}' defined at {storage_path}")
        
        # Set pool to autostart
        try:
            pool.setAutostart(1)
            logger.info(f"Storage pool '{pool_name}' set to autostart")
        except Exception as e:
            logger.warning(f"Failed to set autostart for pool '{pool_name}': {e}")
        
        return pool
        
    except libvirt.libvirtError as e:
        raise Exception(f"Libvirt error creating storage pool '{pool_name}': {e}")


def start_storage_pool(pool):
    """Starts a stopped storage pool.
    
    Args:
        pool: libvirt storage pool object
        
    Raises:
        Exception: if pool start fails
    """
    try:
        pool.create(0)
        pool_name = pool.name()
        logger.info(f"Storage pool '{pool_name}' started successfully")
    except libvirt.libvirtError as e:
        raise Exception(f"Failed to start storage pool: {e}")


def ensure_storage_pool(conn, pool_name, storage_path):
    """Ensures a storage pool exists and is running, creating it if necessary.
    
    This function will:
    1. Check if the pool exists
    2. If not, create and start it
    3. If it exists but isn't running, start it
    4. Set the pool to autostart
    
    Args:
        conn: libvirt connection object
        pool_name: name for the storage pool
        storage_path: directory path for the pool
        
    Returns:
        libvirt storage pool object
        
    Raises:
        Exception: if pool cannot be created or started
    """
    try:
        # Try to lookup the pool by name
        pool = conn.storagePoolLookupByName(pool_name)
        
        # Pool exists, check if it's running
        pool_info = pool.info()
        if pool_info[0] != libvirt.VIR_STORAGE_POOL_RUNNING:
            logger.info(f"Storage pool '{pool_name}' exists but not running, starting it...")
            start_storage_pool(pool)
        else:
            logger.debug(f"Storage pool '{pool_name}' already exists and is running")
        
        return pool
        
    except libvirt.libvirtError as e:
        # Pool doesn't exist, create it
        # Check for VIR_ERR_NO_STORAGE_POOL error code
        error_code = e.get_error_code()
        if error_code == libvirt.VIR_ERR_NO_STORAGE_POOL:
            logger.info(f"Storage pool '{pool_name}' not found, creating it at {storage_path}...")
            pool = create_storage_pool(conn, pool_name, storage_path)
            
            # Start the newly created pool
            start_storage_pool(pool)
            
            return pool
        else:
            # Some other libvirt error
            raise Exception(f"Error accessing storage pool '{pool_name}': {e}")
