"""
Package management functions for Starlight updates.

This module provides functions for managing system packages during updates
using apt.
"""

import os
import subprocess
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _run_command(
    cmd: List[str],
    timeout: int = 300,
    env: Optional[Dict] = None
) -> Dict:
    """
    Run a shell command and capture output.
    
    Args:
        cmd: Command and arguments as list
        timeout: Command timeout in seconds
        env: Optional environment variables
        
    Returns:
        dict: Command result with returncode, stdout, stderr
    """
    result = {
        'success': False,
        'returncode': -1,
        'stdout': '',
        'stderr': '',
        'command': ' '.join(cmd)
    }
    
    try:
        # Merge with current environment
        run_env = os.environ.copy()
        if env:
            run_env.update(env)
        
        # Set DEBIAN_FRONTEND to noninteractive to avoid prompts
        run_env['DEBIAN_FRONTEND'] = 'noninteractive'
        
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env
        )
        
        result['returncode'] = proc.returncode
        result['stdout'] = proc.stdout
        result['stderr'] = proc.stderr
        result['success'] = proc.returncode == 0
        
    except subprocess.TimeoutExpired:
        result['stderr'] = f"Command timed out after {timeout} seconds"
        logger.error(f"Command timed out: {' '.join(cmd)}")
    except Exception as e:
        result['stderr'] = str(e)
        logger.error(f"Error running command {' '.join(cmd)}: {e}")
    
    return result


def apt_update() -> Dict:
    """
    Run apt-get update to refresh package lists.
    
    Returns:
        dict: Result with success status and output
    """
    logger.info("Running apt-get update...")
    
    result = _run_command(['apt-get', 'update'], timeout=120)
    
    if result['success']:
        logger.info("apt-get update completed successfully")
    else:
        logger.error(f"apt-get update failed: {result['stderr']}")
    
    return result


def apt_upgrade(dist_upgrade: bool = False) -> Dict:
    """
    Run apt-get upgrade to upgrade installed packages.
    
    Args:
        dist_upgrade: If True, run dist-upgrade instead of upgrade
        
    Returns:
        dict: Result with success status, output, and packages updated
    """
    upgrade_cmd = 'dist-upgrade' if dist_upgrade else 'upgrade'
    logger.info(f"Running apt-get {upgrade_cmd}...")
    
    # Use -y for non-interactive, -q for quieter output
    cmd = ['apt-get', upgrade_cmd, '-y', '-q']
    
    result = _run_command(cmd, timeout=600)
    
    # Parse output to count upgraded packages
    packages_upgraded = 0
    if result['success'] and result['stdout']:
        for line in result['stdout'].splitlines():
            if 'upgraded,' in line and 'newly installed' in line:
                # Parse line like "5 upgraded, 0 newly installed..."
                try:
                    packages_upgraded = int(line.split()[0])
                except (ValueError, IndexError):
                    pass
    
    result['packages_upgraded'] = packages_upgraded
    
    if result['success']:
        logger.info(f"apt-get {upgrade_cmd} completed: {packages_upgraded} packages upgraded")
    else:
        logger.error(f"apt-get {upgrade_cmd} failed: {result['stderr']}")
    
    return result


def install_package(package_name: str, version: Optional[str] = None) -> Dict:
    """
    Install a specific apt package.
    
    Args:
        package_name: Name of the package to install
        version: Optional specific version
        
    Returns:
        dict: Installation result
    """
    logger.info(f"Installing package: {package_name}")
    
    pkg_spec = package_name
    if version:
        pkg_spec = f"{package_name}={version}"
    
    result = _run_command(
        ['apt-get', 'install', '-y', '-q', pkg_spec],
        timeout=300
    )
    
    if result['success']:
        logger.info(f"Package {package_name} installed successfully")
    else:
        logger.error(f"Failed to install {package_name}: {result['stderr']}")
    
    return result


def get_package_info(package_name: str) -> Dict:
    """
    Get information about an installed package.
    
    Args:
        package_name: Name of the package
        
    Returns:
        dict: Package information or None if not installed
    """
    result = _run_command(
        ['dpkg', '-s', package_name],
        timeout=10
    )
    
    if not result['success']:
        return {'installed': False, 'package': package_name}
    
    info = {
        'installed': True,
        'package': package_name,
        'version': None,
        'status': None
    }
    
    for line in result['stdout'].splitlines():
        if line.startswith('Version:'):
            info['version'] = line.split(':', 1)[1].strip()
        elif line.startswith('Status:'):
            info['status'] = line.split(':', 1)[1].strip()
    
    return info


def run_apt_autoremove() -> Dict:
    """
    Run apt-get autoremove to clean up unused packages.
    
    Returns:
        dict: Command result
    """
    logger.info("Running apt-get autoremove...")
    
    result = _run_command(
        ['apt-get', 'autoremove', '-y', '-q'],
        timeout=120
    )
    
    if result['success']:
        logger.info("apt-get autoremove completed")
    else:
        logger.warning(f"apt-get autoremove failed: {result['stderr']}")
    
    return result


def run_apt_clean() -> Dict:
    """
    Run apt-get clean to free up disk space.
    
    Returns:
        dict: Command result
    """
    logger.info("Running apt-get clean...")
    
    result = _run_command(['apt-get', 'clean'], timeout=60)
    
    if result['success']:
        logger.info("apt-get clean completed")
    else:
        logger.warning(f"apt-get clean failed: {result['stderr']}")
    
    return result


def full_system_update() -> Dict:
    """
    Perform a full system package update (apt update + upgrade).
    
    Returns:
        dict: Combined result of update and upgrade
    """
    result = {
        'success': False,
        'apt_update': None,
        'apt_upgrade': None,
        'packages_upgraded': 0,
        'errors': []
    }
    
    # Run apt update
    update_result = apt_update()
    result['apt_update'] = update_result
    
    if not update_result['success']:
        result['errors'].append(f"apt update failed: {update_result['stderr']}")
        return result
    
    # Run apt upgrade
    upgrade_result = apt_upgrade()
    result['apt_upgrade'] = upgrade_result
    result['packages_upgraded'] = upgrade_result.get('packages_upgraded', 0)
    
    if not upgrade_result['success']:
        result['errors'].append(f"apt upgrade failed: {upgrade_result['stderr']}")
        return result
    
    result['success'] = True
    return result
