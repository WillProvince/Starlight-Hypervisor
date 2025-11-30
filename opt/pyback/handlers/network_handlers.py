"""
Network configuration API handlers.

This module provides HTTP request handlers for managing network configuration
including getting/setting network settings and retrieving network status information.
"""

import os
import re
import socket
import logging
import subprocess
from aiohttp import web

from ..config_loader import (
    get_network_config,
    save_network_config,
    NETWORK_CONFIG_PATH,
)
from ..auth.user_management import is_admin

logger = logging.getLogger(__name__)

# Regex patterns for validation
IP_PATTERN = re.compile(
    r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
)
HOSTNAME_PATTERN = re.compile(
    r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
)


def validate_ip_address(ip: str) -> bool:
    """Validate an IP address format."""
    if not ip:
        return True  # Empty is allowed for optional fields
    return bool(IP_PATTERN.match(ip))


def validate_hostname(hostname: str) -> bool:
    """Validate a hostname format."""
    if not hostname:
        return True  # Empty is allowed
    return bool(HOSTNAME_PATTERN.match(hostname)) and len(hostname) <= 63


def get_current_ip() -> str:
    """Get the current primary IP address of the system."""
    try:
        # Create a socket to determine the IP address that would be used
        # to connect to an external host
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # Doesn't need to be reachable
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip
    except Exception as e:
        logger.warning(f"Error getting current IP: {e}")
        return 'unknown'


def get_current_hostname() -> str:
    """Get the current system hostname."""
    try:
        return socket.gethostname()
    except Exception as e:
        logger.warning(f"Error getting hostname: {e}")
        return 'unknown'


def get_primary_interface() -> str:
    """Get the primary network interface name."""
    try:
        result = subprocess.run(
            ['ip', 'route', 'show', 'default'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Parse output like: "default via 192.168.1.1 dev eth0 proto ..."
            parts = result.stdout.split()
            if 'dev' in parts:
                dev_index = parts.index('dev')
                if dev_index + 1 < len(parts):
                    return parts[dev_index + 1]
    except Exception as e:
        logger.warning(f"Error getting primary interface: {e}")
    return 'unknown'


def get_current_dns_servers() -> list:
    """Get currently configured DNS servers from systemd-resolved or resolv.conf."""
    dns_servers = []
    try:
        # Try systemd-resolved first (may not be available on all systems)
        result = subprocess.run(
            ['resolvectl', 'status'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'DNS Servers:' in line:
                    servers = line.split(':', 1)[1].strip().split()
                    dns_servers.extend(servers)
    except FileNotFoundError:
        # resolvectl binary not found on this system
        logger.debug("resolvectl binary not found, using resolv.conf fallback")
    except Exception as e:
        logger.warning(f"Error running resolvectl: {e}")
    
    # Fallback to resolv.conf if no DNS found via systemd-resolved
    if not dns_servers:
        try:
            if os.path.exists('/etc/resolv.conf'):
                with open('/etc/resolv.conf', 'r') as f:
                    for line in f:
                        if line.strip().startswith('nameserver'):
                            parts = line.split()
                            if len(parts) >= 2:
                                dns_servers.append(parts[1])
        except Exception as e:
            logger.warning(f"Error reading resolv.conf: {e}")
    
    return dns_servers[:2] if dns_servers else []


async def get_network_config_handler(request: web.Request) -> web.Response:
    """
    Get current network configuration.
    
    GET /api/network/config
    
    Returns:
        JSON response with network configuration
    """
    try:
        config = get_network_config(force_reload=True)
        
        return web.json_response({
            'status': 'success',
            'config': {
                'mode': config.get('mode', 'dhcp'),
                'hostname': config.get('hostname', ''),
                'ip_address': config.get('ip_address', ''),
                'netmask': config.get('netmask', '255.255.255.0'),
                'gateway': config.get('gateway', ''),
                'dns_primary': config.get('dns_primary', '8.8.8.8'),
                'dns_secondary': config.get('dns_secondary', '1.1.1.1'),
            }
        })
    except Exception as e:
        logger.error(f"Error getting network config: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'Failed to retrieve network configuration'
        }, status=500)


async def update_network_config_handler(request: web.Request) -> web.Response:
    """
    Update network configuration (admin only).
    
    POST /api/network/config
    
    Body:
        {
            "mode": "dhcp" | "static",
            "hostname": "starlight-server",
            "ip_address": "192.168.1.100",
            "netmask": "255.255.255.0",
            "gateway": "192.168.1.1",
            "dns_primary": "8.8.8.8",
            "dns_secondary": "1.1.1.1"
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
            'message': 'Admin privileges required to modify network configuration'
        }, status=403)
    
    try:
        data = await request.json()
    except Exception:
        return web.json_response({
            'status': 'error',
            'message': 'Invalid JSON body'
        }, status=400)
    
    # Get current config
    current_config = get_network_config(force_reload=True)
    
    # Validate and update
    errors = []
    
    # Validate mode
    mode = data.get('mode', current_config.get('mode', 'dhcp'))
    if mode not in ('dhcp', 'static'):
        errors.append("Mode must be 'dhcp' or 'static'")
    
    # Validate hostname
    hostname = data.get('hostname', current_config.get('hostname', ''))
    if hostname and not validate_hostname(hostname):
        errors.append('Invalid hostname format')
    
    # For static mode, validate IP settings
    if mode == 'static':
        ip_address = data.get('ip_address', '')
        if not ip_address:
            errors.append('IP address is required for static mode')
        elif not validate_ip_address(ip_address):
            errors.append('Invalid IP address format')
        
        gateway = data.get('gateway', '')
        if gateway and not validate_ip_address(gateway):
            errors.append('Invalid gateway format')
        
        netmask = data.get('netmask', '255.255.255.0')
        if not validate_ip_address(netmask):
            errors.append('Invalid netmask format')
    
    # Validate DNS servers
    dns_primary = data.get('dns_primary', current_config.get('dns_primary', '8.8.8.8'))
    if dns_primary and not validate_ip_address(dns_primary):
        errors.append('Invalid primary DNS format')
    
    dns_secondary = data.get('dns_secondary', current_config.get('dns_secondary', '1.1.1.1'))
    if dns_secondary and not validate_ip_address(dns_secondary):
        errors.append('Invalid secondary DNS format')
    
    if errors:
        return web.json_response({
            'status': 'error',
            'message': 'Validation failed',
            'errors': errors
        }, status=400)
    
    # Build new config
    new_config = {
        'mode': mode,
        'hostname': hostname,
        'ip_address': data.get('ip_address', current_config.get('ip_address', '')),
        'netmask': data.get('netmask', current_config.get('netmask', '255.255.255.0')),
        'gateway': data.get('gateway', current_config.get('gateway', '')),
        'dns_primary': dns_primary,
        'dns_secondary': dns_secondary,
    }
    
    # Save configuration
    if not save_network_config(new_config):
        return web.json_response({
            'status': 'error',
            'message': 'Failed to save network configuration'
        }, status=500)
    
    logger.info(f"Network configuration updated by {username}")
    
    return web.json_response({
        'status': 'success',
        'message': 'Network configuration saved. Changes will take effect after applying network settings.',
        'config': new_config,
        'apply_required': True
    })


async def get_network_status_handler(request: web.Request) -> web.Response:
    """
    Get current network status (real-time system info).
    
    GET /api/network/status
    
    Returns:
        JSON response with current network status
    """
    try:
        current_ip = get_current_ip()
        current_hostname = get_current_hostname()
        primary_interface = get_primary_interface()
        dns_servers = get_current_dns_servers()
        
        return web.json_response({
            'status': 'success',
            'network_status': {
                'ip_address': current_ip,
                'hostname': current_hostname,
                'interface': primary_interface,
                'dns_servers': dns_servers,
            }
        })
    except Exception as e:
        logger.error(f"Error getting network status: {e}")
        return web.json_response({
            'status': 'error',
            'message': 'Failed to retrieve network status'
        }, status=500)
