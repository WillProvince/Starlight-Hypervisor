"""
Authentication HTTP Handlers

Handles HTTP requests for authentication, user management, and API key management.
"""

import logging
from aiohttp import web

from pyback.auth.pam_auth import authenticate_user, user_exists, get_user_info
from pyback.auth.jwt_auth import generate_token, verify_token, refresh_token
from pyback.auth.api_keys import (
    create_api_key, list_user_api_keys, revoke_api_key, 
    delete_api_key, update_api_key
)
from pyback.auth.user_management import (
    create_user, delete_user, change_password, list_users,
    update_user_metadata, is_admin
)
from pyback.auth.middleware import get_current_user, get_username, require_admin

logger = logging.getLogger(__name__)


# --- Authentication Endpoints ---

async def login(request: web.Request) -> web.Response:
    """
    Handle user login with username/password.
    
    POST /api/auth/login
    Body: {"username": "user", "password": "pass"}
    """
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return web.json_response(
                {
                    'status': 'error',
                    'message': 'Username and password are required'
                },
                status=400
            )
        
        # Authenticate with PAM
        if not authenticate_user(username, password):
            logger.warning(f"Failed login attempt for user: {username}")
            return web.json_response(
                {
                    'status': 'error',
                    'message': 'Invalid username or password'
                },
                status=401
            )
        
        # Check if user is in starlight-users group or is admin
        from pyback.auth.pam_auth import is_user_in_group
        from pyback.auth.user_management import STARLIGHT_GROUP
        
        if not is_user_in_group(username, STARLIGHT_GROUP) and not is_admin(username):
            logger.warning(f"User {username} not authorized for Starlight access")
            return web.json_response(
                {
                    'status': 'error',
                    'message': 'User not authorized for Starlight access'
                },
                status=403
            )
        
        # Generate JWT token
        token = generate_token(username, {'role': 'admin' if is_admin(username) else 'user'})
        
        if not token:
            return web.json_response(
                {
                    'status': 'error',
                    'message': 'Failed to generate authentication token'
                },
                status=500
            )
        
        logger.info(f"Successful login for user: {username}")
        
        # Get user info
        user_info = get_user_info(username)
        
        return web.json_response(
            {
                'status': 'success',
                'message': 'Login successful',
                'token': token,
                'user': {
                    'username': username,
                    'role': 'admin' if is_admin(username) else 'user',
                    'uid': user_info.get('uid') if user_info else None
                }
            }
        )
    
    except Exception as e:
        logger.error(f"Error during login: {e}")
        return web.json_response(
            {
                'status': 'error',
                'message': 'An error occurred during login'
            },
            status=500
        )


async def logout(request: web.Request) -> web.Response:
    """
    Handle user logout.
    
    POST /api/auth/logout
    """
    # In a stateless JWT system, logout is handled client-side by removing the token
    # We just log the event
    user = get_current_user(request)
    if user:
        logger.info(f"User logged out: {user['username']}")
    
    return web.json_response(
        {
            'status': 'success',
            'message': 'Logged out successfully'
        }
    )


async def verify(request: web.Request) -> web.Response:
    """
    Verify current authentication status.
    
    GET /api/auth/verify
    """
    user = get_current_user(request)
    
    if not user:
        return web.json_response(
            {
                'status': 'error',
                'authenticated': False,
                'message': 'Not authenticated'
            },
            status=401
        )
    
    return web.json_response(
        {
            'status': 'success',
            'authenticated': True,
            'user': {
                'username': user['username'],
                'auth_type': user['auth_type'],
                'role': 'admin' if is_admin(user['username']) else 'user'
            }
        }
    )


async def refresh(request: web.Request) -> web.Response:
    """
    Refresh JWT token.
    
    POST /api/auth/refresh
    """
    user = get_current_user(request)
    
    if not user or user['auth_type'] != 'jwt':
        return web.json_response(
            {
                'status': 'error',
                'message': 'Invalid token for refresh'
            },
            status=401
        )
    
    # Extract old token
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return web.json_response(
            {
                'status': 'error',
                'message': 'Invalid authorization header'
            },
            status=400
        )
    
    old_token = auth_header[7:]
    new_token = refresh_token(old_token)
    
    if not new_token:
        return web.json_response(
            {
                'status': 'error',
                'message': 'Failed to refresh token'
            },
            status=500
        )
    
    return web.json_response(
        {
            'status': 'success',
            'token': new_token
        }
    )


# --- User Management Endpoints ---

@require_admin
async def get_users(request: web.Request) -> web.Response:
    """
    List all users (admin only).
    
    GET /api/users
    """
    try:
        users = list_users(include_system=False)
        
        return web.json_response(
            {
                'status': 'success',
                'users': users
            }
        )
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return web.json_response(
            {
                'status': 'error',
                'message': 'Failed to list users'
            },
            status=500
        )


@require_admin
async def add_user(request: web.Request) -> web.Response:
    """
    Create a new user (admin only).
    
    POST /api/users
    Body: {"username": "user", "password": "pass", "role": "user", "full_name": "Full Name"}
    """
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        role = data.get('role', 'user')
        full_name = data.get('full_name', '')
        
        if not username or not password:
            return web.json_response(
                {
                    'status': 'error',
                    'message': 'Username and password are required'
                },
                status=400
            )
        
        if user_exists(username):
            return web.json_response(
                {
                    'status': 'error',
                    'message': f'User {username} already exists'
                },
                status=409
            )
        
        result = create_user(username, password, role, full_name)
        
        if result['status'] == 'success':
            return web.json_response(result, status=201)
        else:
            return web.json_response(result, status=400)
    
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return web.json_response(
            {
                'status': 'error',
                'message': 'Failed to create user'
            },
            status=500
        )


async def modify_user(request: web.Request) -> web.Response:
    """
    Update user information (admin or self).
    
    PUT /api/users/{username}
    Body: {"role": "admin", "full_name": "New Name"}
    """
    try:
        target_username = request.match_info['username']
        current_user = get_current_user(request)
        
        if not current_user:
            return web.json_response(
                {'status': 'error', 'message': 'Authentication required'},
                status=401
            )
        
        # Check permissions (admin or self)
        if target_username != current_user['username'] and not is_admin(current_user['username']):
            return web.json_response(
                {'status': 'error', 'message': 'Permission denied'},
                status=403
            )
        
        data = await request.json()
        role = data.get('role')
        full_name = data.get('full_name')
        
        # Only admin can change roles
        if role and not is_admin(current_user['username']):
            return web.json_response(
                {'status': 'error', 'message': 'Only admins can change user roles'},
                status=403
            )
        
        result = update_user_metadata(target_username, role, full_name)
        
        if result['status'] == 'success':
            return web.json_response(result)
        else:
            return web.json_response(result, status=400)
    
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return web.json_response(
            {'status': 'error', 'message': 'Failed to update user'},
            status=500
        )


@require_admin
async def remove_user(request: web.Request) -> web.Response:
    """
    Delete a user (admin only).
    
    DELETE /api/users/{username}
    """
    try:
        username = request.match_info['username']
        
        if not user_exists(username):
            return web.json_response(
                {'status': 'error', 'message': f'User {username} does not exist'},
                status=404
            )
        
        result = delete_user(username, remove_home=True)
        
        if result['status'] == 'success':
            return web.json_response(result)
        else:
            return web.json_response(result, status=400)
    
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return web.json_response(
            {'status': 'error', 'message': 'Failed to delete user'},
            status=500
        )


async def change_user_password(request: web.Request) -> web.Response:
    """
    Change user password (admin or self).
    
    POST /api/users/{username}/password
    Body: {"new_password": "newpass", "current_password": "oldpass"}
    """
    try:
        target_username = request.match_info['username']
        current_user = get_current_user(request)
        
        if not current_user:
            return web.json_response(
                {'status': 'error', 'message': 'Authentication required'},
                status=401
            )
        
        data = await request.json()
        new_password = data.get('new_password', '')
        current_password = data.get('current_password', '')
        
        if not new_password:
            return web.json_response(
                {'status': 'error', 'message': 'New password is required'},
                status=400
            )
        
        # Check permissions
        is_self = target_username == current_user['username']
        is_user_admin = is_admin(current_user['username'])
        
        if not is_self and not is_user_admin:
            return web.json_response(
                {'status': 'error', 'message': 'Permission denied'},
                status=403
            )
        
        # If changing own password, verify current password
        if is_self and not is_user_admin:
            if not current_password:
                return web.json_response(
                    {'status': 'error', 'message': 'Current password is required'},
                    status=400
                )
            if not authenticate_user(target_username, current_password):
                return web.json_response(
                    {'status': 'error', 'message': 'Current password is incorrect'},
                    status=401
                )
        
        result = change_password(target_username, new_password)
        
        if result['status'] == 'success':
            return web.json_response(result)
        else:
            return web.json_response(result, status=400)
    
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return web.json_response(
            {'status': 'error', 'message': 'Failed to change password'},
            status=500
        )


# --- API Key Management Endpoints ---

async def get_api_keys(request: web.Request) -> web.Response:
    """
    List current user's API keys.
    
    GET /api/auth/api-keys
    """
    try:
        username = get_username(request)
        if not username:
            return web.json_response(
                {'status': 'error', 'message': 'Authentication required'},
                status=401
            )
        
        keys = list_user_api_keys(username)
        
        return web.json_response(
            {
                'status': 'success',
                'api_keys': keys
            }
        )
    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        return web.json_response(
            {'status': 'error', 'message': 'Failed to list API keys'},
            status=500
        )


async def create_new_api_key(request: web.Request) -> web.Response:
    """
    Generate a new API key.
    
    POST /api/auth/api-keys
    Body: {"name": "My Key", "description": "For CI/CD", "expires_at": "2025-12-31T23:59:59"}
    """
    try:
        username = get_username(request)
        if not username:
            return web.json_response(
                {'status': 'error', 'message': 'Authentication required'},
                status=401
            )
        
        data = await request.json()
        name = data.get('name', '').strip()
        description = data.get('description', '')
        expires_at = data.get('expires_at')
        
        if not name:
            return web.json_response(
                {'status': 'error', 'message': 'API key name is required'},
                status=400
            )
        
        try:
            key_info = create_api_key(username, name, description, expires_at)
        except RuntimeError as e:
            return web.json_response(
                {'status': 'error', 'message': str(e)},
                status=503  # Service Unavailable
            )
        
        return web.json_response(
            {
                'status': 'success',
                'message': 'API key created successfully. Save it now - it won\'t be shown again!',
                'api_key': key_info
            },
            status=201
        )
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        return web.json_response(
            {'status': 'error', 'message': 'Failed to create API key'},
            status=500
        )


async def delete_user_api_key(request: web.Request) -> web.Response:
    """
    Revoke/delete an API key.
    
    DELETE /api/auth/api-keys/{key_id}
    """
    try:
        username = get_username(request)
        if not username:
            return web.json_response(
                {'status': 'error', 'message': 'Authentication required'},
                status=401
            )
        
        key_id = request.match_info['key_id']
        
        success = delete_api_key(key_id, username)
        
        if success:
            return web.json_response(
                {'status': 'success', 'message': 'API key deleted successfully'}
            )
        else:
            return web.json_response(
                {'status': 'error', 'message': 'Failed to delete API key or key not found'},
                status=404
            )
    except Exception as e:
        logger.error(f"Error deleting API key: {e}")
        return web.json_response(
            {'status': 'error', 'message': 'Failed to delete API key'},
            status=500
        )


async def modify_api_key(request: web.Request) -> web.Response:
    """
    Update API key metadata.
    
    PUT /api/auth/api-keys/{key_id}
    Body: {"name": "New Name", "description": "New Description"}
    """
    try:
        username = get_username(request)
        if not username:
            return web.json_response(
                {'status': 'error', 'message': 'Authentication required'},
                status=401
            )
        
        key_id = request.match_info['key_id']
        data = await request.json()
        name = data.get('name')
        description = data.get('description')
        
        success = update_api_key(key_id, username, name, description)
        
        if success:
            return web.json_response(
                {'status': 'success', 'message': 'API key updated successfully'}
            )
        else:
            return web.json_response(
                {'status': 'error', 'message': 'Failed to update API key or key not found'},
                status=404
            )
    except Exception as e:
        logger.error(f"Error updating API key: {e}")
        return web.json_response(
            {'status': 'error', 'message': 'Failed to update API key'},
            status=500
        )
