"""
System power management API handlers.

This module provides HTTP request handlers for system reboot and shutdown operations.
"""

import logging
import subprocess
from aiohttp import web

from ..auth.middleware import require_admin

logger = logging.getLogger(__name__)


@require_admin
async def reboot_system(request):
    """
    Reboot the server.
    
    Requires admin privileges.
    
    Note: This uses sudo systemctl commands. The application should be configured
    with appropriate sudoers rules to allow the service account to execute
    'systemctl reboot' and 'systemctl poweroff' without a password prompt.
    Example sudoers rule:
        starlight-service ALL=(ALL) NOPASSWD: /bin/systemctl reboot, /bin/systemctl poweroff
    """
    try:
        logger.info(f"Server reboot requested by {request['user']['username']}")
        
        # Execute reboot command in background
        # Using subprocess.Popen to avoid blocking the response
        subprocess.Popen(['systemctl', 'reboot'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        
        return web.json_response({
            'status': 'success',
            'message': 'Server reboot initiated'
        })
    except Exception as e:
        logger.error(f"Error initiating server reboot: {e}")
        return web.json_response({
            'status': 'error',
            'message': f'Failed to reboot server: {str(e)}'
        }, status=500)


@require_admin
async def shutdown_system(request):
    """
    Shutdown the server.
    
    Requires admin privileges.
    
    Note: This uses sudo systemctl commands. See reboot_system() for sudoers
    configuration requirements.
    """
    try:
        logger.info(f"Server shutdown requested by {request['user']['username']}")
        
        # Execute shutdown command in background
        # Using subprocess.Popen to avoid blocking the response
        subprocess.Popen(['sudo', 'systemctl', 'poweroff'], 
                        stdout=subprocess.DEVNULL, 
                        stderr=subprocess.DEVNULL)
        
        return web.json_response({
            'status': 'success',
            'message': 'Server shutdown initiated'
        })
    except Exception as e:
        logger.error(f"Error initiating server shutdown: {e}")
        return web.json_response({
            'status': 'error',
            'message': f'Failed to shutdown server: {str(e)}'
        }, status=500)
