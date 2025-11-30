#!/bin/bash
#
# Bridge Configuration Script for Starlight
# WARNING: This script will temporarily disrupt network connectivity. 
# It MUST be run as root. 

set -e

# --- Configuration ---
BRIDGE_NAME="br0"
NETWORK_DIR="/etc/systemd/network"
NETDEV_FILE="${NETWORK_DIR}/${BRIDGE_NAME}.netdev"
BRIDGE_NETWORK_FILE="${NETWORK_DIR}/10-${BRIDGE_NAME}-dhcp.network"
PHYS_NETWORK_FILE="${NETWORK_DIR}/20-phys-to-${BRIDGE_NAME}.network"
BACKUP_DIR="${NETWORK_DIR}/.backup-$(date +%s)"

# Log file configuration - follows Starlight convention
LOG_DIR="/var/log/starlight"
LOG_FILE="${LOG_DIR}/network-setup.log"

# --- Logging Functions (Starlight Convention) ---
# Initialize logging
init_logging() {
    mkdir -p "$LOG_DIR"
    echo "=== Starlight Bridge Network Setup ===" > "$LOG_FILE"
    echo "Started: $(date)" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
}

# Log function - writes to both console and log file
log() {
    echo "$1" | tee -a "$LOG_FILE"
}

# Log error - writes to both console and log file
log_error() {
    echo "❌ ERROR: $1" | tee -a "$LOG_FILE"
}

# Log success - writes to both console and log file
log_success() {
    echo "✓ $1" | tee -a "$LOG_FILE"
}

# Log warning - writes to both console and log file
log_warn() {
    echo "⚠ WARNING: $1" | tee -a "$LOG_FILE"
}

# Error trap function
cleanup_on_error() {
    log_error "Bridge setup failed at line $1"
    log "Check $LOG_FILE for details"
    
    # Attempt to restore from backup if it exists
    if [ -d "$BACKUP_DIR" ]; then
        log "Attempting to restore network configuration from backup..."
        if cp -a "$BACKUP_DIR"/*. network "${NETWORK_DIR}/" 2>/dev/null && \
           cp -a "$BACKUP_DIR"/*.netdev "${NETWORK_DIR}/" 2>/dev/null; then
            log "Restarting systemd-networkd with restored configuration..."
            systemctl restart systemd-networkd || true
            log_warn "Backup restored.  Network may need manual verification."
        else
            log_error "Failed to restore backup automatically"
        fi
    fi
    
    log "Bridge setup aborted"
    exit 1
}

# Set up error trap
trap 'cleanup_on_error $LINENO' ERR

# Initialize logging
init_logging

log "================================"
log "Starting Bridge Network Setup"
log "================================"
log ""

# 1. Check for root privileges
if [ "$(id -u)" != "0" ]; then
   log_error "This script must be run as root (use sudo)."
   exit 1
fi
log_success "Running with root privileges"

# 2.  Detect active network manager and warn about conflicts
log ""
log "Checking for network management conflicts..."
ACTIVE_MANAGER=""
if systemctl is-active --quiet NetworkManager; then
    ACTIVE_MANAGER="NetworkManager"
    log_warn "NetworkManager is active. This may conflict with systemd-networkd."
    log_warn "Consider disabling NetworkManager if you want to use systemd-networkd exclusively."
    log "Continuing anyway..."
fi
if [ -z "$ACTIVE_MANAGER" ]; then
    log_success "No conflicting network managers detected"
fi

# 3.  Automatically detect the primary network interface
log ""
log "Detecting primary network interface..."
PRIMARY_INTERFACE=$(ip route show default | awk '/default/ {print $5}' | head -1)

if [ -z "$PRIMARY_INTERFACE" ] || [ "$PRIMARY_INTERFACE" = "lo" ]; then
    log_error "Could not determine a valid primary network interface (e.g., eth0, ens33, or enp0s3)."
    exit 1
fi

log_success "Detected Primary Interface: $PRIMARY_INTERFACE"

# 4. Capture current network state for logging
log ""
log "Current network state:"
log "---------------------"
ip -4 addr show "$PRIMARY_INTERFACE" 2>&1 | tee -a "$LOG_FILE"
log ""

# 5.  Backup existing configuration
log "Backing up existing network configuration..."
mkdir -p "$BACKUP_DIR"
if ls "${NETWORK_DIR}"/*.network &>/dev/null; then
    cp -a "${NETWORK_DIR}"/*. network "$BACKUP_DIR/" 2>&1 | tee -a "$LOG_FILE" || true
fi
if ls "${NETWORK_DIR}"/*. netdev &>/dev/null; then
    cp -a "${NETWORK_DIR}"/*.netdev "$BACKUP_DIR/" 2>&1 | tee -a "$LOG_FILE" || true
fi
log_success "Backup created at: $BACKUP_DIR"

# 6. Clear existing configurations for the physical interface (targeted removal)
log ""
log "Removing existing network configuration for $PRIMARY_INTERFACE..."
# Only remove files that exactly match the interface name
REMOVED_COUNT=0
for file in "${NETWORK_DIR}"/*"${PRIMARY_INTERFACE}".network; do
    if [ -f "$file" ]; then
        rm -f "$file"
        log "  Removed: $(basename "$file")"
        ((REMOVED_COUNT++))
    fi
done
if [ $REMOVED_COUNT -eq 0 ]; then
    log "  No existing configuration files found for $PRIMARY_INTERFACE"
else
    log_success "Removed $REMOVED_COUNT configuration file(s)"
fi

# 7. Enable systemd-networkd if not already enabled
log ""
log "Checking systemd-networkd status..."
if !  systemctl is-enabled systemd-networkd >/dev/null 2>&1; then
    log "Enabling systemd-networkd..."
    systemctl enable systemd-networkd 2>&1 | tee -a "$LOG_FILE"
    log_success "systemd-networkd enabled"
else
    log_success "systemd-networkd is already enabled"
fi

# 8. Create the . netdev file to define the bridge
log ""
log "Creating bridge definition file: $NETDEV_FILE"
cat << EOF > "${NETDEV_FILE}"
[NetDev]
Name=${BRIDGE_NAME}
Kind=bridge
EOF
log_success "Bridge device configuration created"

# 9.  Create the .network file to configure the physical interface
log ""
log "Creating physical interface configuration file: $PHYS_NETWORK_FILE"
cat << EOF > "${PHYS_NETWORK_FILE}"
[Match]
Name=${PRIMARY_INTERFACE}

[Network]
Bridge=${BRIDGE_NAME}
# Prevent this interface from getting an IP
DHCP=no
EOF
log_success "Physical interface configuration created"

# 10. Create the .network file to configure the bridge with DHCP
log ""
log "Creating bridge DHCP configuration file: $BRIDGE_NETWORK_FILE"
cat << EOF > "${BRIDGE_NETWORK_FILE}"
[Match]
Name=${BRIDGE_NAME}

[Network]
DHCP=yes
# Use DHCP for both IPv4 and IPv6 if available
LinkLocalAddressing=fallback
# Fallback DNS servers in case DHCP doesn't provide them
DNS=8.8.8.8
DNS=1.1.1.1

[DHCP]
UseDNS=yes
UseNTP=yes
EOF
log_success "Bridge DHCP configuration created"

# 11. Apply the changes
log ""
log "Applying new systemd-networkd configurations..."
systemctl daemon-reload 2>&1 | tee -a "$LOG_FILE"
log_success "systemd daemon reloaded"

# 12.  Restart systemd-networkd to apply the new configuration
log ""
log "Restarting systemd-networkd..."
log_warn "Network connectivity will drop momentarily!"
if systemctl restart systemd-networkd 2>&1 | tee -a "$LOG_FILE"; then
    log_success "systemd-networkd restarted successfully"
else
    log_error "Failed to restart systemd-networkd"
    exit 1
fi

# 13. Wait for network to stabilize
log ""
log "Waiting for network to stabilize (this may take 10-15 seconds)..."
sleep 10

# 14. Verification with validation
log ""
log "================================"
log "Verification"
log "================================"

# Check if bridge exists
if !  ip link show "$BRIDGE_NAME" &>/dev/null; then
    log_error "Bridge $BRIDGE_NAME was not created!"
    exit 1
fi
log_success "Bridge device $BRIDGE_NAME exists"

# Check if bridge is UP
BRIDGE_STATE=$(ip -o link show "$BRIDGE_NAME" | awk '{print $9}')
if [ "$BRIDGE_STATE" != "UP" ]; then
    log_warn "Bridge $BRIDGE_NAME is not UP (state: $BRIDGE_STATE)"
else
    log_success "Bridge $BRIDGE_NAME is UP"
fi

# Check if interface is attached to bridge
if ip link show master "$BRIDGE_NAME" 2>/dev/null | grep -q "$PRIMARY_INTERFACE"; then
    log_success "Interface $PRIMARY_INTERFACE is attached to bridge $BRIDGE_NAME"
else
    log_error "Interface $PRIMARY_INTERFACE is NOT attached to bridge $BRIDGE_NAME!"
    exit 1
fi

# Display bridge status
log ""
log "Bridge $BRIDGE_NAME Status:"
log "----------------------------"
ip a show dev "${BRIDGE_NAME}" 2>&1 | tee -a "$LOG_FILE"

log ""
log "Interface $PRIMARY_INTERFACE Status (should have NO IP address):"
log "----------------------------------------------------------------"
ip a show dev "${PRIMARY_INTERFACE}" 2>&1 | tee -a "$LOG_FILE"

# Check if bridge has an IP address
BRIDGE_IP=$(ip -4 addr show dev "$BRIDGE_NAME" | grep -oP '(?<=inet\s)\d+(\.\d+){3}' || echo "none")
log ""
if [ "$BRIDGE_IP" = "none" ]; then
    log_warn "Bridge did not acquire an IP address via DHCP."
    log_warn "This might be normal if DHCP is slow.  Check with 'ip a show $BRIDGE_NAME' in a few moments."
else
    log_success "Bridge $BRIDGE_NAME has IP address: $BRIDGE_IP"
fi

# 15. Clean up old backups (keep last 5)
log ""
log "Cleaning up old backups (keeping last 5)..."
OLD_BACKUPS=$(ls -dt "${NETWORK_DIR}"/. backup-* 2>/dev/null | tail -n +6)
if [ -n "$OLD_BACKUPS" ]; then
    echo "$OLD_BACKUPS" | xargs rm -rf 2>/dev/null || true
    log_success "Old backups cleaned up"
else
    log "No old backups to clean up"
fi

# 16. Final status
log ""
log "================================"
log "✓ Bridge Setup Complete!"
log "================================"
log ""
log "Summary:"
log "  - Primary Interface: $PRIMARY_INTERFACE (attached to bridge)"
log "  - Bridge Device: $BRIDGE_NAME"
log "  - Bridge IP: ${BRIDGE_IP}"
log "  - Configuration Backup: $BACKUP_DIR"
log "  - Log File: $LOG_FILE"
log ""
log "If you encounter issues, restore the backup with:"
log "  sudo cp -a $BACKUP_DIR/* $NETWORK_DIR/"
log "  sudo systemctl restart systemd-networkd"
log ""
log "Completed: $(date)"

exit 0
