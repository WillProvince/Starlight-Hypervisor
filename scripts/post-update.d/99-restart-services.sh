#!/bin/bash
# Post-update script: Restart services
# This script restarts Starlight services after an update
#
# Scripts in post-update.d are executed in alphabetical order

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[POST-UPDATE]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[POST-UPDATE]${NC} $1"
}

SERVICE_NAME="${STARLIGHT_SERVICE_NAME:-starlight-backend}"

log_info "Service restart handled by updater system"
log_info "Service name: ${SERVICE_NAME}"

# Note: The actual service restart is handled by the Python updater
# to ensure proper sequencing and error handling.
# This script can be used for additional service-related tasks.

# Example: Reload nginx if configuration changed
# if systemctl is-active --quiet nginx; then
#     log_info "Reloading nginx..."
#     systemctl reload nginx || log_warn "nginx reload failed"
# fi

# Example: Clear systemd service caches
# systemctl daemon-reload 2>/dev/null || true

log_info "Post-update service check completed"

exit 0
