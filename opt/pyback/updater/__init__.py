"""
Updater package for Starlight Hypervisor Manager.

This package contains system update functionality for:
- Update checking and status
- Update execution and rollback
- Backup creation and restoration
- File synchronization from repository to system
- Package management (apt)
- Update script execution
- Configurable repository settings via updater.json
"""

from .system import (
    validate_git_repo,
    get_current_version,
    check_for_updates,
    perform_update,
    schedule_service_restart,
    rollback_update,
    perform_health_check,
    get_repo_path,
    get_repo_url,
    get_repo_branch,
)

from .backup import (
    load_update_config,
    save_update_config,
    create_backup,
)

from .file_sync import (
    sync_file,
    sync_directory,
    sync_repo_to_system,
    validate_sync,
)

from .package_manager import (
    apt_update,
    apt_upgrade,
    full_system_update,
)

__all__ = [
    # System update functions
    'validate_git_repo',
    'get_current_version',
    'check_for_updates',
    'perform_update',
    'schedule_service_restart',
    'rollback_update',
    'perform_health_check',
    'get_repo_path',
    'get_repo_url',
    'get_repo_branch',
    # Backup functions
    'load_update_config',
    'save_update_config',
    'create_backup',
    # File sync functions
    'sync_file',
    'sync_directory',
    'sync_repo_to_system',
    'validate_sync',
    # Package manager functions
    'apt_update',
    'apt_upgrade',
    'full_system_update',
]
