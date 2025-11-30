"""
First-Run Wizard HTTP Handlers

Handles HTTP requests for the first-run setup wizard.
These endpoints are only accessible when the .needs-firstrun flag exists.
"""

import os
import logging
import subprocess
import socket
import json
from aiohttp import web

from pyback.auth.user_management import create_user, change_password
from pyback.auth.pam_auth import user_exists
from pyback.config_loader import (
    CONFIG_BASE_DIR,
    STORAGE_CONFIG_PATH,
    save_storage_config,
    get_vm_storage_path,
    ensure_config_directories,
)

logger = logging.getLogger(__name__)

# Configuration paths
STARLIGHT_CONFIG_DIR = CONFIG_BASE_DIR
FIRSTRUN_FLAG = os.path.join(STARLIGHT_CONFIG_DIR, '.needs-firstrun')
FIRSTRUN_COMPLETE_FLAG = os.path.join(STARLIGHT_CONFIG_DIR, '.firstrun-complete')
STORAGE_CONFIG_FILE = STORAGE_CONFIG_PATH


def needs_firstrun() -> bool:
    """Check if first-run wizard is still needed."""
    return os.path.exists(FIRSTRUN_FLAG) and not os.path.exists(FIRSTRUN_COMPLETE_FLAG)


def require_firstrun(handler):
    """Decorator to ensure endpoint is only accessible during first-run."""
    async def wrapper(request: web.Request) -> web.Response:
        if not needs_firstrun():
            return web.json_response(
                {'status': 'error', 'message': 'First-run wizard already completed'},
                status=403
            )
        return await handler(request)
    return wrapper


async def firstrun_status(request: web.Request) -> web.Response:
    """
    Check if first-run wizard is needed.
    
    GET /api/firstrun/status
    """
    return web.json_response({
        'status': 'success',
        'needs_firstrun': needs_firstrun()
    })


@require_firstrun
async def get_system_info(request: web.Request) -> web.Response:
    """
    Get system information for the wizard.
    
    GET /api/firstrun/system-info
    """
    try:
        # Get hostname
        hostname = socket.gethostname()
        
        # Get primary IP address
        ip_address = None
        interface = None
        try:
            # Try to get the IP address that would be used to reach the internet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip_address = s.getsockname()[0]
            s.close()
        except Exception:
            # Fallback: get any non-localhost IP
            try:
                result = subprocess.run(
                    ['ip', '-4', 'route', 'get', '1'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    parts = result.stdout.split()
                    if 'src' in parts:
                        ip_address = parts[parts.index('src') + 1]
                    if 'dev' in parts:
                        interface = parts[parts.index('dev') + 1]
            except Exception:
                pass
        
        # Get available disk space
        available_space = 'Unknown'
        try:
            statvfs = os.statvfs('/var/lib/libvirt/images')
            available_bytes = statvfs.f_frsize * statvfs.f_bavail
            available_gb = available_bytes / (1024 ** 3)
            available_space = f'{available_gb:.1f} GB'
        except Exception:
            try:
                statvfs = os.statvfs('/')
                available_bytes = statvfs.f_frsize * statvfs.f_bavail
                available_gb = available_bytes / (1024 ** 3)
                available_space = f'{available_gb:.1f} GB'
            except Exception:
                pass
        
        return web.json_response({
            'status': 'success',
            'hostname': hostname,
            'ip_address': ip_address or 'Unknown',
            'interface': interface or 'Unknown',
            'available_space': available_space
        })
    
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'Failed to get system information'
        }, status=500)


@require_firstrun
async def set_root_password(request: web.Request) -> web.Response:
    """
    Change the root password.
    
    POST /api/firstrun/set-root-password
    Body: {"password": "new_password"}
    """
    try:
        data = await request.json()
        password = data.get('password', '')
        
        if not password:
            return web.json_response({
                'status': 'error',
                'message': 'Password is required'
            }, status=400)
        
        if len(password) < 8:
            return web.json_response({
                'status': 'error',
                'message': 'Password must be at least 8 characters'
            }, status=400)
        
        # Change root password using chpasswd
        # Password is passed via stdin to avoid exposure in process lists or logs
        try:
            result = subprocess.run(
                ['/usr/sbin/chpasswd'],
                input=f'root:{password}\n',
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"chpasswd failed: {result.stderr}")
                raise Exception('chpasswd failed')
            
            # Log success without exposing the password
            logger.info("Root password changed successfully via first-run wizard")
            
            return web.json_response({
                'status': 'success',
                'message': 'Root password changed successfully'
            })
        
        except Exception as e:
            logger.error(f"Failed to change root password: {e}")
            return web.json_response({
                'status': 'error',
                'message': 'Failed to change root password'
            }, status=500)
    
    except Exception as e:
        logger.error(f"Error in set_root_password: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'An error occurred'
        }, status=500)


@require_firstrun
async def create_admin_user(request: web.Request) -> web.Response:
    """
    Create an admin user for Starlight.
    
    POST /api/firstrun/create-admin
    Body: {"username": "admin", "password": "password"}
    """
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return web.json_response({
                'status': 'error',
                'message': 'Username and password are required'
            }, status=400)
        
        # Validate username
        import re
        if not re.match(r'^[a-z_][a-z0-9_-]*$', username):
            return web.json_response({
                'status': 'error',
                'message': 'Invalid username format'
            }, status=400)
        
        if username == 'root':
            return web.json_response({
                'status': 'error',
                'message': 'Cannot use root as username'
            }, status=400)
        
        if len(password) < 8:
            return web.json_response({
                'status': 'error',
                'message': 'Password must be at least 8 characters'
            }, status=400)
        
        # Check if user already exists
        if user_exists(username):
            # User exists, just change password and ensure in starlight-users group
            result = change_password(username, password)
            if result['status'] != 'success':
                return web.json_response({
                    'status': 'error',
                    'message': 'Failed to update existing user password'
                }, status=500)
            
            # Ensure user is in starlight-users group
            subprocess.run(['usermod', '-aG', 'starlight-users', username], check=False)
            
            return web.json_response({
                'status': 'success',
                'message': f'User {username} updated successfully'
            })
        
        # Create new user
        result = create_user(username, password, role='admin', full_name='')
        
        if result['status'] == 'success':
            logger.info(f"Admin user {username} created via first-run wizard")
            return web.json_response({
                'status': 'success',
                'message': f'User {username} created successfully'
            })
        else:
            return web.json_response({
                'status': 'error',
                'message': result.get('message', 'Failed to create user')
            }, status=400)
    
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'Failed to create admin user'
        }, status=500)


@require_firstrun
async def set_hostname(request: web.Request) -> web.Response:
    """
    Set the system hostname.
    
    POST /api/firstrun/set-hostname
    Body: {"hostname": "starlight"}
    """
    try:
        data = await request.json()
        hostname = data.get('hostname', '').strip()
        
        if not hostname:
            return web.json_response({
                'status': 'skipped',
                'message': 'No hostname provided, skipping'
            })
        
        # Validate hostname
        import re
        if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$', hostname):
            return web.json_response({
                'status': 'error',
                'message': 'Invalid hostname format'
            }, status=400)
        
        try:
            # Set hostname using hostnamectl
            subprocess.run(['hostnamectl', 'set-hostname', hostname], check=True)
            
            # Update /etc/hosts
            with open('/etc/hosts', 'r') as f:
                hosts_content = f.read()
            
            # Add entry for new hostname if not present
            if hostname not in hosts_content:
                with open('/etc/hosts', 'a') as f:
                    f.write(f'\n127.0.1.1\t{hostname}\n')
            
            logger.info(f"Hostname set to {hostname}")
            
            return web.json_response({
                'status': 'success',
                'message': f'Hostname set to {hostname}'
            })
        
        except Exception as e:
            logger.error(f"Failed to set hostname: {e}")
            return web.json_response({
                'status': 'error',
                'message': 'Failed to set hostname'
            }, status=500)
    
    except Exception as e:
        logger.error(f"Error in set_hostname: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'An error occurred'
        }, status=500)


@require_firstrun
async def set_storage(request: web.Request) -> web.Response:
    """
    Configure VM storage location.
    
    POST /api/firstrun/set-storage
    Body: {"storage_path": "/var/lib/libvirt/images"}
    """
    try:
        data = await request.json()
        storage_path = data.get('storage_path', '/var/lib/libvirt/images').strip()
        
        if not storage_path:
            storage_path = '/var/lib/libvirt/images'
        
        # Validate path
        if not storage_path.startswith('/'):
            return web.json_response({
                'status': 'error',
                'message': 'Storage path must be an absolute path'
            }, status=400)
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(storage_path, mode=0o755, exist_ok=True)
            
            # Test write access
            test_file = os.path.join(storage_path, '.starlight-test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            
            # Ensure config directories exist
            ensure_config_directories()
            
            # Save configuration using config_loader
            config = {
                'vm_storage_path': storage_path,
                'iso_storage_path': os.path.join(os.path.dirname(storage_path), 'isos'),
                'default_pool_name': 'default'
            }
            
            if not save_storage_config(config):
                raise Exception("Failed to save storage configuration")
            
            logger.info(f"Storage path set to {storage_path}")
            
            return web.json_response({
                'status': 'success',
                'message': f'Storage configured at {storage_path}'
            })
        
        except PermissionError:
            return web.json_response({
                'status': 'error',
                'message': 'Permission denied: cannot write to storage path'
            }, status=400)
        except Exception as e:
            logger.error(f"Failed to configure storage: {e}")
            return web.json_response({
                'status': 'error',
                'message': 'Failed to configure storage'
            }, status=500)
    
    except Exception as e:
        logger.error(f"Error in set_storage: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'An error occurred'
        }, status=500)


@require_firstrun
async def complete_firstrun(request: web.Request) -> web.Response:
    """
    Complete the first-run wizard.
    
    POST /api/firstrun/complete
    """
    try:
        # Remove the needs-firstrun flag
        if os.path.exists(FIRSTRUN_FLAG):
            os.remove(FIRSTRUN_FLAG)
        
        # Create the firstrun-complete flag
        os.makedirs(STARLIGHT_CONFIG_DIR, exist_ok=True)
        with open(FIRSTRUN_COMPLETE_FLAG, 'w') as f:
            f.write('completed')
        
        # Switch nginx configuration from firstrun to normal
        try:
            nginx_sites_enabled = '/etc/nginx/sites-enabled'
            nginx_sites_available = '/etc/nginx/sites-available'
            
            # Remove firstrun config
            firstrun_link = os.path.join(nginx_sites_enabled, 'default')
            if os.path.islink(firstrun_link):
                os.remove(firstrun_link)
            
            # Enable normal Starlight config
            starlight_config = os.path.join(nginx_sites_available, 'starlight')
            if os.path.exists(starlight_config):
                os.symlink(starlight_config, firstrun_link)
            
            # Reload nginx
            subprocess.run(['systemctl', 'reload', 'nginx'], check=False)
        except Exception as e:
            logger.warning(f"Failed to switch nginx config: {e}")
        
        logger.info("First-run wizard completed successfully")
        
        return web.json_response({
            'status': 'success',
            'message': 'First-run wizard completed'
        })
    
    except Exception as e:
        logger.error(f"Error completing first-run: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'Failed to complete first-run wizard'
        }, status=500)
