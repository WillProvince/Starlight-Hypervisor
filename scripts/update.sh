#!/bin/bash
# Starlight Update Script Template
# This script is executed during system updates
# 
# Add custom update logic here that should run after git pull
# and file synchronization, but before service restart.
#
# Exit codes:
#   0 - Success
#   1 - Non-fatal error (update continues)
#   2 - Fatal error (update should be rolled back)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[UPDATE]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[UPDATE]${NC} $1"
}

log_error() {
    echo -e "${RED}[UPDATE]${NC} $1"
}

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

log_info "=== Starlight Update Script ==="
log_info "Repository path: ${REPO_DIR}"
log_info "Script path: ${SCRIPT_DIR}"

# Example: Database migrations
# if [ -f "${REPO_DIR}/scripts/migrate_db.sh" ]; then
#     log_info "Running database migrations..."
#     bash "${REPO_DIR}/scripts/migrate_db.sh" || {
#         log_warn "Database migration returned non-zero exit code"
#     }
# fi

# Example: Clear cache directories
# log_info "Clearing cache directories..."
# rm -rf /var/cache/starlight/* 2>/dev/null || true

# Example: Rebuild assets
# if [ -f "${REPO_DIR}/var/www/html/build.sh" ]; then
#     log_info "Rebuilding web assets..."
#     bash "${REPO_DIR}/var/www/html/build.sh" || {
#         log_warn "Asset rebuild failed"
#     }
# fi

# Run post-update.d scripts
POST_UPDATE_DIR="${SCRIPT_DIR}/post-update.d"
if [ -d "$POST_UPDATE_DIR" ]; then
    log_info "Running post-update scripts from ${POST_UPDATE_DIR}..."
    
    for script in "${POST_UPDATE_DIR}"/*.sh; do
        if [ -f "$script" ] && [ -x "$script" ]; then
            script_name=$(basename "$script")
            log_info "Executing: ${script_name}"
            
            if ! "$script"; then
                log_warn "Script ${script_name} returned non-zero exit code"
            fi
        fi
    done
fi

log_info "=== Update script completed ==="

exit 0
