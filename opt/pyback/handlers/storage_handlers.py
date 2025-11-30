"""
Storage management API handlers.

This module provides HTTP request handlers for managing storage configuration
including getting/setting storage paths and retrieving storage usage information.
"""

import os
import json
import logging
from aiohttp import web
from pathlib import Path

from ..config_loader import (
    get_storage_config,
    save_storage_config,
    get_vm_storage_path,
    get_iso_storage_path,
    STORAGE_CONFIG_PATH,
)
from ..auth.user_management import is_admin

logger = logging.getLogger(__name__)


def get_path_info(path: str) -> dict:
    """
    Get information about a storage path.
    
    Args:
        path: The path to check
        
    Returns:
        dict: Path information including existence, size, and permissions
    """
    info = {
        'path': path,
        'exists': False,
        'writable': False,
        'total_bytes': 0,
        'used_bytes': 0,
        'available_bytes': 0,
    }
    
    try:
        if os.path.exists(path):
            info['exists'] = True
            info['writable'] = os.access(path, os.W_OK)
            
            # Get disk space statistics
            statvfs = os.statvfs(path)
            info['total_bytes'] = statvfs.f_frsize * statvfs.f_blocks
            info['available_bytes'] = statvfs.f_frsize * statvfs.f_bavail
            info['used_bytes'] = info['total_bytes'] - (statvfs.f_frsize * statvfs.f_bfree)
    except Exception as e:
        logger.warning(f"Error getting path info for {path}: {e}")
    
    return info


async def get_storage_config_handler(request: web.Request) -> web.Response:
    """
    Get current storage configuration.
    
    GET /api/storage/config
    
    Returns:
        JSON response with storage configuration
    """
    try:
        config = get_storage_config(force_reload=True)
        
        return web.json_response({
            'status': 'success',
            'config': {
                'vm_storage_path': config.get('vm_storage_path', '/var/lib/libvirt/images'),
                'iso_storage_path': config.get('iso_storage_path', '/var/lib/libvirt/isos'),
                'default_pool_name': config.get('default_pool_name', 'default'),
            }
        })
    except Exception as e:
        logger.error(f"Error getting storage config: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'Failed to retrieve storage configuration'
        }, status=500)


async def update_storage_config_handler(request: web.Request) -> web.Response:
    """
    Update storage configuration (admin only).
    
    POST /api/storage/config
    
    Body:
        {
            "vm_storage_path": "/path/to/vm/storage",
            "iso_storage_path": "/path/to/iso/storage",
            "default_pool_name": "default"
        }
    
    Returns:
        JSON response with updated configuration
    """
    # Check admin permissions
    user_info = request.get('user_info', {})
    username = user_info.get('username', '')
    
    if not is_admin(username) and username != 'root':
        return web.json_response({
            'status': 'error',
            'message': 'Admin privileges required to modify storage configuration'
        }, status=403)
    
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({
            'status': 'error',
            'message': 'Invalid JSON body'
        }, status=400)
    
    # Get current config
    current_config = get_storage_config(force_reload=True)
    
    # Validate and update paths
    errors = []
    warnings = []
    
    for path_key in ['vm_storage_path', 'iso_storage_path']:
        if path_key in data:
            new_path = data[path_key].strip()
            
            # Validate path
            if not new_path.startswith('/'):
                errors.append(f"{path_key} must be an absolute path")
                continue
            
            # Check if path exists or can be created
            try:
                Path(new_path).mkdir(parents=True, exist_ok=True)
                
                # Test write access using try-finally to ensure cleanup
                test_file = os.path.join(new_path, '.starlight-test')
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                finally:
                    try:
                        if os.path.exists(test_file):
                            os.remove(test_file)
                    except Exception:
                        pass  # Ignore cleanup errors
                
                current_config[path_key] = new_path
                logger.info(f"Updated {path_key} to: {new_path}")
                
            except PermissionError:
                errors.append(f"Permission denied: cannot write to {new_path}")
            except Exception as e:
                errors.append(f"Cannot use {new_path}: {str(e)}")
    
    # Update pool name if provided
    if 'default_pool_name' in data:
        current_config['default_pool_name'] = data['default_pool_name'].strip()
    
    # Return errors if any
    if errors:
        return web.json_response({
            'status': 'error',
            'message': 'Validation failed',
            'errors': errors
        }, status=400)
    
    # Save configuration
    if not save_storage_config(current_config):
        return web.json_response({
            'status': 'error',
            'message': 'Failed to save storage configuration'
        }, status=500)
    
    response = {
        'status': 'success',
        'message': 'Storage configuration updated successfully',
        'config': current_config
    }
    
    if warnings:
        response['warnings'] = warnings
    
    return web.json_response(response)


async def get_storage_info_handler(request: web.Request) -> web.Response:
    """
    Get disk space and usage statistics for storage paths.
    
    GET /api/storage/info
    
    Returns:
        JSON response with storage information for VM and ISO paths
    """
    try:
        config = get_storage_config(force_reload=True)
        
        vm_path = config.get('vm_storage_path', '/var/lib/libvirt/images')
        iso_path = config.get('iso_storage_path', '/var/lib/libvirt/isos')
        
        vm_info = get_path_info(vm_path)
        iso_info = get_path_info(iso_path)
        
        # Count files in each directory
        vm_file_count = 0
        vm_total_size = 0
        iso_file_count = 0
        iso_total_size = 0
        
        if vm_info['exists']:
            try:
                for entry in os.scandir(vm_path):
                    if entry.is_file():
                        vm_file_count += 1
                        vm_total_size += entry.stat().st_size
            except Exception as e:
                logger.warning(f"Error scanning VM storage: {e}")
        
        if iso_info['exists']:
            try:
                for entry in os.scandir(iso_path):
                    if entry.is_file():
                        iso_file_count += 1
                        iso_total_size += entry.stat().st_size
            except Exception as e:
                logger.warning(f"Error scanning ISO storage: {e}")
        
        vm_info['file_count'] = vm_file_count
        vm_info['content_size_bytes'] = vm_total_size
        iso_info['file_count'] = iso_file_count
        iso_info['content_size_bytes'] = iso_total_size
        
        return web.json_response({
            'status': 'success',
            'info': {
                'vm_storage': vm_info,
                'iso_storage': iso_info
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting storage info: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'Failed to retrieve storage information'
        }, status=500)


async def validate_storage_path_handler(request: web.Request) -> web.Response:
    """
    Validate a storage path without saving it.
    
    POST /api/storage/validate
    
    Body:
        {
            "path": "/path/to/validate"
        }
    
    Returns:
        JSON response with validation results
    """
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({
            'status': 'error',
            'message': 'Invalid JSON body'
        }, status=400)
    
    path = data.get('path', '').strip()
    
    if not path:
        return web.json_response({
            'status': 'error',
            'message': 'Path is required'
        }, status=400)
    
    if not path.startswith('/'):
        return web.json_response({
            'status': 'error',
            'message': 'Path must be an absolute path',
            'valid': False
        })
    
    validation = {
        'path': path,
        'valid': False,
        'exists': os.path.exists(path),
        'writable': False,
        'can_create': False,
        'issues': []
    }
    
    if validation['exists']:
        if os.path.isdir(path):
            validation['writable'] = os.access(path, os.W_OK)
            if not validation['writable']:
                validation['issues'].append('Directory exists but is not writable')
            else:
                validation['valid'] = True
        else:
            validation['issues'].append('Path exists but is not a directory')
    else:
        # Check if we can create it
        try:
            parent = os.path.dirname(path)
            if os.path.exists(parent) and os.access(parent, os.W_OK):
                validation['can_create'] = True
                validation['valid'] = True
            else:
                validation['issues'].append('Parent directory does not exist or is not writable')
        except Exception as e:
            validation['issues'].append(f'Cannot determine path validity: {str(e)}')
    
    # Add disk space info if path or parent exists
    check_path = path if validation['exists'] else os.path.dirname(path)
    if os.path.exists(check_path):
        try:
            statvfs = os.statvfs(check_path)
            validation['available_bytes'] = statvfs.f_frsize * statvfs.f_bavail
            validation['total_bytes'] = statvfs.f_frsize * statvfs.f_blocks
        except Exception:
            pass
    
    return web.json_response({
        'status': 'success',
        'validation': validation
    })
