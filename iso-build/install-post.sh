#!/bin/bash
# Starlight Hypervisor - Post-Installation Script
# This script is run during late_command to configure the system

set -e

# Log file path - matches preseed.cfg configuration
LOG_FILE="/var/log/starlight-install.log"

# Logging function that writes to both console and log file
log() {
    echo "$1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "❌ ERROR: $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo "✓ $1" | tee -a "$LOG_FILE"
}

# Initialize log file
mkdir -p "$(dirname "$LOG_FILE")"
echo "=== Starlight Installation Log ===" > "$LOG_FILE"
echo "Started: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Error trap - do NOT delete /opt/starlight on failure to allow debugging
cleanup_on_error() {
    log_error "Installation failed at line $1"
    log "Check $LOG_FILE for details"
    log "Note: /opt/starlight preserved for debugging"
    exit 1
}

trap 'cleanup_on_error $LINENO' ERR

log "================================"
log "Starlight Post-Installation"
log "================================"

# Create starlight-users group
if ! getent group starlight-users > /dev/null 2>&1; then
    groupadd starlight-users
    log_success "Created starlight-users group"
else
    log_success "starlight-users group already exists"
fi

# Create configuration directory structure
mkdir -p /etc/starlight/config
mkdir -p /etc/starlight/data
mkdir -p /etc/starlight/preferences
mkdir -p /etc/starlight/rollback_data
chmod 755 /etc/starlight
chmod 755 /etc/starlight/config
chmod 755 /etc/starlight/data
chmod 755 /etc/starlight/preferences
chmod 755 /etc/starlight/rollback_data
log_success "Created configuration directory structure"

# Create first-run flag file
touch /etc/starlight/.needs-firstrun
log_success "Created first-run flag file"

# Verify Starlight files exist and show contents for debugging
if [ -d /opt/starlight ]; then
    log_success "Starlight files found in /opt/starlight"
    log ""
    log "=== Contents of /opt/starlight (before rsync) ==="
    find /opt/starlight -type f | head -50 | tee -a "$LOG_FILE"
    log "..."
    log "Total files: $(find /opt/starlight -type f | wc -l)"
    log ""
else
    log_error "Starlight files not found in /opt/starlight!"
    exit 1
fi

# Distribute Starlight files to system locations using rsync
# Note: /opt/starlight/ mirrors the final filesystem structure by design
# e.g., /opt/starlight/opt/* → /opt/*, /opt/starlight/etc/* → /etc/*
log ""
log "=== Distributing Starlight files to system locations ==="
log "Running: rsync -av --exclude='iso-build' /opt/starlight/ /"
rsync -av --exclude='iso-build' /opt/starlight/ / 2>&1 | tee -a "$LOG_FILE"
log_success "Files distributed to system locations"

# Verification function to check critical files exist
verify_installation() {
    log ""
    log "=== Verifying installation ==="
    local missing_files=0
    
    # Critical directories and files that must exist after rsync
    local critical_paths=(
        "/opt/pyback"
        "/opt/pyback/main.py"
        "/opt/starlight_startup.sh"
        "/opt/scripts"
        "/opt/scripts/firstrun-service.sh"
        "/opt/scripts/setup-bridge.sh"
        "/var/www/html"
        "/var/www/html/index.html"
        "/etc/systemd/system/starlight-backend.service"
        "/etc/systemd/system/starlight-firstrun.service"
        "/etc/nginx/sites-available/firstrun"
        "/etc/nginx/sites-available/default"
    )
    
    for path in "${critical_paths[@]}"; do
        if [ -e "$path" ]; then
            log_success "Found: $path"
        else
            log_error "MISSING: $path"
            missing_files=$((missing_files + 1))
        fi
    done
    
    log ""
    if [ $missing_files -gt 0 ]; then
        log_error "$missing_files critical file(s) missing after rsync!"
        log "Check if the source files exist in /opt/starlight:"
        log "  - /opt/starlight/opt/ should contain pyback, start_scripts, scripts, starlight_startup.sh"
        log "  - /opt/starlight/var/www/html/ should contain web files"
        log "  - /opt/starlight/etc/ should contain systemd and nginx configs"
        return 1
    else
        log_success "All critical files verified successfully"
        return 0
    fi
}

# Run verification
if ! verify_installation; then
    log_error "Verification failed! Installation incomplete."
    log "Preserving /opt/starlight for debugging."
    exit 1
fi

# Enable firstrun site by default (will be replaced after wizard completes)
rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
ln -s /etc/nginx/sites-available/firstrun /etc/nginx/sites-enabled/default
log_success "Nginx configured with firstrun site"

# Generate self-signed SSL certificate if not exists
if [ ! -f /etc/ssl/private/starlight.key ]; then
    log "Generating self-signed SSL certificate..."
    mkdir -p /etc/ssl/private
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/ssl/private/starlight.key \
        -out /etc/ssl/certs/starlight.crt \
        -subj "/CN=starlight/O=Starlight Hypervisor/C=US" 2>&1 | tee -a "$LOG_FILE"
    chmod 600 /etc/ssl/private/starlight.key
    log_success "Generated self-signed SSL certificate"
else
    log_success "SSL certificate already exists"
fi

# Create SSL snippets for nginx
mkdir -p /etc/nginx/snippets
cat > /etc/nginx/snippets/self-signed.conf << 'EOF'
ssl_certificate /etc/ssl/certs/starlight.crt;
ssl_certificate_key /etc/ssl/private/starlight.key;
EOF
log_success "Created SSL snippets for nginx"

# Configure libvirt defaults
log "Configuring libvirt..."
mkdir -p /var/lib/libvirt/images
mkdir -p /var/lib/libvirt/isos
chmod 755 /var/lib/libvirt/images
chmod 755 /var/lib/libvirt/isos
log_success "Configured libvirt storage directories"

# Create default storage configuration in new centralized location (only if it doesn't exist)
if [ ! -f /etc/starlight/config/storage.json ]; then
    cat > /etc/starlight/config/storage.json << 'EOF'
{
    "vm_storage_path": "/var/lib/libvirt/images",
    "iso_storage_path": "/var/lib/libvirt/isos",
    "default_pool_name": "default"
}
EOF
    log_success "Created default storage configuration"
else
    log_success "Storage configuration already exists"
fi

# Create default system configuration if it doesn't exist
if [ ! -f /etc/starlight/config/system.json ]; then
    cat > /etc/starlight/config/system.json << 'EOF'
{
    "network_mode": "bridge",
    "bridge_name": "br0",
    "nat_network_name": "default",
    "service_name": "starlight-backend"
}
EOF
    log_success "Created default system configuration"
fi

log ""
log "================================"
log "Configuring Bridge Network"
log "================================"

BRIDGE_NAME="br0"
NETWORK_DIR="/etc/systemd/network"
NETDEV_FILE="${NETWORK_DIR}/${BRIDGE_NAME}.netdev"
BRIDGE_NETWORK_FILE="${NETWORK_DIR}/10-${BRIDGE_NAME}-dhcp.network"

# Detect the primary network interface
log "Detecting primary network interface..."

# First try: Check for default route (most reliable during installation)
PRIMARY_INTERFACE=$(ip route show default 2>/dev/null | awk '/default/ {print $5}' | head -1)

# Fallback: If no default route exists, find first physical interface with link
if [ -z "$PRIMARY_INTERFACE" ] || [ "$PRIMARY_INTERFACE" = "lo" ]; then
    log "No default route found, scanning for physical interfaces..."
    for iface in /sys/class/net/*; do
        iface_name=$(basename "$iface")
        # Skip loopback and virtual interfaces
        if [ "$iface_name" != "lo" ] && [ -d "$iface/device" ]; then
            # Prefer interfaces with carrier (cable connected)
            if [ "$(cat /sys/class/net/$iface_name/carrier 2>/dev/null)" = "1" ]; then
                PRIMARY_INTERFACE="$iface_name"
                break
            fi
        fi
    done
fi

if [ -z "$PRIMARY_INTERFACE" ]; then
    log_warn "Could not detect primary network interface. Skipping bridge setup."
    log_warn "You can manually run /opt/scripts/setup-bridge.sh after first boot."
else
    log_success "Detected Primary Interface: $PRIMARY_INTERFACE"
    PHYS_NETWORK_FILE="${NETWORK_DIR}/20-phys-to-${BRIDGE_NAME}.network"
    
    # Create systemd-networkd configuration directory
    mkdir -p "$NETWORK_DIR"
    
    # Backup any existing configs (safety measure)
    if ls "${NETWORK_DIR}"/*.network &>/dev/null 2>&1; then
        BACKUP_DIR="${NETWORK_DIR}/.backup-preinstall"
        mkdir -p "$BACKUP_DIR"
        cp -a "${NETWORK_DIR}"/*.network "$BACKUP_DIR/" 2>/dev/null || true
        log "Backed up existing network configs"
    fi
    
    # Remove any existing interface-specific configs
    log "Cleaning up any existing network configurations..."
    find "${NETWORK_DIR}" -maxdepth 1 -type f -name "*${PRIMARY_INTERFACE}.network" -delete 2>/dev/null || true
    
    # Create the .netdev file to define the bridge
    log "Creating bridge device configuration..."
    cat > "${NETDEV_FILE}" << 'EOF'
[NetDev]
Name=br0
Kind=bridge
EOF
    
    if [ !  -f "${NETDEV_FILE}" ]; then
        log_error "Failed to create bridge device file"
        exit 1
    fi
    log_success "Created: $NETDEV_FILE"
    
    # Create the .network file to configure the physical interface as a bridge member
    log "Creating physical interface configuration..."
    cat > "${PHYS_NETWORK_FILE}" << EOF
[Match]
Name=${PRIMARY_INTERFACE}

[Network]
Bridge=${BRIDGE_NAME}
# Prevent this interface from getting an IP
DHCP=no
EOF
    
    if [ ! -f "${PHYS_NETWORK_FILE}" ]; then
        log_error "Failed to create physical interface configuration"
        exit 1
    fi
    log_success "Created: $PHYS_NETWORK_FILE"
    
    # Create the .network file to configure the bridge with DHCP
    log "Creating bridge DHCP configuration..."
    cat > "${BRIDGE_NETWORK_FILE}" << 'EOF'
[Match]
Name=br0

[Network]
DHCP=yes
# Support both IPv4 and IPv6
LinkLocalAddressing=fallback
# Fallback DNS servers in case DHCP doesn't provide them
DNS=8.8.8.8
DNS=1.1.1.1

[DHCP]
UseDNS=yes
UseNTP=yes
EOF
    
    if [ ! -f "${BRIDGE_NETWORK_FILE}" ]; then
        log_error "Failed to create bridge DHCP configuration"
        exit 1
    fi
    log_success "Created: $BRIDGE_NETWORK_FILE"
    
    # Disable traditional /etc/network/interfaces in favor of systemd-networkd
    if [ -f /etc/network/interfaces ]; then
        log "Migrating from traditional networking to systemd-networkd..."
        cp /etc/network/interfaces /etc/network/interfaces.prebridge 2>/dev/null || true
        cat > /etc/network/interfaces << 'EOF'
# The loopback network interface
auto lo
iface lo inet loopback

# Network interfaces are now managed by systemd-networkd
# See /etc/systemd/network/ for bridge configuration
EOF
        log_success "Disabled traditional networking configuration"
    fi
    
    # Disable traditional networking service (ifupdown)
    log "Disabling traditional networking service..."
    systemctl disable networking.service 2>&1 | tee -a "$LOG_FILE" || log "networking.service not found (OK)"
    systemctl mask networking.service 2>&1 | tee -a "$LOG_FILE" || log "Could not mask networking.service"
    
    # Disable NetworkManager if present
    if systemctl list-unit-files | grep -q NetworkManager; then
        log "Disabling NetworkManager..."
        systemctl disable NetworkManager 2>&1 | tee -a "$LOG_FILE" || true
        systemctl mask NetworkManager 2>&1 | tee -a "$LOG_FILE" || true
    fi
    
    # Enable systemd-networkd
    log "Enabling systemd-networkd..."
    systemctl enable systemd-networkd.service 2>&1 | tee -a "$LOG_FILE"
    
    # Enable systemd-resolved for DNS
    log "Enabling systemd-resolved for DNS..."
    systemctl enable systemd-resolved.service 2>&1 | tee -a "$LOG_FILE"
    
    # Configure systemd-resolved
    if [ ! -L /etc/resolv.conf ] || [ "$(readlink /etc/resolv.conf)" != "/run/systemd/resolve/stub-resolv.conf" ]; then
        log "Configuring systemd-resolved..."
        rm -f /etc/resolv.conf
        ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
        log_success "Configured systemd-resolved"
    fi
    
    log_success "systemd-networkd configured and enabled"
    log_success "Bridge network configuration complete!"
    log "Configuration summary:"
    log "  - Bridge device: $BRIDGE_NAME"
    log "  - Physical interface: $PRIMARY_INTERFACE"
    log "  - Network management: systemd-networkd"
    log "  - DNS management: systemd-resolved"
    log ""
    log "Note: The bridge will become active on first boot when systemd-networkd starts."
fi

# End of bridge setup
log "================================"

# Migrate legacy storage.json if it exists in the old location
if [ -f /etc/starlight/storage.json ] && [ ! -f /etc/starlight/config/storage.json ]; then
    mv /etc/starlight/storage.json /etc/starlight/config/storage.json
    log_success "Migrated legacy storage configuration"
fi

# Create misc directories for Starlight customization
mkdir -p /opt/start_scripts

# Set proper permissions for Starlight components
chown -R root:root /opt/pyback
chown -R root:root /opt/start_scripts
chown -R root:root /opt/scripts
chown root:root /opt/starlight_startup.sh
chmod -R 755 /opt/pyback
chmod -R 755 /opt/start_scripts
chmod 755 /opt/scripts
chmod +x /opt/starlight_startup.sh
find /opt/scripts -name "*.sh" -type f -exec chmod +x {} + 2>/dev/null || true
log_success "Set proper permissions for Starlight components"

# Clean up temporary installation directory
log "Cleaning up temporary files..."
rm -rf /opt/starlight
log_success "Removed temporary installation directory"

# Add root to necessary groups
usermod -aG libvirt root 2>/dev/null || true
usermod -aG kvm root 2>/dev/null || true
log_success "Added root to libvirt and kvm groups"

# Reload systemd
systemctl daemon-reload
systemctl enable starlight-backend.service
systemctl enable starlight-firstrun.service
systemctl enable nginx.service
systemctl enable libvirtd.service
log_success "Enabled systemd services"

log ""
log "================================"
log "✓ Starlight installation complete!"
log "================================"
log ""
log "First-run wizard will start on first boot."
log "Access: https://<server-ip>/"
log ""
log "Installation log saved to: $LOG_FILE"
log "Completed: $(date)"
