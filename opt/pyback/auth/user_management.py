"""
User Management Module

Handles creation, modification, and deletion of system users for Starlight.
Requires appropriate sudo permissions or running as root.
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, List

from ..config_loader import get_config_file_path, USERS_METADATA_PATH as CONFIG_USERS_PATH

logger = logging.getLogger(__name__)

# Configuration paths - use config_loader paths with fallback
def _get_users_metadata_path():
    """Get the users metadata path with fallback to legacy."""
    new_path = CONFIG_USERS_PATH
    legacy_path = get_config_file_path('users', use_legacy=True)
    
    # Return new path if it exists, otherwise check legacy
    if Path(new_path).exists():
        return new_path
    if Path(legacy_path).exists():
        return legacy_path
    # Default to new path for new installations
    return new_path

USERS_METADATA_PATH = _get_users_metadata_path()

# Starlight users group name
STARLIGHT_GROUP = 'starlight-users'

# System users to exclude from listing (UIDs < 1000)
MIN_UID = 1000


def load_users_metadata() -> dict:
    """Load users metadata from storage file."""
    metadata_path = Path(_get_users_metadata_path())
    
    if not metadata_path.exists():
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        default_data = {'users': {}}
        save_users_metadata(default_data)
        return default_data
    
    try:
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading users metadata: {e}")
        return {'users': {}}


def save_users_metadata(data: dict):
    """Save users metadata to storage file."""
    try:
        # Always save to new location
        metadata_path = Path(CONFIG_USERS_PATH)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, 'w') as f:
            json.dump(data, f, indent=2)
        # Set restrictive permissions
        metadata_path.chmod(0o600)
    except Exception as e:
        logger.error(f"Error saving users metadata: {e}")


def ensure_starlight_group() -> bool:
    """
    Ensure the starlight-users group exists.
    
    Returns:
        bool: True if group exists or was created successfully
    """
    try:
        # Check if group exists
        result = subprocess.run(
            ['getent', 'group', STARLIGHT_GROUP],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return True
        
        # Create the group
        result = subprocess.run(
            ['groupadd', STARLIGHT_GROUP],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"Created group: {STARLIGHT_GROUP}")
            return True
        else:
            logger.error(f"Failed to create group {STARLIGHT_GROUP}: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error ensuring starlight group: {e}")
        return False


def create_user(username: str, password: str, role: str = 'user', 
                full_name: str = '', shell: str = '/bin/bash') -> Dict[str, any]:
    """
    Create a new system user for Starlight.
    
    Args:
        username: The username to create
        password: The user's password
        role: User role ('admin' or 'user')
        full_name: Optional full name/description
        shell: User's shell (default: /bin/bash)
        
    Returns:
        dict: Result with status and message
    """
    try:
        # Ensure starlight group exists
        if not ensure_starlight_group():
            return {'status': 'error', 'message': 'Failed to ensure starlight-users group exists'}
        
        # Create the user
        cmd = ['useradd', '-m', '-s', shell, '-c', full_name or username]
        
        # Add to starlight-users group
        cmd.extend(['-G', STARLIGHT_GROUP])
        
        cmd.append(username)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Failed to create user {username}: {result.stderr}")
            return {'status': 'error', 'message': f'Failed to create user: {result.stderr}'}
        
        # Set password
        password_result = subprocess.run(
            ['chpasswd'],
            input=f"{username}:{password}",
            capture_output=True,
            text=True
        )
        
        if password_result.returncode != 0:
            logger.error(f"Failed to set password for {username}: {password_result.stderr}")
            # Try to clean up the created user
            subprocess.run(['userdel', '-r', username], capture_output=True)
            return {'status': 'error', 'message': 'Failed to set user password'}
        
        # Save user metadata
        metadata = load_users_metadata()
        metadata['users'][username] = {
            'role': role,
            'full_name': full_name,
            'created_by': 'system',
            'created_at': subprocess.run(
                ['date', '-Iseconds'],
                capture_output=True,
                text=True
            ).stdout.strip()
        }
        save_users_metadata(metadata)
        
        logger.info(f"Created user: {username} with role: {role}")
        return {'status': 'success', 'message': f'User {username} created successfully'}
    
    except Exception as e:
        logger.error(f"Error creating user {username}: {e}")
        return {'status': 'error', 'message': str(e)}


def delete_user(username: str, remove_home: bool = True) -> Dict[str, any]:
    """
    Delete a system user.
    
    Args:
        username: The username to delete
        remove_home: Whether to remove the user's home directory
        
    Returns:
        dict: Result with status and message
    """
    try:
        cmd = ['userdel']
        if remove_home:
            cmd.append('-r')
        cmd.append(username)
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"Failed to delete user {username}: {result.stderr}")
            return {'status': 'error', 'message': f'Failed to delete user: {result.stderr}'}
        
        # Remove from metadata
        metadata = load_users_metadata()
        if username in metadata['users']:
            del metadata['users'][username]
            save_users_metadata(metadata)
        
        logger.info(f"Deleted user: {username}")
        return {'status': 'success', 'message': f'User {username} deleted successfully'}
    
    except Exception as e:
        logger.error(f"Error deleting user {username}: {e}")
        return {'status': 'error', 'message': str(e)}


def change_password(username: str, new_password: str) -> Dict[str, any]:
    """
    Change a user's password.
    
    Args:
        username: The username
        new_password: The new password
        
    Returns:
        dict: Result with status and message
    """
    try:
        result = subprocess.run(
            ['chpasswd'],
            input=f"{username}:{new_password}",
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to change password for {username}: {result.stderr}")
            return {'status': 'error', 'message': 'Failed to change password'}
        
        logger.info(f"Changed password for user: {username}")
        return {'status': 'success', 'message': 'Password changed successfully'}
    
    except Exception as e:
        logger.error(f"Error changing password for {username}: {e}")
        return {'status': 'error', 'message': str(e)}


def list_users(include_system: bool = False) -> List[Dict[str, any]]:
    """
    List all users on the system.
    
    Args:
        include_system: Whether to include system users (UID < 1000)
        
    Returns:
        list: List of user information dictionaries
    """
    try:
        # Get all users from /etc/passwd
        result = subprocess.run(
            ['getent', 'passwd'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error("Failed to get user list")
            return []
        
        users = []
        metadata = load_users_metadata()
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split(':')
            if len(parts) < 7:
                continue
            
            username = parts[0]
            uid = int(parts[2])
            gid = int(parts[3])
            gecos = parts[4]
            home = parts[5]
            shell = parts[6]
            
            # Skip system users if requested
            if not include_system and uid < MIN_UID:
                continue
            
            # Get user's groups
            group_result = subprocess.run(
                ['groups', username],
                capture_output=True,
                text=True
            )
            groups = []
            if group_result.returncode == 0:
                # Format: "username : group1 group2 group3"
                groups_str = group_result.stdout.strip()
                if ':' in groups_str:
                    groups = groups_str.split(':', 1)[1].strip().split()
            
            # Get metadata if available
            user_metadata = metadata['users'].get(username, {})
            
            user_info = {
                'username': username,
                'uid': uid,
                'gid': gid,
                'full_name': gecos,
                'home': home,
                'shell': shell,
                'groups': groups,
                'role': user_metadata.get('role', 'user'),
                'in_starlight_group': STARLIGHT_GROUP in groups
            }
            
            users.append(user_info)
        
        return users
    
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return []


def update_user_metadata(username: str, role: Optional[str] = None, 
                         full_name: Optional[str] = None) -> Dict[str, any]:
    """
    Update user metadata (role, full name, etc.).
    
    Args:
        username: The username
        role: Optional new role
        full_name: Optional new full name
        
    Returns:
        dict: Result with status and message
    """
    try:
        metadata = load_users_metadata()
        
        if username not in metadata['users']:
            metadata['users'][username] = {}
        
        if role is not None:
            metadata['users'][username]['role'] = role
        
        if full_name is not None:
            metadata['users'][username]['full_name'] = full_name
            # Also update system GECOS field
            subprocess.run(
                ['usermod', '-c', full_name, username],
                capture_output=True,
                text=True
            )
        
        metadata['users'][username]['updated_at'] = subprocess.run(
            ['date', '-Iseconds'],
            capture_output=True,
            text=True
        ).stdout.strip()
        
        save_users_metadata(metadata)
        
        logger.info(f"Updated metadata for user: {username}")
        return {'status': 'success', 'message': 'User metadata updated successfully'}
    
    except Exception as e:
        logger.error(f"Error updating user metadata for {username}: {e}")
        return {'status': 'error', 'message': str(e)}


def get_user_role(username: str) -> str:
    """
    Get a user's role from metadata.
    
    The root user is automatically granted admin privileges if they don't have 
    an explicit role set in the metadata.
    
    Args:
        username: The username
        
    Returns:
        str: The user's role ('admin' or 'user')
    """
    metadata = load_users_metadata()
    
    # Check if user has an explicit role in metadata
    if username in metadata['users'] and 'role' in metadata['users'][username]:
        return metadata['users'][username]['role']
    
    # Automatically grant admin role to root user
    if username == 'root':
        logger.info(f"Granting admin role to root user")
        update_user_metadata(username, role='admin')
        return 'admin'
    
    return 'user'


def is_admin(username: str) -> bool:
    """
    Check if a user has admin role.
    
    Args:
        username: The username
        
    Returns:
        bool: True if user is admin, False otherwise
    """
    return get_user_role(username) == 'admin'
