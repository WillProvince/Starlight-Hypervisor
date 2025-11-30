"""
Repository management API handlers.

This module provides HTTP request handlers for managing VM/LXC template repositories.
"""

import json
import logging
from aiohttp import web

from .vm_deployment import (
    load_repositories_config, 
    save_repositories_config, 
    fetch_repository_apps
)

logger = logging.getLogger(__name__)


async def list_repositories(request):
    """Returns the list of configured repositories."""
    config = load_repositories_config()
    return web.json_response({'status': 'success', 'repositories': config.get('repositories', [])})


async def get_all_apps(request):
    """Fetches and aggregates apps from all enabled repositories."""
    config = load_repositories_config()
    all_apps = []
    
    # Fetch apps from all enabled repositories
    for repo in config.get('repositories', []):
        if repo.get('enabled', False):
            apps = await fetch_repository_apps(repo['url'])
            if apps:
                # Add repository metadata to each app
                for app in apps:
                    app['repo_id'] = repo['id']
                    app['repo_name'] = repo['name']
                all_apps.extend(apps)
    
    return web.json_response({'status': 'success', 'apps': all_apps, 'total': len(all_apps)})


async def add_repository(request):
    """Adds a new repository to the configuration."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({'status': 'error', 'message': 'Invalid JSON body.'}, status=400)
    
    repo_id = data.get('id')
    name = data.get('name')
    url = data.get('url')
    
    if not all([repo_id, name, url]):
        return web.json_response({'status': 'error', 'message': 'Missing required fields: id, name, url'}, status=400)
    
    config = load_repositories_config()
    
    # Check if repo_id already exists
    for repo in config['repositories']:
        if repo['id'] == repo_id:
            return web.json_response({'status': 'error', 'message': f'Repository with id {repo_id} already exists.'}, status=409)
    
    # Add new repository
    new_repo = {
        'id': repo_id,
        'name': name,
        'url': url,
        'enabled': data.get('enabled', True),
        'description': data.get('description', '')
    }
    config['repositories'].append(new_repo)
    
    if save_repositories_config(config):
        return web.json_response({'status': 'success', 'message': f'Repository {name} added successfully.', 'repository': new_repo})
    else:
        return web.json_response({'status': 'error', 'message': 'Failed to save configuration.'}, status=500)


async def update_repository(request):
    """Updates an existing repository (enable/disable, change URL, etc.)."""
    repo_id = request.match_info.get('id')
    
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({'status': 'error', 'message': 'Invalid JSON body.'}, status=400)
    
    config = load_repositories_config()
    
    # Find and update the repository
    for repo in config['repositories']:
        if repo['id'] == repo_id:
            if 'name' in data:
                repo['name'] = data['name']
            if 'url' in data:
                repo['url'] = data['url']
            if 'enabled' in data:
                repo['enabled'] = data['enabled']
            if 'description' in data:
                repo['description'] = data['description']
            
            if save_repositories_config(config):
                return web.json_response({'status': 'success', 'message': f'Repository {repo_id} updated successfully.', 'repository': repo})
            else:
                return web.json_response({'status': 'error', 'message': 'Failed to save configuration.'}, status=500)
    
    return web.json_response({'status': 'error', 'message': f'Repository {repo_id} not found.'}, status=404)


async def delete_repository(request):
    """Removes a repository from the configuration."""
    repo_id = request.match_info.get('id')
    
    config = load_repositories_config()
    
    # Find and remove the repository
    original_length = len(config['repositories'])
    config['repositories'] = [repo for repo in config['repositories'] if repo['id'] != repo_id]
    
    if len(config['repositories']) == original_length:
        return web.json_response({'status': 'error', 'message': f'Repository {repo_id} not found.'}, status=404)
    
    if save_repositories_config(config):
        return web.json_response({'status': 'success', 'message': f'Repository {repo_id} removed successfully.'})
    else:
        return web.json_response({'status': 'error', 'message': 'Failed to save configuration.'}, status=500)
