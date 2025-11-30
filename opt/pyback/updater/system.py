"""
System update functions.

This module provides functions for checking, performing, and rolling back
system updates using git, including file synchronization, package updates,
and update script execution.
"""

import os
import json
import logging
import asyncio
import subprocess
import stat
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config import GIT_REPO_PATH
from ..config_loader import (
    VERSION_FILE_PATH,
    get_service_name,
    get_updater_config,
    save_updater_config,
)
from ..utils.libvirt_connection import get_connection
from .backup import load_update_config, save_update_config, create_backup
from .file_sync import sync_repo_to_system, validate_sync
from .package_manager import (
    apt_update,
    apt_upgrade,
)

logger = logging.getLogger(__name__)

# Path to update scripts in repository
UPDATE_SCRIPT_PATH = 'scripts/update.sh'
POST_UPDATE_DIR = 'scripts/post-update.d'


def get_repo_path() -> str:
    """
    Get the git repository path from configuration or default.
    
    Returns:
        str: Path to the git repository
    """
    # GIT_REPO_PATH is calculated from the module location
    # This provides a fallback that can be overridden by config
    return GIT_REPO_PATH


def get_repo_url() -> str:
    """
    Get the git repository URL from configuration.
    
    Returns:
        str: Git repository URL
    """
    config = get_updater_config()
    return config.get('repository_url', 'https://github.com/WillProvince/Starlight-Hidden.git')


def get_repo_branch() -> str:
    """
    Get the git branch to use from configuration.
    
    Returns:
        str: Git branch name
    """
    config = get_updater_config()
    return config.get('branch', 'main')


def validate_git_repo():
    """Validates that the repository path points to a valid git repository."""
    try:
        repo_path = get_repo_path()
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=repo_path,
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_current_version():
    """Gets the current version information."""
    try:
        # Try to get version from version file
        if os.path.exists(VERSION_FILE_PATH):
            with open(VERSION_FILE_PATH, 'r') as f:
                return json.load(f)
        
        # Fall back to git if no version file exists
        if not validate_git_repo():
            return {
                'version': 'unknown',
                'commit': 'unknown',
                'date': 'unknown',
                'branch': 'unknown'
            }
        
        repo_path = get_repo_path()
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            commit_hash = result.stdout.strip()
            
            # Get commit date
            date_result = subprocess.run(
                ['git', 'log', '-1', '--format=%ci'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            commit_date = date_result.stdout.strip() if date_result.returncode == 0 else 'unknown'
            
            return {
                'version': commit_hash,
                'commit': commit_hash,
                'date': commit_date,
                'branch': get_repo_branch()
            }
        else:
            return {
                'version': 'unknown',
                'commit': 'unknown',
                'date': 'unknown',
                'branch': 'unknown'
            }
    except Exception as e:
        logger.error(f"Error getting current version: {e}")
        return {
            'version': 'unknown',
            'commit': 'unknown',
            'date': 'unknown',
            'branch': 'unknown'
        }


def check_for_updates():
    """Checks if updates are available."""
    try:
        # Validate git repository first
        if not validate_git_repo():
            logger.error("Repository path does not point to a valid git repository")
            return None
        
        repo_path = get_repo_path()
        branch = get_repo_branch()
        
        # Fetch latest changes from remote
        result = subprocess.run(
            ['git', 'fetch', 'origin'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to fetch updates: {result.stderr}")
            return None
        
        # Check if there are new commits
        result = subprocess.run(
            ['git', 'rev-list', '--count', f'HEAD..origin/{branch}'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            commit_count = int(result.stdout.strip())
            
            if commit_count > 0:
                # Get the latest commit info
                log_result = subprocess.run(
                    ['git', 'log', f'origin/{branch}', '-1', '--format=%H|%ci|%s'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if log_result.returncode == 0:
                    parts = log_result.stdout.strip().split('|')
                    return {
                        'available': True,
                        'commit_count': commit_count,
                        'latest_commit': parts[0] if len(parts) > 0 else 'unknown',
                        'latest_date': parts[1] if len(parts) > 1 else 'unknown',
                        'latest_message': parts[2] if len(parts) > 2 else 'Update available'
                    }
            
            return {
                'available': False,
                'commit_count': 0,
                'message': 'System is up to date'
            }
        else:
            logger.error(f"Failed to check for updates: {result.stderr}")
            return None
    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return None


def _execute_update_script(script_path: str) -> Dict:
    """
    Execute an update script safely.
    
    Args:
        script_path: Path to the script to execute
        
    Returns:
        dict: Execution result
    """
    result = {
        'script': os.path.basename(script_path),
        'success': False,
        'stdout': '',
        'stderr': '',
        'error': None
    }
    
    if not os.path.exists(script_path):
        result['error'] = f"Script not found: {script_path}"
        return result
    
    repo_path = get_repo_path()
    
    # Validate script path to prevent injection
    script_path = os.path.abspath(script_path)
    abs_repo_path = os.path.abspath(repo_path)
    
    if not script_path.startswith(abs_repo_path):
        result['error'] = "Script path is outside repository"
        logger.error(f"Security: Attempted to execute script outside repo: {script_path}")
        return result
    
    try:
        # Ensure script is executable
        current_mode = os.stat(script_path).st_mode
        os.chmod(script_path, current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        
        # Execute the script
        logger.info(f"Executing update script: {script_path}")
        
        proc = subprocess.run(
            ['bash', script_path],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=300,
            env={
                **os.environ,
                'STARLIGHT_REPO_PATH': repo_path,
                'STARLIGHT_SERVICE_NAME': get_service_name()
            }
        )
        
        result['stdout'] = proc.stdout
        result['stderr'] = proc.stderr
        result['success'] = proc.returncode == 0
        result['returncode'] = proc.returncode
        
        if not result['success']:
            logger.warning(f"Script {script_path} returned code {proc.returncode}")
            
    except subprocess.TimeoutExpired:
        result['error'] = "Script timed out"
        logger.error(f"Script timed out: {script_path}")
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error executing script {script_path}: {e}")
    
    return result


def _run_update_scripts() -> Dict:
    """
    Run update scripts from the scripts directory.
    
    Returns:
        dict: Results of script execution
    """
    result = {
        'scripts_executed': [],
        'scripts_succeeded': 0,
        'scripts_failed': 0,
        'errors': []
    }
    
    repo_path = get_repo_path()
    
    # Run main update.sh script if it exists
    main_script = os.path.join(repo_path, UPDATE_SCRIPT_PATH)
    if os.path.exists(main_script):
        script_result = _execute_update_script(main_script)
        result['scripts_executed'].append(script_result['script'])
        
        if script_result['success']:
            result['scripts_succeeded'] += 1
        else:
            result['scripts_failed'] += 1
            if script_result['error']:
                result['errors'].append(f"{script_result['script']}: {script_result['error']}")
    
    # Run scripts from post-update.d directory
    post_update_dir = os.path.join(repo_path, POST_UPDATE_DIR)
    if os.path.isdir(post_update_dir):
        # Get all .sh files and sort them
        scripts = sorted([
            f for f in os.listdir(post_update_dir)
            if f.endswith('.sh') and os.path.isfile(os.path.join(post_update_dir, f))
        ])
        
        for script_name in scripts:
            script_path = os.path.join(post_update_dir, script_name)
            script_result = _execute_update_script(script_path)
            result['scripts_executed'].append(f"post-update.d/{script_result['script']}")
            
            if script_result['success']:
                result['scripts_succeeded'] += 1
            else:
                result['scripts_failed'] += 1
                if script_result['error']:
                    result['errors'].append(f"{script_name}: {script_result['error']}")
    
    return result


def perform_update(
    sync_files: Optional[bool] = None,
    update_packages: Optional[bool] = None,
    run_scripts: Optional[bool] = None
) -> Dict:
    """
    Performs a complete system update.
    
    This includes:
    1. Creating a backup
    2. Stashing local changes
    3. Pulling git changes
    4. Syncing all files to system locations
    5. Running apt update and upgrade
    6. Executing update scripts
    7. Validating the update
    
    Args:
        sync_files: Whether to sync files to system locations (uses config default if None)
        update_packages: Whether to run apt update/upgrade (uses config default if None)
        run_scripts: Whether to execute update scripts (uses config default if None)
        
    Returns:
        dict: Detailed result including:
            - success: Overall success status
            - message: Human-readable status message
            - backup: Backup information
            - restart_required: Whether service restart is needed
            - changes: Details of what was changed
            - errors: List of non-fatal errors
    """
    # Get configuration
    updater_config = get_updater_config()
    
    # Use config defaults if parameters not explicitly provided
    if sync_files is None:
        sync_files = updater_config.get('auto_sync_files', True)
    if update_packages is None:
        update_packages = updater_config.get('auto_update_packages', True)
    if run_scripts is None:
        run_scripts = updater_config.get('run_update_scripts', True)
    
    repo_path = get_repo_path()
    branch = get_repo_branch()
    
    result = {
        'success': False,
        'message': '',
        'backup': None,
        'restart_required': True,
        'changes': {
            'files_synced': 0,
            'packages_updated': 0,
            'scripts_executed': []
        },
        'errors': []
    }
    
    try:
        # Step 1: Create backup first
        logger.info("Step 1/7: Creating backup...")
        backup_info = create_backup()
        if not backup_info:
            result['message'] = 'Failed to create backup'
            return result
        
        result['backup'] = backup_info
        
        # Step 2: Stash any local changes (ignore errors if nothing to stash)
        logger.info("Step 2/7: Stashing local changes...")
        stash_result = subprocess.run(
            ['git', 'stash', 'push', '-m', 'Auto-stash before update'],
            cwd=repo_path,
            capture_output=True,
            timeout=10
        )
        if stash_result.returncode != 0:
            logger.debug(f"Git stash returned non-zero: {stash_result.stderr}")
        
        # Step 3: Pull latest changes
        logger.info(f"Step 3/7: Pulling latest changes from git (branch: {branch})...")
        pull_result = subprocess.run(
            ['git', 'pull', 'origin', branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if pull_result.returncode != 0:
            logger.error(f"Git pull failed: {pull_result.stderr}")
            # Attempt rollback
            rollback_result = rollback_update(backup_info['commit'])
            result['message'] = f'Git pull failed: {pull_result.stderr}'
            result['errors'].append(result['message'])
            return result
        
        logger.info("Git pull completed successfully")
        
        # Step 4: Sync all files to system locations
        if sync_files:
            logger.info("Step 4/7: Syncing all files to system locations...")
            try:
                sync_result = sync_repo_to_system(repo_path)
                result['changes']['files_synced'] = sync_result['total_files_synced']
                
                if sync_result['errors']:
                    for error in sync_result['errors']:
                        result['errors'].append(f"File sync: {error}")
                
                logger.info(f"File sync completed: {sync_result['total_files_synced']} files synced")
            except Exception as e:
                error_msg = f"File sync error: {e}"
                logger.error(error_msg)
                result['errors'].append(error_msg)
        
        # Step 5: Run apt update and upgrade
        if update_packages:
            logger.info("Step 5/7: Running system package updates...")
            try:
                # Run apt update
                apt_update_result = apt_update()
                if not apt_update_result['success']:
                    result['errors'].append(f"apt update failed: {apt_update_result['stderr']}")
                else:
                    # Run apt upgrade
                    apt_upgrade_result = apt_upgrade()
                    if apt_upgrade_result['success']:
                        result['changes']['packages_updated'] = apt_upgrade_result.get('packages_upgraded', 0)
                        logger.info(f"Package update completed: {result['changes']['packages_updated']} packages updated")
                    else:
                        result['errors'].append(f"apt upgrade failed: {apt_upgrade_result['stderr']}")
            except Exception as e:
                error_msg = f"Package update error: {e}"
                logger.error(error_msg)
                result['errors'].append(error_msg)
        
        # Step 6: Execute update scripts
        if run_scripts:
            logger.info("Step 6/7: Running update scripts...")
            try:
                script_result = _run_update_scripts()
                result['changes']['scripts_executed'] = script_result['scripts_executed']
                
                if script_result['errors']:
                    for error in script_result['errors']:
                        result['errors'].append(f"Script error: {error}")
                
                logger.info(f"Update scripts completed: {script_result['scripts_succeeded']} succeeded, {script_result['scripts_failed']} failed")
            except Exception as e:
                error_msg = f"Script execution error: {e}"
                logger.error(error_msg)
                result['errors'].append(error_msg)
        
        # Step 7: Update the last update timestamp
        logger.info("Step 7/7: Updating configuration...")
        config = load_update_config()
        config['last_update'] = datetime.now().isoformat()
        save_update_config(config)
        
        # Mark as successful
        result['success'] = True
        result['message'] = 'Update completed successfully'
        
        # Add details about errors if any (non-fatal)
        if result['errors']:
            result['message'] += f" with {len(result['errors'])} non-fatal error(s)"
        
        logger.info("Update process completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error performing update: {e}")
        result['message'] = str(e)
        result['errors'].append(str(e))
        
        # Attempt rollback if we have backup info
        if result['backup']:
            try:
                rollback_result = rollback_update(result['backup']['commit'])
                result['rollback_attempted'] = True
                result['rollback_success'] = rollback_result.get('success', False)
            except Exception as rb_error:
                result['errors'].append(f"Rollback failed: {rb_error}")
        
        return result


def schedule_service_restart(delay_seconds=2):
    """Schedules a service restart after a delay."""
    async def restart_service():
        await asyncio.sleep(delay_seconds)
        try:
            service_name = get_service_name()
            subprocess.run(
                ['systemctl', 'restart', service_name],
                timeout=10
            )
            logger.info("Service restart triggered")
        except Exception as e:
            logger.error(f"Failed to restart service: {e}")
    
    asyncio.create_task(restart_service())


def rollback_update(commit_hash):
    """Rolls back to a previous commit."""
    try:
        logger.info(f"Rolling back to commit {commit_hash}")
        
        repo_path = get_repo_path()
        
        # Reset to the specified commit
        result = subprocess.run(
            ['git', 'reset', '--hard', commit_hash],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"Rollback failed: {result.stderr}")
            return {'success': False, 'error': result.stderr}
        
        logger.info("Rollback completed successfully")
        return {
            'success': True,
            'message': f'Rolled back to commit {commit_hash}'
        }
    except Exception as e:
        logger.error(f"Error during rollback: {e}")
        return {'success': False, 'error': str(e)}


def perform_health_check():
    """Performs a health check of the system after update."""
    try:
        service_name = get_service_name()
        # Check if the backend service is running
        result = subprocess.run(
            ['systemctl', 'is-active', service_name],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        service_running = result.returncode == 0 and result.stdout.strip() == 'active'
        
        # Check if we can connect to libvirt
        libvirt_ok = get_connection() is not None
        
        return {
            'healthy': service_running and libvirt_ok,
            'service_running': service_running,
            'libvirt_connected': libvirt_ok
        }
    except Exception as e:
        logger.error(f"Error during health check: {e}")
        return {
            'healthy': False,
            'error': str(e)
        }
