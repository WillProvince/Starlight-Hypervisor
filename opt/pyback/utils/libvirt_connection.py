"""
Libvirt connection management utilities.

This module provides functions for establishing and managing connections
to libvirt and retrieving domain objects.
"""

import logging
import libvirt
from ..config import LIBVIRT_URI, LIBVIRT_LXC_URI

logger = logging.getLogger(__name__)


def get_connection(conn_type='qemu'):
    """Connects to libvirt or returns None/raises exception.
    
    Args:
        conn_type: 'qemu' for VMs or 'lxc' for containers
        
    Returns:
        libvirt connection object or None on failure
    """
    try:
        uri = LIBVIRT_LXC_URI if conn_type == 'lxc' else LIBVIRT_URI
        conn = libvirt.open(uri)
        if conn is None:
            logger.error(f"Failed to open connection to {uri}")
            return None
        return conn
    except libvirt.libvirtError as e:
        logger.error(f"LIBVIRT ERROR: {e}")
        return None


def get_domain_by_name(conn, name):
    """Safely look up a domain by name.
    
    Args:
        conn: libvirt connection object
        name: domain name to lookup
        
    Returns:
        domain object or None if not found
    """
    try:
        return conn.lookupByName(name)
    except libvirt.libvirtError:
        return None
