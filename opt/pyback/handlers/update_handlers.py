"""
System update API handlers.

This module provides HTTP request handlers for system update operations.
"""

import os
import json
import logging
from datetime import datetime
from aiohttp import web

from ..config_loader import ROLLBACK_DIR as BACKUP_DIR
from ..updater.backup import load_update_config, save_update_config
from ..updater.system import (
    get_current_version,
    check_for_updates,
    perform_update,
    schedule_service_restart,
    rollback_update
)

logger = logging.getLogger(__name__)


async def get_update_status(request):
    """Returns the current update status and configuration."""
    try:
        config = load_update_config()
        current_version = get_current_version()
        
        # Update last check timestamp
        config['last_check'] = datetime.now().isoformat()
        save_update_config(config)
        
        return web.json_response({
            'status': 'success',
            'current_version': current_version,
            'config': config
        })
    except Exception as e:
        logger.error(f"Error getting update status: {e}")
        return web.json_response({
            'status': 'error',
            'message': str(e)
        }, status=500)


async def check_updates(request):
    """Checks for available updates."""
    try:
        update_info = check_for_updates()
        
        if update_info is None:
            return web.json_response({
                'status': 'error',
                'message': 'Failed to check for updates'
            }, status=500)
        
        # Update last check timestamp
        config = load_update_config()
        config['last_check'] = datetime.now().isoformat()
        save_update_config(config)
        
        return web.json_response({
            'status': 'success',
            'update_info': update_info
        })
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return web.json_response({
            'status': 'error',
            'message': str(e)
        }, status=500)


async def trigger_update(request):
    """Triggers the update process."""
    try:
        # Perform the update
        result = perform_update()
        
        if result['success']:
            # If update was successful and restart is required, schedule restart
            if result.get('restart_required'):
                schedule_service_restart()
            
            return web.json_response({
                'status': 'success',
                'message': result['message'],
                'restart_required': result.get('restart_required', False)
            })
        else:
            return web.json_response({
                'status': 'error',
                'message': result.get('error', 'Update failed'),
                'rollback_attempted': result.get('rollback_attempted', False),
                'rollback_success': result.get('rollback_success', False)
            }, status=500)
    except Exception as e:
        logger.error(f"Error triggering update: {e}")
        return web.json_response({
            'status': 'error',
            'message': str(e)
        }, status=500)


async def update_auto_update_config(request):
    """Updates the auto-update configuration."""
    try:
        data = await request.json()
        
        config = load_update_config()
        
        if 'auto_update_enabled' in data:
            config['auto_update_enabled'] = bool(data['auto_update_enabled'])
        
        if 'update_channel' in data:
            config['update_channel'] = data['update_channel']
        
        if save_update_config(config):
            return web.json_response({
                'status': 'success',
                'message': 'Configuration updated successfully',
                'config': config
            })
        else:
            return web.json_response({
                'status': 'error',
                'message': 'Failed to save configuration'
            }, status=500)
    except Exception as e:
        logger.error(f"Error updating auto-update config: {e}")
        return web.json_response({
            'status': 'error',
            'message': str(e)
        }, status=500)


async def get_update_history(request):
    """Returns the update history from backups."""
    try:
        if not os.path.exists(BACKUP_DIR):
            return web.json_response({
                'status': 'success',
                'backups': []
            })
        
        backups = []
        for filename in os.listdir(BACKUP_DIR):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(BACKUP_DIR, filename), 'r') as f:
                        backup_info = json.load(f)
                        backups.append(backup_info)
                except Exception as e:
                    logger.error(f"Error reading backup file {filename}: {e}")
        
        # Sort by timestamp, newest first
        backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return web.json_response({
            'status': 'success',
            'backups': backups
        })
    except Exception as e:
        logger.error(f"Error getting update history: {e}")
        return web.json_response({
            'status': 'error',
            'message': str(e)
        }, status=500)


async def perform_rollback(request):
    """Performs a rollback to a previous version."""
    try:
        data = await request.json()
        commit_hash = data.get('commit')
        
        if not commit_hash:
            return web.json_response({
                'status': 'error',
                'message': 'Commit hash is required'
            }, status=400)
        
        result = rollback_update(commit_hash)
        
        if result['success']:
            # Schedule service restart
            schedule_service_restart()
            
            return web.json_response({
                'status': 'success',
                'message': result['message'],
                'restart_required': True
            })
        else:
            return web.json_response({
                'status': 'error',
                'message': result.get('error', 'Rollback failed')
            }, status=500)
    except Exception as e:
        logger.error(f"Error performing rollback: {e}")
        return web.json_response({
            'status': 'error',
            'message': str(e)
        }, status=500)
