"""
File synchronization functions for Starlight updates.

This module provides functions for syncing files from the git repository
to their system locations after updates.
"""

import os
import shutil
import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Files/patterns to never sync (preserve user data and git internals)
EXCLUDE_PATTERNS = [
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '.git',
    '.gitignore',
    '*.backup',
    '*.bak',
    '.DS_Store',
    'README.md',
    'LICENSE',
    '.github',
]

# Config files that should never be overwritten if they exist
PRESERVE_CONFIG_FILES = [
    'users.json',
    'api_keys.json',
    'auth.json',
    'storage.json',
    'system.json',
    'update.json',
    'updater.json',
    'network.json',
    'vm_metadata.json',
    'lxc_metadata.json',
    'repositories.json',
]


def _should_exclude(path: str) -> bool:
    """
    Check if a path should be excluded from sync.
    
    Args:
        path: The file or directory path to check
        
    Returns:
        bool: True if the path should be excluded
    """
    import fnmatch
    
    basename = os.path.basename(path)
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(basename, pattern):
            return True
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def _should_preserve_config(filepath: str) -> bool:
    """
    Check if a config file should be preserved (not overwritten).
    
    Args:
        filepath: The file path to check
        
    Returns:
        bool: True if the file should be preserved
    """
    basename = os.path.basename(filepath)
    return basename in PRESERVE_CONFIG_FILES


def _calculate_file_hash(filepath: str) -> str:
    """
    Calculate SHA256 hash of a file.
    
    Args:
        filepath: Path to the file
        
    Returns:
        str: Hex digest of the file hash
    """
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        logger.error(f"Error calculating hash for {filepath}: {e}")
        return ''


def _get_file_permissions(filepath: str) -> int:
    """
    Determine appropriate permissions for a file.
    
    Args:
        filepath: Path to the file
        
    Returns:
        int: File permission mode (e.g., 0o755 or 0o644)
    """
    # Check if file is executable (shell scripts, etc.)
    basename = os.path.basename(filepath)
    
    # Executable patterns
    if filepath.endswith('.sh'):
        return 0o755
    if filepath.endswith('.py') and basename.startswith('main'):
        return 0o755
    if '/scripts/' in filepath:
        return 0o755
    
    # Config files
    if filepath.endswith('.json') or filepath.endswith('.conf'):
        return 0o644
    
    # HTML/CSS/JS files
    if any(filepath.endswith(ext) for ext in ['.html', '.css', '.js']):
        return 0o644
    
    # Default for most files
    return 0o644


def sync_file(src: str, dst: str, preserve_existing: bool = False) -> Dict:
    """
    Sync a single file from source to destination.
    
    Args:
        src: Source file path
        dst: Destination file path
        preserve_existing: If True, don't overwrite existing files
        
    Returns:
        dict: Result with status information
    """
    result = {
        'src': src,
        'dst': dst,
        'synced': False,
        'action': None,
        'error': None
    }
    
    try:
        # Check if source exists
        if not os.path.exists(src):
            result['error'] = f"Source file does not exist: {src}"
            return result
        
        # Check if we should preserve existing
        if preserve_existing and os.path.exists(dst):
            result['action'] = 'preserved'
            result['synced'] = True
            return result
        
        # Create destination directory if needed
        dst_dir = os.path.dirname(dst)
        if dst_dir:
            Path(dst_dir).mkdir(parents=True, exist_ok=True)
        
        # Check if file has changed
        if os.path.exists(dst):
            src_hash = _calculate_file_hash(src)
            dst_hash = _calculate_file_hash(dst)
            if src_hash and dst_hash and src_hash == dst_hash:
                result['action'] = 'unchanged'
                result['synced'] = True
                return result
        
        # Copy file
        shutil.copy2(src, dst)
        
        # Set permissions
        permissions = _get_file_permissions(dst)
        os.chmod(dst, permissions)
        
        result['action'] = 'updated' if os.path.exists(dst) else 'created'
        result['synced'] = True
        
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"Error syncing {src} to {dst}: {e}")
    
    return result


def sync_directory(
    src_dir: str,
    dst_dir: str,
    preserve_configs: bool = False
) -> Dict:
    """
    Sync a directory from source to destination.
    
    Args:
        src_dir: Source directory path
        dst_dir: Destination directory path
        preserve_configs: If True, don't overwrite config files
        
    Returns:
        dict: Result with sync statistics
    """
    result = {
        'src_dir': src_dir,
        'dst_dir': dst_dir,
        'files_synced': 0,
        'files_created': 0,
        'files_updated': 0,
        'files_unchanged': 0,
        'files_preserved': 0,
        'files_skipped': 0,
        'errors': []
    }
    
    if not os.path.isdir(src_dir):
        result['errors'].append(f"Source directory does not exist: {src_dir}")
        return result
    
    try:
        # Create destination if it doesn't exist
        Path(dst_dir).mkdir(parents=True, exist_ok=True)
        
        # Walk through source directory
        for root, dirs, files in os.walk(src_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if not _should_exclude(d)]
            
            # Calculate relative path
            rel_path = os.path.relpath(root, src_dir)
            dst_subdir = os.path.join(dst_dir, rel_path) if rel_path != '.' else dst_dir
            
            for filename in files:
                if _should_exclude(filename):
                    result['files_skipped'] += 1
                    continue
                
                src_file = os.path.join(root, filename)
                dst_file = os.path.join(dst_subdir, filename)
                
                # Determine if we should preserve this file
                preserve = preserve_configs and _should_preserve_config(filename)
                
                sync_result = sync_file(src_file, dst_file, preserve_existing=preserve)
                
                if sync_result['synced']:
                    result['files_synced'] += 1
                    action = sync_result['action']
                    if action == 'created':
                        result['files_created'] += 1
                    elif action == 'updated':
                        result['files_updated'] += 1
                    elif action == 'unchanged':
                        result['files_unchanged'] += 1
                    elif action == 'preserved':
                        result['files_preserved'] += 1
                elif sync_result['error']:
                    result['errors'].append(sync_result['error'])
    
    except Exception as e:
        result['errors'].append(str(e))
        logger.error(f"Error syncing directory {src_dir}: {e}")
    
    return result


def sync_repo_to_system(repo_path: str, sync_mappings: Optional[Dict[str, str]] = None) -> Dict:
    """
    Sync all files from git repository to system locations.
    
    Files in the repository are mapped to the root filesystem based on their
    relative paths. For example:
    - repo/opt/pyback/ -> /opt/pyback/
    - repo/var/www/html/ -> /var/www/html/
    - repo/etc/starlight/ -> /etc/starlight/
    
    Args:
        repo_path: Path to the git repository
        sync_mappings: Optional custom sync mappings (repo_relative_path -> system_path).
                       If None, syncs all directories from repo to root (/).
        
    Returns:
        dict: Overall sync result with statistics
    """
    result = {
        'success': True,
        'total_files_synced': 0,
        'total_files_created': 0,
        'total_files_updated': 0,
        'total_files_unchanged': 0,
        'total_files_preserved': 0,
        'directories_synced': [],
        'errors': []
    }
    
    if not os.path.isdir(repo_path):
        result['errors'].append(f"Repository path does not exist: {repo_path}")
        result['success'] = False
        return result
    
    # If custom mappings provided, use those
    if sync_mappings:
        for repo_rel_path, system_path in sync_mappings.items():
            src_dir = os.path.join(repo_path, repo_rel_path)
            
            if not os.path.exists(src_dir):
                logger.warning(f"Source directory does not exist, skipping: {src_dir}")
                continue
            
            logger.info(f"Syncing {src_dir} -> {system_path}")
            
            # Preserve configs in etc directories
            preserve_configs = '/etc/' in system_path
            sync_result = sync_directory(src_dir, system_path, preserve_configs=preserve_configs)
            
            _update_result_stats(result, sync_result, src_dir, system_path, preserve_configs)
    else:
        # Default behavior: sync entire repo structure to root
        # Walk through top-level directories in the repo
        for item in os.listdir(repo_path):
            if _should_exclude(item):
                continue
            
            src_path = os.path.join(repo_path, item)
            
            # Only sync directories that map to system paths
            if os.path.isdir(src_path):
                # Map repo paths to system paths (e.g., opt/pyback -> /opt/pyback)
                system_path = '/' + item
                
                logger.info(f"Syncing {src_path} -> {system_path}")
                
                # Preserve configs in etc directories
                preserve_configs = item == 'etc'
                sync_result = sync_directory(src_path, system_path, preserve_configs=preserve_configs)
                
                _update_result_stats(result, sync_result, src_path, system_path, preserve_configs)
    
    if result['errors']:
        result['success'] = False
    
    return result


def _update_result_stats(result: Dict, sync_result: Dict, src_dir: str, system_path: str, preserve_configs: bool):
    """Helper to update result statistics from a sync operation."""
    result['total_files_synced'] += sync_result['files_synced']
    result['total_files_created'] += sync_result['files_created']
    result['total_files_updated'] += sync_result['files_updated']
    result['total_files_unchanged'] += sync_result['files_unchanged']
    result['total_files_preserved'] += sync_result['files_preserved']
    result['directories_synced'].append({
        'src': src_dir,
        'dst': system_path,
        'stats': sync_result,
        'preserve_configs': preserve_configs
    })
    
    if sync_result['errors']:
        result['errors'].extend(sync_result['errors'])


def validate_sync(repo_path: str, system_path: str) -> Dict:
    """
    Validate that a sync was successful by comparing hashes.
    
    Args:
        repo_path: Path in the repository
        system_path: System path to validate
        
    Returns:
        dict: Validation result
    """
    result = {
        'valid': True,
        'files_checked': 0,
        'files_matched': 0,
        'files_mismatched': [],
        'errors': []
    }
    
    if not os.path.isdir(repo_path):
        result['valid'] = False
        result['errors'].append(f"Repository path does not exist: {repo_path}")
        return result
    
    if not os.path.isdir(system_path):
        result['valid'] = False
        result['errors'].append(f"System path does not exist: {system_path}")
        return result
    
    try:
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if not _should_exclude(d)]
            
            rel_path = os.path.relpath(root, repo_path)
            sys_subdir = os.path.join(system_path, rel_path) if rel_path != '.' else system_path
            
            for filename in files:
                if _should_exclude(filename):
                    continue
                
                # Skip config files that may be different
                if _should_preserve_config(filename):
                    continue
                
                repo_file = os.path.join(root, filename)
                sys_file = os.path.join(sys_subdir, filename)
                
                result['files_checked'] += 1
                
                if not os.path.exists(sys_file):
                    result['files_mismatched'].append({
                        'file': sys_file,
                        'reason': 'missing'
                    })
                    continue
                
                repo_hash = _calculate_file_hash(repo_file)
                sys_hash = _calculate_file_hash(sys_file)
                
                if repo_hash == sys_hash:
                    result['files_matched'] += 1
                else:
                    result['files_mismatched'].append({
                        'file': sys_file,
                        'reason': 'hash_mismatch'
                    })
    
    except Exception as e:
        result['errors'].append(str(e))
    
    if result['files_mismatched'] or result['errors']:
        result['valid'] = False
    
    return result
