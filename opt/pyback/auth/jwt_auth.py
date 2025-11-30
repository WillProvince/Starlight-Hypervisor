"""
JWT Token Authentication Module

Handles JWT token generation, validation, and session management
for web UI authentication.
"""

import logging
import secrets
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

from ..config_loader import (
    get_config_file_path, 
    AUTH_CONFIG_PATH as CONFIG_AUTH_PATH,
    DEFAULT_AUTH_CONFIG
)

logger = logging.getLogger(__name__)

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logger.warning("PyJWT not available. JWT authentication will be disabled.")

# Configuration paths - use config_loader paths with fallback
def _get_auth_config_path():
    """Get the auth config path with fallback to legacy."""
    new_path = CONFIG_AUTH_PATH
    legacy_path = get_config_file_path('auth', use_legacy=True)
    
    # Return new path if it exists, otherwise check legacy
    if Path(new_path).exists():
        return new_path
    if Path(legacy_path).exists():
        return legacy_path
    # Default to new path for new installations
    return new_path

AUTH_CONFIG_PATH = _get_auth_config_path()


def load_auth_config() -> dict:
    """Load authentication configuration from file."""
    config_path = Path(_get_auth_config_path())
    
    # Create default config if it doesn't exist
    if not config_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = DEFAULT_AUTH_CONFIG.copy()
        # Generate a secure JWT secret
        config['jwt_secret'] = secrets.token_urlsafe(64)
        save_auth_config(config)
        logger.info("Created new authentication configuration with generated JWT secret")
        return config
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            # Ensure JWT secret exists
            if not config.get('jwt_secret'):
                config['jwt_secret'] = secrets.token_urlsafe(64)
                save_auth_config(config)
            return config
    except Exception as e:
        logger.error(f"Error loading auth config: {e}")
        return DEFAULT_AUTH_CONFIG


def save_auth_config(config: dict):
    """Save authentication configuration to file."""
    try:
        # Always save to new location
        config_path = Path(CONFIG_AUTH_PATH)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        # Set restrictive permissions
        config_path.chmod(0o600)
    except Exception as e:
        logger.error(f"Error saving auth config: {e}")


def generate_token(username: str, additional_claims: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Generate a JWT token for a user.
    
    Args:
        username: The username to create a token for
        additional_claims: Optional additional claims to include in the token
        
    Returns:
        str: The JWT token, or None if JWT is not available
    """
    if not JWT_AVAILABLE:
        logger.error("JWT is not available (PyJWT not installed)")
        return None
    
    try:
        config = load_auth_config()
        
        # Token payload
        now = datetime.utcnow()
        expiration = now + timedelta(hours=config.get('session_timeout_hours', 24))
        
        payload = {
            'username': username,
            'iat': now,
            'exp': expiration,
            'jti': secrets.token_urlsafe(16)  # Unique token ID
        }
        
        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)
        
        # Generate token
        token = jwt.encode(
            payload,
            config['jwt_secret'],
            algorithm=config.get('jwt_algorithm', 'HS256')
        )
        
        logger.info(f"Generated JWT token for user: {username}")
        return token
    except Exception as e:
        logger.error(f"Error generating JWT token: {e}")
        return None


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        dict: The decoded token payload, or None if invalid
    """
    if not JWT_AVAILABLE:
        logger.error("JWT is not available (PyJWT not installed)")
        return None
    
    try:
        config = load_auth_config()
        
        payload = jwt.decode(
            token,
            config['jwt_secret'],
            algorithms=[config.get('jwt_algorithm', 'HS256')]
        )
        
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token verification failed: token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("JWT token verification failed: invalid token")
        return None
    except Exception as e:
        logger.error(f"JWT token verification failed: {type(e).__name__}")
        return None


def refresh_token(old_token: str) -> Optional[str]:
    """
    Refresh a JWT token (generate a new one with updated expiration).
    
    Args:
        old_token: The current JWT token
        
    Returns:
        str: A new JWT token, or None if the old token is invalid
    """
    payload = verify_token(old_token)
    if not payload:
        return None
    
    # Extract username and any custom claims
    username = payload.get('username')
    if not username:
        return None
    
    # Remove standard JWT claims before passing as additional claims
    custom_claims = {k: v for k, v in payload.items() 
                     if k not in ['username', 'iat', 'exp', 'jti']}
    
    # Generate new token
    return generate_token(username, custom_claims if custom_claims else None)


def decode_token_without_verification(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without verification (useful for expired tokens).
    
    Args:
        token: The JWT token to decode
        
    Returns:
        dict: The decoded token payload, or None if invalid
    """
    if not JWT_AVAILABLE:
        return None
    
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload
    except Exception as e:
        logger.error(f"Error decoding JWT token: {e}")
        return None
