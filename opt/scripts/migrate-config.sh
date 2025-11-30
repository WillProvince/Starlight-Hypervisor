#!/bin/bash
# Starlight Configuration Migration Script
# Migrates configuration files from old scattered layout to centralized /etc/starlight/config/

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration directories
CONFIG_BASE="/etc/starlight"
CONFIG_DIR="${CONFIG_BASE}/config"
DATA_DIR="${CONFIG_BASE}/data"
PREFERENCES_DIR="${CONFIG_BASE}/preferences"
ROLLBACK_DIR="${CONFIG_BASE}/rollback_data"

# Create new directory structure
create_directories() {
    log_info "Creating new configuration directory structure..."
    
    mkdir -p "${CONFIG_DIR}"
    mkdir -p "${DATA_DIR}"
    mkdir -p "${PREFERENCES_DIR}"
    mkdir -p "${ROLLBACK_DIR}"
    
    chmod 755 "${CONFIG_BASE}"
    chmod 755 "${CONFIG_DIR}"
    chmod 755 "${DATA_DIR}"
    chmod 755 "${PREFERENCES_DIR}"
    chmod 755 "${ROLLBACK_DIR}"
    
    log_info "Directory structure created successfully"
}

# Migrate a single file
migrate_file() {
    local src="$1"
    local dst="$2"
    local desc="$3"
    
    if [ -f "$src" ]; then
        if [ ! -f "$dst" ]; then
            cp "$src" "$dst"
            log_info "Migrated ${desc}: ${src} -> ${dst}"
            return 0
        else
            log_warn "${desc} already exists at ${dst}, skipping migration"
            return 1
        fi
    fi
    return 2
}

# Migrate configuration files
migrate_config_files() {
    log_info "Checking for configuration files to migrate..."
    
    local migrated=0
    
    # Storage configuration
    if migrate_file "${CONFIG_BASE}/storage.json" "${CONFIG_DIR}/storage.json" "storage configuration"; then
        ((migrated++))
    fi
    
    # Repositories configuration
    if migrate_file "${CONFIG_BASE}/repositories.json" "${CONFIG_DIR}/repositories.json" "repositories configuration"; then
        ((migrated++))
    fi
    
    # Auth configuration
    if migrate_file "${CONFIG_BASE}/auth.json" "${CONFIG_DIR}/auth.json" "auth configuration"; then
        ((migrated++))
    fi
    
    # Update configuration
    if migrate_file "${CONFIG_BASE}/update_config.json" "${CONFIG_DIR}/update.json" "update configuration"; then
        ((migrated++))
    fi
    
    log_info "Migrated ${migrated} configuration file(s)"
}

# Migrate data files
migrate_data_files() {
    log_info "Checking for data files to migrate..."
    
    local migrated=0
    
    # VM metadata
    if migrate_file "${CONFIG_BASE}/vm_metadata.json" "${DATA_DIR}/vm_metadata.json" "VM metadata"; then
        ((migrated++))
    fi
    
    # LXC metadata
    if migrate_file "${CONFIG_BASE}/lxc_metadata.json" "${DATA_DIR}/lxc_metadata.json" "LXC metadata"; then
        ((migrated++))
    fi
    
    # Users metadata
    if migrate_file "${CONFIG_BASE}/users.json" "${DATA_DIR}/users.json" "users metadata"; then
        ((migrated++))
    fi
    
    # API keys
    if migrate_file "${CONFIG_BASE}/api_keys.json" "${DATA_DIR}/api_keys.json" "API keys"; then
        ((migrated++))
    fi
    
    log_info "Migrated ${migrated} data file(s)"
}

# Create default configurations if they don't exist
create_defaults() {
    log_info "Creating default configurations if needed..."
    
    # Default storage configuration
    if [ ! -f "${CONFIG_DIR}/storage.json" ]; then
        cat > "${CONFIG_DIR}/storage.json" << 'EOF'
{
    "vm_storage_path": "/var/lib/libvirt/images",
    "iso_storage_path": "/var/lib/libvirt/isos",
    "default_pool_name": "default"
}
EOF
        log_info "Created default storage configuration"
    fi
    
    # Default system configuration
    if [ ! -f "${CONFIG_DIR}/system.json" ]; then
        cat > "${CONFIG_DIR}/system.json" << 'EOF'
{
    "network_mode": "bridge",
    "bridge_name": "br0",
    "nat_network_name": "default",
    "service_name": "starlight-backend"
}
EOF
        log_info "Created default system configuration"
    fi
}

# Check if migration is needed
check_migration_needed() {
    # If new config directory exists with content, no migration needed
    if [ -d "${CONFIG_DIR}" ] && [ "$(ls -A ${CONFIG_DIR} 2>/dev/null)" ]; then
        log_info "New configuration directory already exists with content"
        return 1
    fi
    
    # Check if any legacy configs exist
    local legacy_files=(
        "${CONFIG_BASE}/storage.json"
        "${CONFIG_BASE}/repositories.json"
        "${CONFIG_BASE}/auth.json"
        "${CONFIG_BASE}/update_config.json"
        "${CONFIG_BASE}/vm_metadata.json"
        "${CONFIG_BASE}/lxc_metadata.json"
        "${CONFIG_BASE}/users.json"
        "${CONFIG_BASE}/api_keys.json"
    )
    
    for file in "${legacy_files[@]}"; do
        if [ -f "$file" ]; then
            return 0
        fi
    done
    
    log_info "No legacy configuration files found"
    return 1
}

# Main migration function
main() {
    log_info "=== Starlight Configuration Migration ==="
    
    # Check if running as root
    if [ "$(id -u)" -ne 0 ]; then
        log_error "This script must be run as root"
        exit 1
    fi
    
    # Create directories first
    create_directories
    
    # Check if migration is needed
    if check_migration_needed; then
        log_info "Migration needed, proceeding..."
        migrate_config_files
        migrate_data_files
    fi
    
    # Always create defaults if missing
    create_defaults
    
    log_info "=== Migration Complete ==="
    log_info "Configuration is now centralized under ${CONFIG_DIR}"
    log_info "Data files are stored in ${DATA_DIR}"
}

# Run if executed directly
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
