"""
Authentication Middleware Module

Provides aiohttp middleware to protect API endpoints with
JWT token or API key authentication.
"""

import logging
from aiohttp import web
from typing import Callable, List, Optional
from .jwt_auth import verify_token
from .api_keys import verify_api_key

logger = logging.getLogger(__name__)

# Endpoints that don't require authentication
PUBLIC_ENDPOINTS = [
    '/api/auth/login',
    '/api/auth/verify',  # Needs to check but not block
    '/api/firstrun',
]

# Endpoints that can use public access (for initial setup)
OPTIONAL_AUTH_ENDPOINTS = []


def extract_token_from_request(request: web.Request) -> Optional[str]:
    """
    Extract authentication token from request headers or query parameters.
    
    Checks (in order):
    1. Authorization: Bearer <token>
    2. X-API-Key: <key>
    3. Query parameter: token=<token> (for WebSocket connections)
    
    Args:
        request: The aiohttp request object
        
    Returns:
        tuple: (token, token_type) where token_type is 'jwt' or 'api_key'
    """
    # Check Authorization header for Bearer token (JWT)
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        return (token, 'jwt')
    
    # Check X-API-Key header
    api_key = request.headers.get('X-API-Key', '')
    if api_key:
        return (api_key, 'api_key')
    
    # Check query parameter for token (used by WebSocket connections)
    token = request.query.get('token', '')
    if token:
        return (token, 'jwt')
    
    return (None, None)


def is_public_endpoint(path: str) -> bool:
    """Check if an endpoint is public (doesn't require auth)."""
    for public_path in PUBLIC_ENDPOINTS:
        if path == public_path or path.startswith(public_path + '/'):
            return True
    return False


def is_optional_auth_endpoint(path: str) -> bool:
    """Check if an endpoint has optional authentication."""
    for optional_path in OPTIONAL_AUTH_ENDPOINTS:
        if path == optional_path or path.startswith(optional_path + '/'):
            return True
    return False


async def authenticate_request(request: web.Request) -> Optional[dict]:
    """
    Authenticate a request using JWT or API key.
    
    Args:
        request: The aiohttp request object
        
    Returns:
        dict: User information if authenticated, None otherwise
    """
    token, token_type = extract_token_from_request(request)
    
    if not token:
        return None
    
    if token_type == 'jwt':
        # Verify JWT token
        payload = verify_token(token)
        if payload:
            return {
                'username': payload.get('username'),
                'auth_type': 'jwt',
                'token_payload': payload
            }
    
    elif token_type == 'api_key':
        # Verify API key
        key_info = verify_api_key(token)
        if key_info:
            return {
                'username': key_info['username'],
                'auth_type': 'api_key',
                'key_id': key_info['key_id'],
                'key_name': key_info['key_name']
            }
    
    return None


@web.middleware
async def auth_middleware(request: web.Request, handler: Callable) -> web.Response:
    """
    Authentication middleware for aiohttp.
    
    Checks authentication for all non-public endpoints.
    Attaches user information to request if authenticated.
    
    Args:
        request: The aiohttp request object
        handler: The request handler
        
    Returns:
        web.Response: The response from the handler or an error response
    """
    # Check if endpoint is public
    if is_public_endpoint(request.path):
        # Still try to authenticate but don't block
        user_info = await authenticate_request(request)
        if user_info:
            request['user'] = user_info
        return await handler(request)
    
    # Check if endpoint has optional authentication
    if is_optional_auth_endpoint(request.path):
        user_info = await authenticate_request(request)
        if user_info:
            request['user'] = user_info
        return await handler(request)
    
    # For all other endpoints, require authentication
    user_info = await authenticate_request(request)
    
    if not user_info:
        logger.warning(f"Unauthorized access attempt to {request.path}")
        return web.json_response(
            {
                'status': 'error',
                'message': 'Authentication required. Please provide a valid JWT token or API key.'
            },
            status=401
        )
    
    # Attach user info to request for use in handlers
    request['user'] = user_info
    
    # Log authenticated access
    logger.debug(f"Authenticated request to {request.path} by {user_info['username']} via {user_info['auth_type']}")
    
    # Call the handler
    return await handler(request)


def require_admin(handler: Callable) -> Callable:
    """
    Decorator to require admin role for a handler.
    
    Usage:
        @require_admin
        async def admin_only_handler(request):
            ...
    """
    async def wrapper(request: web.Request) -> web.Response:
        user_info = request.get('user')
        
        if not user_info:
            return web.json_response(
                {
                    'status': 'error',
                    'message': 'Authentication required'
                },
                status=401
            )
        
        # Check if user is admin
        from .user_management import is_admin
        if not is_admin(user_info['username']):
            logger.warning(f"User {user_info['username']} attempted to access admin-only endpoint: {request.path}")
            return web.json_response(
                {
                    'status': 'error',
                    'message': 'Admin privileges required'
                },
                status=403
            )
        
        return await handler(request)
    
    return wrapper


def get_current_user(request: web.Request) -> Optional[dict]:
    """
    Get the current authenticated user from the request.
    
    Args:
        request: The aiohttp request object
        
    Returns:
        dict: User information if authenticated, None otherwise
    """
    return request.get('user')


def get_username(request: web.Request) -> Optional[str]:
    """
    Get the current authenticated username from the request.
    
    Args:
        request: The aiohttp request object
        
    Returns:
        str: Username if authenticated, None otherwise
    """
    user = get_current_user(request)
    return user.get('username') if user else None
