#!/bin/bash
# Starlight Authentication System Setup Script

set -e

echo "==================================="
echo "Starlight Authentication Setup"
echo "==================================="
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root (use sudo)" 
   exit 1
fi

# Install system packages
echo "Installing system packages..."
apt-get install -y python3-pam || {
    echo "Warning: Failed to install python3-pam"
    echo "Make sure apt is available"
}

# Install Python dependencies via apt
echo ""
echo "Installing Python dependencies..."
apt-get update
apt-get install -y python3-aiohttp python3-libvirt python3-jwt python3-bcrypt || {
    echo "Error: Failed to install Python dependencies"
    echo "Make sure apt is working properly"
    exit 1
}
echo "✓ Python dependencies installed"

# Create starlight-users group
echo ""
echo "Creating starlight-users group..."
if ! getent group starlight-users > /dev/null 2>&1; then
    groupadd starlight-users
    echo "✓ Created starlight-users group"
else
    echo "✓ starlight-users group already exists"
fi

# Create /etc/starlight directory
echo ""
echo "Setting up configuration directory..."
mkdir -p /etc/starlight
chmod 755 /etc/starlight
echo "✓ Created /etc/starlight directory"

# Create default admin user (optional)
echo ""
read -p "Create a default admin user? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter admin username: " admin_user
    
    if id "$admin_user" &>/dev/null; then
        echo "User $admin_user already exists"
        read -p "Add to starlight-users group? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            usermod -aG starlight-users "$admin_user"
            echo "✓ Added $admin_user to starlight-users group"
        fi
    else
        useradd -m -G starlight-users -s /bin/bash "$admin_user"
        echo ""
        echo "Setting password for $admin_user:"
        passwd "$admin_user"
        echo "✓ Created user $admin_user"
    fi
fi

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Make sure your Starlight backend service is configured"
echo "2. Start/restart the backend: systemctl restart starlight-backend"
echo "3. Access the web interface and log in with your credentials"
echo ""
echo "Configuration files will be auto-created in /etc/starlight/ on first run:"
echo "  - auth.json (JWT configuration)"
echo "  - api_keys.json (API keys storage)"
echo "  - users.json (User metadata)"
echo ""
