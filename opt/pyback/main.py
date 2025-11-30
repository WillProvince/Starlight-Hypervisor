"""
Starlight Hypervisor Manager - Main Entry Point

This is the main entry point for the Starlight backend API server.
All functionality is now organized into modular packages.
"""

import sys
import os

# Configure module path for package imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import logging
from aiohttp import web

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import handlers
from pyback.handlers.vm_handlers import list_vms, create_vm, get_vm_disk_info, update_vm_settings
from pyback.handlers.vm_actions import vm_action
from pyback.handlers.vm_deployment import deploy_vm_from_url
from pyback.handlers.repository_handlers import (
    list_repositories, get_all_apps, add_repository, 
    update_repository, delete_repository
)
from pyback.handlers.download_handlers import (
    get_download_progress, get_all_downloads, 
    get_deployment_logs, cleanup_orphaned_containers,
    download_progress as dl_progress
)
from pyback.handlers.update_handlers import (
    get_update_status, check_updates, trigger_update,
    update_auto_update_config, get_update_history, perform_rollback
)
from pyback.handlers.auth_handlers import (
    login, logout, verify, refresh,
    get_users, add_user, modify_user, remove_user, change_user_password,
    get_api_keys, create_new_api_key, delete_user_api_key, modify_api_key
)
from pyback.handlers.system_handlers import (
    reboot_system, shutdown_system
)
from pyback.handlers.firstrun_handlers import (
    firstrun_status, get_system_info, set_root_password,
    create_admin_user, set_hostname, set_storage, complete_firstrun
)
from pyback.handlers.storage_handlers import (
    get_storage_config_handler, update_storage_config_handler,
    get_storage_info_handler, validate_storage_path_handler
)
from pyback.handlers.network_handlers import (
    get_network_config_handler, update_network_config_handler,
    get_network_status_handler
)

# Import proxies
from pyback.proxies.vnc_proxy import vnc_proxy_handler
from pyback.proxies.lxc_console import lxc_console_handler
from pyback.proxies.host_console import host_console_handler

# Import authentication middleware
from pyback.auth.middleware import auth_middleware

# Import utilities for initialization
from pyback.utils.libvirt_connection import get_connection

# Initialize download progress tracking for VM deployment module
import pyback.handlers.vm_deployment as vm_deployment_module
vm_deployment_module.download_progress = dl_progress


def init_app():
    """Initializes the Aiohttp application with routes."""
    app = web.Application()
    
    # Set up CORS middleware to allow the NGINX frontend to access the API
    async def cors_middleware(app, handler):
        async def middleware_handler(request):
            # Handle OPTIONS preflight requests
            if request.method == 'OPTIONS':
                response = web.Response()
            else:
                response = await handler(request)
            
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-API-Key'
            response.headers['Access-Control-Max-Age'] = '86400'  # 24 hours
            return response
        return middleware_handler

    # Add middlewares (applied in reverse order: CORS outermost, then auth)
    app.middlewares.append(cors_middleware)
    app.middlewares.append(auth_middleware) 

    # ---< API Routes >---
    # Authentication
    app.router.add_post('/api/auth/login', login)
    app.router.add_post('/api/auth/logout', logout)
    app.router.add_get('/api/auth/verify', verify)
    app.router.add_post('/api/auth/refresh', refresh)
    
    # User Management
    app.router.add_get('/api/users', get_users)
    app.router.add_post('/api/users', add_user)
    app.router.add_put('/api/users/{username}', modify_user)
    app.router.add_delete('/api/users/{username}', remove_user)
    app.router.add_post('/api/users/{username}/password', change_user_password)
    
    # API Key Management
    app.router.add_get('/api/auth/api-keys', get_api_keys)
    app.router.add_post('/api/auth/api-keys', create_new_api_key)
    app.router.add_delete('/api/auth/api-keys/{key_id}', delete_user_api_key)
    app.router.add_put('/api/auth/api-keys/{key_id}', modify_api_key)
    
    # VM Management
    app.router.add_get('/api/vm_list', list_vms)
    app.router.add_post('/api/vm', create_vm)
    app.router.add_post('/api/vm/deploy', deploy_vm_from_url)
    app.router.add_get('/api/vm/{name}/disk-info', get_vm_disk_info)
    app.router.add_put('/api/vm/{name}/settings', update_vm_settings)
    app.router.add_post('/api/vm/{name}/{action}', vm_action)
    
    # Repository Management
    app.router.add_get('/api/repositories', list_repositories)
    app.router.add_get('/api/repositories/apps', get_all_apps)
    app.router.add_post('/api/repositories', add_repository)
    app.router.add_put('/api/repositories/{id}', update_repository)
    app.router.add_delete('/api/repositories/{id}', delete_repository)
    
    # Download Progress
    app.router.add_get('/api/downloads/{vm_name}', get_download_progress)
    app.router.add_get('/api/downloads', get_all_downloads)
    app.router.add_get('/api/logs', get_deployment_logs)
    
    # Cleanup
    app.router.add_post('/api/cleanup/orphaned', cleanup_orphaned_containers)
    
    # Updater
    app.router.add_get('/api/update/status', get_update_status)
    app.router.add_get('/api/update/check', check_updates)
    app.router.add_post('/api/update/trigger', trigger_update)
    app.router.add_post('/api/update/rollback', perform_rollback)
    app.router.add_put('/api/update/config', update_auto_update_config)
    app.router.add_get('/api/update/history', get_update_history)
    
    # System Power Management
    app.router.add_post('/api/system/reboot', reboot_system)
    app.router.add_post('/api/system/shutdown', shutdown_system)
    
    # Storage Management
    app.router.add_get('/api/storage/config', get_storage_config_handler)
    app.router.add_post('/api/storage/config', update_storage_config_handler)
    app.router.add_get('/api/storage/info', get_storage_info_handler)
    app.router.add_post('/api/storage/validate', validate_storage_path_handler)
    
    # Network Management
    app.router.add_get('/api/network/config', get_network_config_handler)
    app.router.add_post('/api/network/config', update_network_config_handler)
    app.router.add_get('/api/network/status', get_network_status_handler)

    # ---< First-Run Wizard >---
    # Endpoints available only during initial setup (when .needs-firstrun flag exists)
    app.router.add_get('/api/firstrun/status', firstrun_status)
    app.router.add_get('/api/firstrun/system-info', get_system_info)
    app.router.add_post('/api/firstrun/set-root-password', set_root_password)
    app.router.add_post('/api/firstrun/create-admin', create_admin_user)
    app.router.add_post('/api/firstrun/set-hostname', set_hostname)
    app.router.add_post('/api/firstrun/set-storage', set_storage)
    app.router.add_post('/api/firstrun/complete', complete_firstrun)

    # ---< Proxies >---
    # VNC 
    app.router.add_get('/vnc-proxy/{port}', vnc_proxy_handler)
    # LXC Console
    app.router.add_get('/lxc-console/{name}', lxc_console_handler)
    # Host Console (root only)
    app.router.add_get('/host-console', host_console_handler)
    
    return app


if __name__ == '__main__':
    # Log connection attempt status
    if get_connection():
        logger.info("Successfully connected to libvirt. Aiohttp API & WS Proxy ready.")
    else:
        logger.critical("Failed to connect to libvirt. Ensure KVM/libvirt is installed and service is running.")

    # Start the Aiohttp application
    # Bind to all interfaces (0.0.0.0) to remain accessible during network changes
    # such as bridge setup where IP addresses may temporarily change
    app = init_app()
    web.run_app(app, host='0.0.0.0', port=5000)
