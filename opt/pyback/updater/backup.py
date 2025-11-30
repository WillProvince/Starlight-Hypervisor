"""
Backup and update configuration management.

This module provides functions for managing backup creation and
update configuration persistence.
"""

import os
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from ..config_loader import (
    UPDATE_CONFIG_PATH as CONFIG_UPDATE_PATH,
    ROLLBACK_DIR as BACKUP_DIR,
    get_config_file_path
)
from ..config import GIT_REPO_PATH

logger = logging.getLogger(__name__)


def _get_update_config_path():
    """Get the update config path with fallback to legacy."""
    new_path = CONFIG_UPDATE_PATH
    legacy_path = get_config_file_path('update', use_legacy=True)
    
    # Return new path if it exists, otherwise check legacy
    if Path(new_path).exists():
        return new_path
    if Path(legacy_path).exists():
        return legacy_path
    # Default to new path for new installations
    return new_path


def load_update_config():
    """Loads update configuration from JSON file."""
    try:
        update_config_path = _get_update_config_path()
        if not os.path.exists(update_config_path):
            # Default configuration
            return {
                'auto_update_enabled': False,
                'update_channel': 'main',
                'last_check': None,
                'last_update': None
            }
        with open(update_config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading update config: {e}")
        return {
            'auto_update_enabled': False,
            'update_channel': 'main',
            'last_check': None,
            'last_update': None
        }


def save_update_config(config):
    """Saves update configuration to JSON file."""
    try:
        # Always save to new location
        os.makedirs(os.path.dirname(CONFIG_UPDATE_PATH), exist_ok=True)
        with open(CONFIG_UPDATE_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving update config: {e}")
        return False


def create_backup():
    """Creates a backup of the current installation."""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(BACKUP_DIR, f'backup_{timestamp}')
        
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Get current commit hash
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=GIT_REPO_PATH,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        commit_hash = result.stdout.strip() if result.returncode == 0 else 'unknown'
        
        # Save backup metadata
        backup_info = {
            'timestamp': timestamp,
            'commit': commit_hash,
            'path': backup_path
        }
        
        backup_info_path = os.path.join(BACKUP_DIR, f'backup_{timestamp}.json')
        with open(backup_info_path, 'w') as f:
            json.dump(backup_info, f, indent=2)
        
        logger.info(f"Created backup metadata at {backup_info_path}")
        
        return backup_info
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return None
