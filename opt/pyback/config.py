"""
Configuration module for Starlight Hypervisor Manager.

This module provides configuration constants used throughout the application.
Configuration is now loaded dynamically from JSON files via config_loader.

For backward compatibility, this module exposes the same constant names,
but values are now retrieved from the config_loader module.
"""

import os

# Import dynamic configuration loader
from .config_loader import (
    # Configuration functions
    get_storage_config,
    get_system_config,
    get_vm_storage_path,
    get_iso_storage_path,
    get_default_pool_name,
    get_network_mode,
    get_bridge_name,
    get_nat_network_name,
    get_service_name,
    # Path constants
    CONFIG_BASE_DIR,
    CONFIG_DIR,
    DATA_DIR,
    PREFERENCES_DIR,
    ROLLBACK_DIR as BACKUP_DIR,
    # Configuration file paths
    STORAGE_CONFIG_PATH,
    SYSTEM_CONFIG_PATH,
    REPOSITORIES_CONFIG_PATH,
    AUTH_CONFIG_PATH,
    UPDATE_CONFIG_PATH,
    VERSION_FILE_PATH,
    # Data file paths
    VM_METADATA_PATH,
    LXC_METADATA_PATH,
    USERS_METADATA_PATH,
    API_KEYS_PATH,
)

# --- Libvirt Configuration ---
LIBVIRT_URI = 'qemu:///system'
LIBVIRT_LXC_URI = 'lxc:///'  # URI for LXC containers


# --- Dynamic Storage Configuration Properties ---
# These are now loaded from /etc/starlight/config/storage.json
# with fallback to /etc/starlight/storage.json for backward compatibility

class _DynamicStorageConfig:
    """Provides dynamic access to storage configuration values."""
    
    @property
    def DEFAULT_STORAGE_PATH(self) -> str:
        """VM storage path (dynamically loaded)."""
        return get_vm_storage_path()
    
    @property
    def DEFAULT_POOL_NAME(self) -> str:
        """Default storage pool name (dynamically loaded)."""
        return get_default_pool_name()
    
    @property
    def ISO_STORAGE_PATH(self) -> str:
        """ISO storage path (dynamically loaded)."""
        return get_iso_storage_path()


class _DynamicNetworkConfig:
    """Provides dynamic access to network configuration values."""
    
    @property
    def NETWORK_MODE(self) -> str:
        """Network mode: 'bridge' or 'nat' (dynamically loaded)."""
        return get_network_mode()
    
    @property
    def BRIDGE_NAME(self) -> str:
        """Bridge device name (dynamically loaded)."""
        return get_bridge_name()
    
    @property
    def NAT_NETWORK_NAME(self) -> str:
        """NAT network name (dynamically loaded)."""
        return get_nat_network_name()


class _DynamicServiceConfig:
    """Provides dynamic access to service configuration values."""
    
    @property
    def SERVICE_NAME(self) -> str:
        """Systemd service name (dynamically loaded)."""
        return get_service_name()


# Create instances for backward-compatible access
_storage_config = _DynamicStorageConfig()
_network_config = _DynamicNetworkConfig()
_service_config = _DynamicServiceConfig()


# --- Module-level function to get current config values ---
# Use these functions instead of the constants above for clearer code

def get_storage_path() -> str:
    """Get the current VM storage path."""
    return get_vm_storage_path()


def get_pool_name() -> str:
    """Get the current default pool name."""
    return get_default_pool_name()


# --- Static Paths (these don't change) ---

# Git Repository Path
# Calculate git repository path: from /path/to/repo/opt/pyback/main.py -> /path/to/repo
GIT_REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


# --- For direct import compatibility, expose commonly used values ---
# Note: These are loaded once at import time. For runtime updates, use the functions above.

def _get_default_storage_path():
    """Get default storage path at module load time."""
    try:
        return get_vm_storage_path()
    except Exception:
        return '/var/lib/libvirt/images'  # Fallback default


def _get_default_pool_name():
    """Get default pool name at module load time."""
    try:
        return get_default_pool_name()
    except Exception:
        return 'default'  # Fallback default


def _get_network_mode():
    """Get network mode at module load time."""
    try:
        return get_network_mode()
    except Exception:
        return 'bridge'  # Fallback default


def _get_bridge_name():
    """Get bridge name at module load time."""
    try:
        return get_bridge_name()
    except Exception:
        return 'br0'  # Fallback default


def _get_nat_network_name():
    """Get NAT network name at module load time."""
    try:
        return get_nat_network_name()
    except Exception:
        return 'default'  # Fallback default


def _get_service_name():
    """Get service name at module load time."""
    try:
        return get_service_name()
    except Exception:
        return 'starlight-backend'  # Fallback default


def _get_iso_storage_path():
    """Get ISO storage path at module load time."""
    try:
        return get_iso_storage_path()
    except Exception:
        # Fallback: derive from VM storage path using proper path manipulation
        try:
            vm_path = get_vm_storage_path()
            parent_dir = os.path.dirname(vm_path)
            return os.path.join(parent_dir, 'isos')
        except Exception:
            return '/var/lib/libvirt/isos'  # Final fallback


# Initialize with dynamic values - these can be imported directly
# WARNING: These are loaded once. For always-current values, use the functions.
DEFAULT_STORAGE_PATH = _get_default_storage_path()
DEFAULT_POOL_NAME = _get_default_pool_name()
ISO_STORAGE_PATH = _get_iso_storage_path()
NETWORK_MODE = _get_network_mode()
BRIDGE_NAME = _get_bridge_name()
NAT_NETWORK_NAME = _get_nat_network_name()
SERVICE_NAME = _get_service_name()
