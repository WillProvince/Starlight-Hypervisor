"""
Storage package for Starlight Hypervisor Manager.

This package contains storage management functions for creating and managing
storage volumes and pools.
"""

from .pool import ensure_storage_pool, create_storage_pool, start_storage_pool
from .volume import create_storage_volume

__all__ = [
    'ensure_storage_pool',
    'create_storage_pool', 
    'start_storage_pool',
    'create_storage_volume',
]
