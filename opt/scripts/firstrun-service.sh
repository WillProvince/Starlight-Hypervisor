#!/bin/bash
# Starlight First-Run Service Script
# Displays setup instructions on console and configures nginx for first-run wizard

set -e

FIRSTRUN_FLAG="/etc/starlight/.needs-firstrun"
COMPLETE_FLAG="/etc/starlight/.firstrun-complete"

# Check if first-run is needed
if [ ! -f "$FIRSTRUN_FLAG" ] || [ -f "$COMPLETE_FLAG" ]; then
    echo "First-run wizard not needed or already completed."
    exit 0
fi

# Get system IP address
get_ip() {
    ip -4 route get 1 2>/dev/null | grep -oP 'src \K[\d.]+' || \
    hostname -I 2>/dev/null | awk '{print $1}' || \
    echo "localhost"
}

IP_ADDRESS=$(get_ip)

# Configure nginx for first-run
echo "Configuring nginx for first-run wizard..."

NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"

# Remove default site if it exists
rm -f "${NGINX_SITES_ENABLED}/default" 2>/dev/null || true

# Link firstrun config
if [ -f "${NGINX_SITES_AVAILABLE}/firstrun" ]; then
    ln -sf "${NGINX_SITES_AVAILABLE}/firstrun" "${NGINX_SITES_ENABLED}/default"
fi

# Reload nginx
systemctl reload nginx 2>/dev/null || true

# Display message on all TTYs
display_message() {
    local tty=$1
    
    cat > "$tty" << EOF

================================================================================
                    ⭐ STARLIGHT HYPERVISOR - SETUP REQUIRED ⭐
================================================================================

Your Starlight Hypervisor installation is almost complete!

Please complete the first-run setup wizard to configure your system.

Access the setup wizard at:

    🌐  https://${IP_ADDRESS}/

--------------------------------------------------------------------------------
The setup wizard will help you:
  ✓ Change the default root password (REQUIRED for security)
  ✓ Create an administrator account
  ✓ Configure network settings
  ✓ Set up storage locations

After completing the wizard, this message will no longer appear.
================================================================================

EOF
}

# Display message on console
for tty in /dev/tty1 /dev/console; do
    if [ -w "$tty" ]; then
        display_message "$tty" 2>/dev/null || true
    fi
done

# Also log to journal
echo "Starlight first-run wizard available at https://${IP_ADDRESS}/"
echo "Complete the setup wizard to configure the system."

exit 0
