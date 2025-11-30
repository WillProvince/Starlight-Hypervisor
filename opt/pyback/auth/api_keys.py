"""
API Key Management Module

Handles creation, validation, and management of API keys for
programmatic access to the Starlight API.
"""

import logging
import secrets
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

from ..config_loader import get_config_file_path, API_KEYS_PATH as CONFIG_API_KEYS_PATH

logger = logging.getLogger(__name__)

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    logger.warning("bcrypt not available. API key hashing will be disabled.")

# Configuration paths - use config_loader paths with fallback
def _get_api_keys_path():
    """Get the API keys path with fallback to legacy."""
    new_path = CONFIG_API_KEYS_PATH
    legacy_path = get_config_file_path('api_keys', use_legacy=True)
    
    # Return new path if it exists, otherwise check legacy
    if Path(new_path).exists():
        return new_path
    if Path(legacy_path).exists():
        return legacy_path
    # Default to new path for new installations
    return new_path

API_KEYS_PATH = _get_api_keys_path()

# API key prefix for identification
API_KEY_PREFIX = 'stl_'


def load_api_keys() -> dict:
    """Load API keys from storage file."""
    keys_path = Path(_get_api_keys_path())
    
    if not keys_path.exists():
        keys_path.parent.mkdir(parents=True, exist_ok=True)
        default_data = {'keys': []}
        save_api_keys(default_data)
        return default_data
    
    try:
        with open(keys_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading API keys: {e}")
        return {'keys': []}


def save_api_keys(data: dict):
    """Save API keys to storage file."""
    try:
        # Always save to new location
        keys_path = Path(CONFIG_API_KEYS_PATH)
        keys_path.parent.mkdir(parents=True, exist_ok=True)
        with open(keys_path, 'w') as f:
            json.dump(data, f, indent=2)
        # Set restrictive permissions
        keys_path.chmod(0o600)
    except Exception as e:
        logger.error(f"Error saving API keys: {e}")


def hash_api_key(api_key: str) -> Optional[str]:
    """
    Hash an API key using bcrypt.
    
    Args:
        api_key: The API key to hash
        
    Returns:
        str: The hashed API key, or None if bcrypt is not available
    """
    if not BCRYPT_AVAILABLE:
        logger.error("bcrypt not available - API key creation disabled for security")
        return None
    
    try:
        hashed = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt())
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error hashing API key: {e}")
        return None


def verify_api_key_hash(api_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash.
    
    Args:
        api_key: The plain text API key
        hashed_key: The hashed API key
        
    Returns:
        bool: True if the key matches, False otherwise
    """
    if not BCRYPT_AVAILABLE:
        # Fallback to plain text comparison (not secure)
        return api_key == hashed_key
    
    try:
        return bcrypt.checkpw(api_key.encode('utf-8'), hashed_key.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying API key: {e}")
        return False


def generate_api_key() -> str:
    """
    Generate a new random API key.
    
    Returns:
        str: The generated API key with prefix
    """
    # Generate a secure random token
    random_part = secrets.token_urlsafe(32)
    return f"{API_KEY_PREFIX}{random_part}"


def create_api_key(username: str, name: str, description: str = '', 
                    expires_at: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a new API key for a user.
    
    Args:
        username: The user to create the key for
        name: A friendly name for the key
        description: Optional description of the key's purpose
        expires_at: Optional expiration date (ISO format)
        
    Returns:
        dict: The created API key information (including the plain key)
    """
    # Generate the key
    api_key = generate_api_key()
    key_id = secrets.token_urlsafe(16)
    
    # Hash the key for storage
    hashed_key = hash_api_key(api_key)
    if hashed_key is None:
        logger.error("Cannot create API key: bcrypt is required but not available")
        raise RuntimeError("API key creation requires bcrypt to be installed")
    
    # Create key metadata
    key_data = {
        'id': key_id,
        'username': username,
        'name': name,
        'description': description,
        'hashed_key': hashed_key,
        'created_at': datetime.utcnow().isoformat(),
        'last_used_at': None,
        'expires_at': expires_at,
        'revoked': False
    }
    
    # Save to storage
    data = load_api_keys()
    data['keys'].append(key_data)
    save_api_keys(data)
    
    logger.info(f"Created API key '{name}' for user: {username}")
    
    # Return the key data with the plain key (only time it's visible)
    return {
        'id': key_id,
        'key': api_key,  # Plain text key - only shown once
        'name': name,
        'description': description,
        'created_at': key_data['created_at'],
        'expires_at': expires_at
    }


def verify_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """
    Verify an API key and return associated user information.
    
    Args:
        api_key: The API key to verify
        
    Returns:
        dict: User and key information if valid, None otherwise
    """
    if not api_key or not api_key.startswith(API_KEY_PREFIX):
        return None
    
    data = load_api_keys()
    
    for key_data in data['keys']:
        # Skip revoked keys
        if key_data.get('revoked', False):
            continue
        
        # Check expiration
        if key_data.get('expires_at'):
            try:
                expires = datetime.fromisoformat(key_data['expires_at'])
                if datetime.utcnow() > expires:
                    continue
            except Exception:
                pass
        
        # Verify the key
        if verify_api_key_hash(api_key, key_data['hashed_key']):
            # Update last used timestamp
            key_data['last_used_at'] = datetime.utcnow().isoformat()
            save_api_keys(data)
            
            logger.info(f"Valid API key used by user: {key_data['username']}")
            return {
                'username': key_data['username'],
                'key_id': key_data['id'],
                'key_name': key_data['name']
            }
    
    logger.warning("Invalid or revoked API key attempted")
    return None


def list_user_api_keys(username: str) -> List[Dict[str, Any]]:
    """
    List all API keys for a user (without the actual keys).
    
    Args:
        username: The username to list keys for
        
    Returns:
        list: List of API key metadata
    """
    data = load_api_keys()
    user_keys = []
    
    for key_data in data['keys']:
        if key_data['username'] == username:
            # Return metadata without the hashed key
            user_keys.append({
                'id': key_data['id'],
                'name': key_data['name'],
                'description': key_data['description'],
                'created_at': key_data['created_at'],
                'last_used_at': key_data['last_used_at'],
                'expires_at': key_data.get('expires_at'),
                'revoked': key_data.get('revoked', False),
                'key_preview': f"{API_KEY_PREFIX}{'*' * 40}"  # Masked key
            })
    
    return user_keys


def revoke_api_key(key_id: str, username: str) -> bool:
    """
    Revoke an API key.
    
    Args:
        key_id: The ID of the key to revoke
        username: The username of the key owner (for authorization)
        
    Returns:
        bool: True if successfully revoked, False otherwise
    """
    data = load_api_keys()
    
    for key_data in data['keys']:
        if key_data['id'] == key_id and key_data['username'] == username:
            key_data['revoked'] = True
            key_data['revoked_at'] = datetime.utcnow().isoformat()
            save_api_keys(data)
            logger.info(f"Revoked API key '{key_data['name']}' for user: {username}")
            return True
    
    logger.warning(f"Failed to revoke API key {key_id} for user: {username}")
    return False


def delete_api_key(key_id: str, username: str) -> bool:
    """
    Delete an API key permanently.
    
    Args:
        key_id: The ID of the key to delete
        username: The username of the key owner (for authorization)
        
    Returns:
        bool: True if successfully deleted, False otherwise
    """
    data = load_api_keys()
    
    original_count = len(data['keys'])
    data['keys'] = [k for k in data['keys'] 
                    if not (k['id'] == key_id and k['username'] == username)]
    
    if len(data['keys']) < original_count:
        save_api_keys(data)
        logger.info(f"Deleted API key {key_id} for user: {username}")
        return True
    
    logger.warning(f"Failed to delete API key {key_id} for user: {username}")
    return False


def update_api_key(key_id: str, username: str, name: Optional[str] = None, 
                    description: Optional[str] = None) -> bool:
    """
    Update API key metadata.
    
    Args:
        key_id: The ID of the key to update
        username: The username of the key owner (for authorization)
        name: Optional new name
        description: Optional new description
        
    Returns:
        bool: True if successfully updated, False otherwise
    """
    data = load_api_keys()
    
    for key_data in data['keys']:
        if key_data['id'] == key_id and key_data['username'] == username:
            if name is not None:
                key_data['name'] = name
            if description is not None:
                key_data['description'] = description
            key_data['updated_at'] = datetime.utcnow().isoformat()
            save_api_keys(data)
            logger.info(f"Updated API key {key_id} for user: {username}")
            return True
    
    logger.warning(f"Failed to update API key {key_id} for user: {username}")
    return False
