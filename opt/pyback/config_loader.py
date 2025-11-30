"""
Dynamic Configuration Loader for Starlight Hypervisor Manager.

This module provides runtime configuration loading from JSON files with:
- Default values if files don't exist
- Caching with ability to reload
- Path validation and creation
- Backward compatibility with old paths
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# --- Configuration Directory Paths ---
CONFIG_BASE_DIR = '/etc/starlight'
CONFIG_DIR = os.path.join(CONFIG_BASE_DIR, 'config')
DATA_DIR = os.path.join(CONFIG_BASE_DIR, 'data')
PREFERENCES_DIR = os.path.join(CONFIG_BASE_DIR, 'preferences')
ROLLBACK_DIR = os.path.join(CONFIG_BASE_DIR, 'rollback_data')

# --- Configuration File Paths (New Centralized Structure) ---
SYSTEM_CONFIG_PATH = os.path.join(CONFIG_DIR, 'system.json')
STORAGE_CONFIG_PATH = os.path.join(CONFIG_DIR, 'storage.json')
REPOSITORIES_CONFIG_PATH = os.path.join(CONFIG_DIR, 'repositories.json')
AUTH_CONFIG_PATH = os.path.join(CONFIG_DIR, 'auth.json')
UPDATE_CONFIG_PATH = os.path.join(CONFIG_DIR, 'update.json')
NETWORK_CONFIG_PATH = os.path.join(CONFIG_DIR, 'network.json')
UPDATER_CONFIG_PATH = os.path.join(CONFIG_DIR, 'updater.json')

# --- Data File Paths ---
VM_METADATA_PATH = os.path.join(DATA_DIR, 'vm_metadata.json')
LXC_METADATA_PATH = os.path.join(DATA_DIR, 'lxc_metadata.json')
USERS_METADATA_PATH = os.path.join(DATA_DIR, 'users.json')
API_KEYS_PATH = os.path.join(DATA_DIR, 'api_keys.json')

# --- Legacy Configuration Paths (for backward compatibility) ---
LEGACY_STORAGE_PATH = os.path.join(CONFIG_BASE_DIR, 'storage.json')
LEGACY_REPOSITORIES_PATH = os.path.join(CONFIG_BASE_DIR, 'repositories.json')
LEGACY_AUTH_PATH = os.path.join(CONFIG_BASE_DIR, 'auth.json')
LEGACY_UPDATE_PATH = os.path.join(CONFIG_BASE_DIR, 'update_config.json')
LEGACY_VM_METADATA_PATH = os.path.join(CONFIG_BASE_DIR, 'vm_metadata.json')
LEGACY_LXC_METADATA_PATH = os.path.join(CONFIG_BASE_DIR, 'lxc_metadata.json')
LEGACY_USERS_PATH = os.path.join(CONFIG_BASE_DIR, 'users.json')
LEGACY_API_KEYS_PATH = os.path.join(CONFIG_BASE_DIR, 'api_keys.json')

# --- Other Static Paths ---
VERSION_FILE_PATH = os.path.join(CONFIG_BASE_DIR, 'version.json')

# --- Default Configurations ---
DEFAULT_SYSTEM_CONFIG = {
    'network_mode': 'bridge',
    'bridge_name': 'br0',
    'nat_network_name': 'default',
    'service_name': 'starlight-backend'
}

DEFAULT_STORAGE_CONFIG = {
    'vm_storage_path': '/var/lib/libvirt/images',
    'iso_storage_path': '/var/lib/libvirt/isos',
    'default_pool_name': 'default'
}

DEFAULT_AUTH_CONFIG = {
    'jwt_secret': None,  # Will be auto-generated
    'jwt_algorithm': 'HS256',
    'session_timeout_hours': 24,
    'refresh_token_days': 30
}

DEFAULT_UPDATE_CONFIG = {
    'auto_update_enabled': False,
    'check_interval_hours': 24,
    'last_check': None
}

DEFAULT_NETWORK_CONFIG = {
    'mode': 'dhcp',  # 'dhcp' or 'static'
    'hostname': '',
    'ip_address': '',
    'netmask': '255.255.255.0',
    'gateway': '',
    'dns_primary': '8.8.8.8',
    'dns_secondary': '1.1.1.1'
}

# Default updater configuration
DEFAULT_UPDATER_CONFIG = {
    'repository_url': 'https://github.com/WillProvince/Starlight-Hidden.git',
    'branch': 'main',
    'auto_sync_files': True,
    'auto_update_packages': True,
    'run_update_scripts': True
}

# --- Configuration Cache ---
_config_cache: Dict[str, Any] = {}


def ensure_config_directories() -> bool:
    """
    Ensure all configuration directories exist with proper permissions.
    
    Returns:
        bool: True if all directories were created/exist successfully
    """
    directories = [CONFIG_DIR, DATA_DIR, PREFERENCES_DIR, ROLLBACK_DIR]
    
    try:
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            os.chmod(directory, 0o755)
        return True
    except Exception as e:
        logger.error(f"Failed to create configuration directories: {e}")
        return False


def _get_config_with_fallback(new_path: str, legacy_path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    """
    Load configuration from new path, falling back to legacy path if not found.
    
    Args:
        new_path: The new centralized configuration path
        legacy_path: The legacy configuration path
        default: Default configuration values
        
    Returns:
        dict: The loaded configuration merged with defaults
    """
    config = default.copy()
    
    # Try new path first
    if os.path.exists(new_path):
        try:
            with open(new_path, 'r') as f:
                loaded = json.load(f)
                config.update(loaded)
                return config
        except Exception as e:
            logger.warning(f"Error loading config from {new_path}: {e}")
    
    # Fall back to legacy path
    if os.path.exists(legacy_path):
        try:
            with open(legacy_path, 'r') as f:
                loaded = json.load(f)
                config.update(loaded)
                logger.info(f"Loaded config from legacy path: {legacy_path}")
                return config
        except Exception as e:
            logger.warning(f"Error loading config from legacy path {legacy_path}: {e}")
    
    return config


def _save_config(path: str, config: Dict[str, Any], permissions: int = 0o644) -> bool:
    """
    Save configuration to a JSON file.
    
    Args:
        path: Path to save the configuration
        config: Configuration dictionary to save
        permissions: File permissions (default 0o644)
        
    Returns:
        bool: True if saved successfully
    """
    try:
        # Ensure directory exists
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
        
        os.chmod(path, permissions)
        return True
    except Exception as e:
        logger.error(f"Failed to save config to {path}: {e}")
        return False


def get_storage_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Get storage configuration.
    
    Args:
        force_reload: If True, bypass cache and reload from disk
        
    Returns:
        dict: Storage configuration with keys:
            - vm_storage_path: Path to VM disk images
            - iso_storage_path: Path to ISO images
            - default_pool_name: Default libvirt storage pool name
    """
    cache_key = 'storage'
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    config = _get_config_with_fallback(
        STORAGE_CONFIG_PATH,
        LEGACY_STORAGE_PATH,
        DEFAULT_STORAGE_CONFIG
    )
    
    # Ensure paths exist
    for path_key in ['vm_storage_path', 'iso_storage_path']:
        path = config.get(path_key)
        if path:
            try:
                Path(path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"Could not create storage path {path}: {e}")
    
    _config_cache[cache_key] = config
    return config


def save_storage_config(config: Dict[str, Any]) -> bool:
    """
    Save storage configuration.
    
    Args:
        config: Storage configuration dictionary
        
    Returns:
        bool: True if saved successfully
    """
    # Merge with defaults to ensure all keys are present
    full_config = DEFAULT_STORAGE_CONFIG.copy()
    full_config.update(config)
    
    if _save_config(STORAGE_CONFIG_PATH, full_config):
        _config_cache['storage'] = full_config
        return True
    return False


def get_system_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Get system configuration (network, service settings).
    
    Args:
        force_reload: If True, bypass cache and reload from disk
        
    Returns:
        dict: System configuration with keys:
            - network_mode: 'bridge' or 'nat'
            - bridge_name: Bridge device name
            - nat_network_name: NAT network name
            - service_name: Systemd service name
    """
    cache_key = 'system'
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    config = _get_config_with_fallback(
        SYSTEM_CONFIG_PATH,
        '',  # No legacy path for system config
        DEFAULT_SYSTEM_CONFIG
    )
    
    _config_cache[cache_key] = config
    return config


def save_system_config(config: Dict[str, Any]) -> bool:
    """
    Save system configuration.
    
    Args:
        config: System configuration dictionary
        
    Returns:
        bool: True if saved successfully
    """
    full_config = DEFAULT_SYSTEM_CONFIG.copy()
    full_config.update(config)
    
    if _save_config(SYSTEM_CONFIG_PATH, full_config):
        _config_cache['system'] = full_config
        return True
    return False


def get_auth_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Get authentication configuration.
    
    Args:
        force_reload: If True, bypass cache and reload from disk
        
    Returns:
        dict: Authentication configuration
    """
    cache_key = 'auth'
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    config = _get_config_with_fallback(
        AUTH_CONFIG_PATH,
        LEGACY_AUTH_PATH,
        DEFAULT_AUTH_CONFIG
    )
    
    _config_cache[cache_key] = config
    return config


def save_auth_config(config: Dict[str, Any]) -> bool:
    """
    Save authentication configuration.
    
    Args:
        config: Authentication configuration dictionary
        
    Returns:
        bool: True if saved successfully
    """
    full_config = DEFAULT_AUTH_CONFIG.copy()
    full_config.update(config)
    
    # Use more restrictive permissions for auth config
    if _save_config(AUTH_CONFIG_PATH, full_config, permissions=0o600):
        _config_cache['auth'] = full_config
        return True
    return False


def get_update_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Get update configuration.
    
    Args:
        force_reload: If True, bypass cache and reload from disk
        
    Returns:
        dict: Update configuration
    """
    cache_key = 'update'
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    config = _get_config_with_fallback(
        UPDATE_CONFIG_PATH,
        LEGACY_UPDATE_PATH,
        DEFAULT_UPDATE_CONFIG
    )
    
    _config_cache[cache_key] = config
    return config


def save_update_config(config: Dict[str, Any]) -> bool:
    """
    Save update configuration.
    
    Args:
        config: Update configuration dictionary
        
    Returns:
        bool: True if saved successfully
    """
    full_config = DEFAULT_UPDATE_CONFIG.copy()
    full_config.update(config)
    
    if _save_config(UPDATE_CONFIG_PATH, full_config):
        _config_cache['update'] = full_config
        return True
    return False


def get_network_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Get network configuration.
    
    Args:
        force_reload: If True, bypass cache and reload from disk
        
    Returns:
        dict: Network configuration with keys:
            - mode: 'dhcp' or 'static'
            - hostname: System hostname
            - ip_address: Static IP address (for static mode)
            - netmask: Network mask
            - gateway: Default gateway
            - dns_primary: Primary DNS server
            - dns_secondary: Secondary DNS server
    """
    cache_key = 'network'
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    config = _get_config_with_fallback(
        NETWORK_CONFIG_PATH,
        '',  # No legacy path for network config
        DEFAULT_NETWORK_CONFIG
    )
    
    _config_cache[cache_key] = config
    return config


def save_network_config(config: Dict[str, Any]) -> bool:
    """
    Save network configuration.
    
    Args:
        config: Network configuration dictionary
        
    Returns:
        bool: True if saved successfully
    """
    full_config = DEFAULT_NETWORK_CONFIG.copy()
    full_config.update(config)
    
    if _save_config(NETWORK_CONFIG_PATH, full_config):
        _config_cache['network'] = full_config
        return True
    return False


def get_updater_config(force_reload: bool = False) -> Dict[str, Any]:
    """
    Get updater configuration.
    
    Args:
        force_reload: If True, bypass cache and reload from disk
        
    Returns:
        dict: Updater configuration with keys:
            - repository_url: Git repository URL
            - branch: Git branch to use
            - auto_sync_files: Whether to sync files after update
            - auto_update_packages: Whether to run apt update/upgrade
            - run_update_scripts: Whether to run update scripts
    """
    cache_key = 'updater'
    
    if not force_reload and cache_key in _config_cache:
        return _config_cache[cache_key]
    
    config = _get_config_with_fallback(
        UPDATER_CONFIG_PATH,
        '',  # No legacy path for updater config
        DEFAULT_UPDATER_CONFIG
    )
    
    _config_cache[cache_key] = config
    return config


def save_updater_config(config: Dict[str, Any]) -> bool:
    """
    Save updater configuration.
    
    Args:
        config: Updater configuration dictionary
        
    Returns:
        bool: True if saved successfully
    """
    full_config = DEFAULT_UPDATER_CONFIG.copy()
    full_config.update(config)
    
    if _save_config(UPDATER_CONFIG_PATH, full_config):
        _config_cache['updater'] = full_config
        return True
    return False


def get_config_file_path(config_type: str, use_legacy: bool = False) -> str:
    """
    Get the file path for a specific configuration type.
    
    Args:
        config_type: Type of configuration ('storage', 'system', 'auth', 'update',
                     'repositories', 'vm_metadata', 'lxc_metadata', 'users', 'api_keys',
                     'network', 'updater')
        use_legacy: If True, return the legacy path
        
    Returns:
        str: The configuration file path
    """
    paths = {
        'storage': (STORAGE_CONFIG_PATH, LEGACY_STORAGE_PATH),
        'system': (SYSTEM_CONFIG_PATH, ''),
        'auth': (AUTH_CONFIG_PATH, LEGACY_AUTH_PATH),
        'update': (UPDATE_CONFIG_PATH, LEGACY_UPDATE_PATH),
        'repositories': (REPOSITORIES_CONFIG_PATH, LEGACY_REPOSITORIES_PATH),
        'vm_metadata': (VM_METADATA_PATH, LEGACY_VM_METADATA_PATH),
        'lxc_metadata': (LXC_METADATA_PATH, LEGACY_LXC_METADATA_PATH),
        'users': (USERS_METADATA_PATH, LEGACY_USERS_PATH),
        'api_keys': (API_KEYS_PATH, LEGACY_API_KEYS_PATH),
        'network': (NETWORK_CONFIG_PATH, ''),
        'updater': (UPDATER_CONFIG_PATH, ''),
    }
    
    if config_type in paths:
        new_path, legacy_path = paths[config_type]
        return legacy_path if use_legacy else new_path
    
    raise ValueError(f"Unknown config type: {config_type}")


def clear_cache(config_type: Optional[str] = None):
    """
    Clear the configuration cache.
    
    Args:
        config_type: Specific configuration type to clear, or None to clear all
    """
    global _config_cache
    
    if config_type:
        _config_cache.pop(config_type, None)
    else:
        _config_cache = {}


def needs_migration() -> bool:
    """
    Check if configuration migration is needed.
    
    Returns:
        bool: True if legacy configs exist but new structure doesn't
    """
    # If new config directory exists with content, no migration needed
    if os.path.exists(CONFIG_DIR) and os.listdir(CONFIG_DIR):
        return False
    
    # Check if any legacy configs exist
    legacy_paths = [
        LEGACY_STORAGE_PATH,
        LEGACY_REPOSITORIES_PATH,
        LEGACY_AUTH_PATH,
        LEGACY_UPDATE_PATH,
    ]
    
    return any(os.path.exists(p) for p in legacy_paths)


# --- Convenience functions for getting specific values ---

def get_vm_storage_path() -> str:
    """Get the VM storage path."""
    return get_storage_config()['vm_storage_path']


def get_iso_storage_path() -> str:
    """Get the ISO storage path."""
    return get_storage_config()['iso_storage_path']


def get_default_pool_name() -> str:
    """Get the default storage pool name."""
    return get_storage_config()['default_pool_name']


def get_network_mode() -> str:
    """Get the network mode (bridge or nat)."""
    return get_system_config()['network_mode']


def get_bridge_name() -> str:
    """Get the bridge name."""
    return get_system_config()['bridge_name']


def get_nat_network_name() -> str:
    """Get the NAT network name."""
    return get_system_config()['nat_network_name']


def get_service_name() -> str:
    """Get the systemd service name."""
    return get_system_config()['service_name']
