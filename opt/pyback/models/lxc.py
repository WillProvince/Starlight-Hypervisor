"""
LXC container data models and metadata management.

This module provides functions for managing LXC container metadata.
"""

import os
import json
import logging
from pathlib import Path
from ..config_loader import LXC_METADATA_PATH, get_config_file_path

logger = logging.getLogger(__name__)


def _get_lxc_metadata_path():
    """Get the LXC metadata path with fallback to legacy."""
    new_path = LXC_METADATA_PATH
    legacy_path = get_config_file_path('lxc_metadata', use_legacy=True)
    
    # Return new path if it exists, otherwise check legacy
    if Path(new_path).exists():
        return new_path
    if Path(legacy_path).exists():
        return legacy_path
    # Default to new path for new installations
    return new_path


def load_lxc_metadata():
    """Loads LXC metadata from JSON file.
    
    Returns:
        dict: LXC metadata dictionary
    """
    try:
        metadata_path = _get_lxc_metadata_path()
        if not os.path.exists(metadata_path):
            return {}
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading LXC metadata: {e}")
        return {}


def save_lxc_metadata(metadata):
    """Saves LXC metadata to JSON file.
    
    Args:
        metadata: LXC metadata dictionary to save
        
    Returns:
        bool: True if save succeeded, False otherwise
    """
    try:
        # Always save to new location
        os.makedirs(os.path.dirname(LXC_METADATA_PATH), exist_ok=True)
        with open(LXC_METADATA_PATH, 'w') as f:
            json.dump(metadata, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving LXC metadata: {e}")
        return False


def get_lxc_metadata(container_name):
    """Gets metadata for a specific LXC container.
    
    Args:
        container_name: name of the container
        
    Returns:
        dict: LXC metadata or empty dict if not found
    """
    metadata = load_lxc_metadata()
    return metadata.get(container_name, {})


def set_lxc_metadata(container_name, data):
    """Sets metadata for a specific LXC container.
    
    Args:
        container_name: name of the container
        data: metadata dictionary to set/update
    """
    metadata = load_lxc_metadata()
    if container_name not in metadata:
        metadata[container_name] = {}
    metadata[container_name].update(data)
    # Store type in metadata
    metadata[container_name]['type'] = 'lxc'
    save_lxc_metadata(metadata)
