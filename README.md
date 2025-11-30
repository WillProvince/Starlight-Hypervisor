# ⭐ Starlight Hypervisor Manager

**Starlight** is a modern web-based management interface for KVM/QEMU virtual machines and LXC containers. It simplifies VM deployment and management by providing an intuitive web UI that abstracts away the complexities of libvirt, making virtualization accessible to everyone.

## ✨ Features

- **🖥️ VM Management** - Start, stop, and monitor virtual machines with a single click
- **🛍️ App Store** - Deploy pre-configured VMs from repositories with one click
- **📦 LXC Container Support** - Manage lightweight Linux containers alongside VMs
- **🎮 Integrated Console** - Built-in VNC viewer and terminal access
- **💾 Multi-Repository** - Add and manage multiple VM template repositories
- **🔐 Authentication System** - PAM-based authentication with JWT tokens and API keys
- **👥 User Management** - Create and manage system users with role-based access control
- **🔑 API Keys** - Generate secure API keys for programmatic access
- **🌙 Dark Mode** - Beautiful light and dark themes
- **📱 Responsive Design** - Works great on desktop and mobile devices

## 🚀 Getting Started

Download a release ISO, burn it to a disk or boot it from USB. Follow on-screen steps.

**Access the interface:**
- Open your web browser and navigate to `https://your-server-ip/`
- Log in with your system username and password
- The first user in the `starlight-users` group will have admin privileges

---

## 📖 User Guide

### Managing Virtual Machines

#### Deployed VMs Page
View and control all your virtual machines and containers:

- **VM Status** - See real-time state (Running, Shut Off, etc.)
- **Resource Info** - View vCPUs, RAM, disk size
- **Network Info** - Automatic IP detection and VNC port display
- **Quick Actions**:
  - **Start** - Boot a VM
  - **Stop** - Gracefully shutdown
  - **Force Stop** - Immediate termination
  - **Delete** - Remove VM and disk
  - **Take Over** - Launch console (VNC for VMs, Terminal for containers)
  - **Settings** - Configure VM resources

#### VM Settings
Modify VM configuration (requires VM to be shut down):
- Change VM name and description
- Adjust RAM and vCPU allocation
- Expand disk size (can only grow, not shrink)
- Configure graphics memory (VRAM)
- Enable/disable audio device
- Set display resolution hints
- Toggle autostart on boot

### App Store

Deploy pre-configured VMs with a single click:

1. Browse available applications from enabled repositories
2. Click on an app to view details
3. Click **Deploy** to create a new VM
4. The system automatically:
   - Downloads the VM image (if cloud image provided)
   - Creates and configures the VM
   - Starts the VM

### Repository Management

Add custom VM template repositories:

1. Go to **Settings** page
2. Click **Add Repository**
3. Fill in repository details:
   - **ID**: Unique identifier
   - **Name**: Display name
   - **URL**: JSON repository URL
   - **Description**: Optional notes
4. Enable/disable repositories as needed

---

## 🏗️ Architecture

### System Components

**Frontend (Web Interface)**
- Modular single-page application with clean separation of concerns
- Organized into CSS and JavaScript modules for maintainability
- Integrated VNC client (noVNC) for VM console access
- Terminal emulator (xterm.js) for LXC container access
- Advanced theming system with custom theme support
- Responsive design for desktop and mobile

**Backend (Python API)**
- Built with `aiohttp` for async HTTP handling
- Uses `libvirt-python` to interface with KVM/QEMU
- WebSocket proxy for VNC connections
- REST API for VM management operations

**Infrastructure (NGINX)**
- Reverse proxy for frontend and API
- SSL/TLS termination
- WebSocket routing for VNC and terminal connections

### Frontend Structure

The web interface is organized into modular files for better maintainability:

```
var/www/html/
├── index.html              # Main HTML shell
├── css/                    # Modular CSS stylesheets
│   ├── variables.css      # CSS custom properties for theming
│   ├── base.css           # Base styles and layout
│   ├── components.css     # Reusable UI components
│   ├── sidebar.css        # Navigation sidebar styles
│   ├── vnc-terminal.css   # VNC and terminal viewer styles
│   └── responsive.css     # Mobile responsive breakpoints
├── js/                     # Modular JavaScript functionality
│   ├── config.js          # Configuration constants
│   ├── auth.js            # Authentication and login
│   ├── api.js             # API communication layer
│   ├── ui.js              # UI helpers and navigation
│   ├── theme.js           # Theme management system
│   ├── vm-manager.js      # VM list and operations
│   ├── vnc-viewer.js      # VNC client functionality
│   ├── terminal.js        # Terminal emulator for LXC containers
│   ├── console-manager.js # Unified tabbed console interface
│   ├── host-terminal.js   # Host system console (root only)
│   ├── appstore.js        # App store and deployment
│   ├── settings.js        # Settings and repositories
│   ├── storage-settings.js # Storage configuration
│   ├── network-settings.js # Network configuration
│   ├── api-keys.js        # API key management
│   ├── user-management.js # User CRUD operations
│   ├── system.js          # System-level operations
│   └── main.js            # Application entry point
└── themes/                 # Theme definitions
    ├── default.json       # Light theme
    ├── dark.json          # Dark theme
    └── README.md          # Theme creation guide
```

### Theming System

Starlight includes a powerful theming system that allows users to:
- Switch between built-in Light and Dark themes
- Import custom themes via JSON files
- Export current theme configuration
- Create personalized color schemes

See `/themes/README.md` for detailed theme creation documentation.

### Key Technical Features

**Automatic IP Detection**
- Reads libvirt DHCP leases for NAT networks
- Checks ARP table for bridged networks
- Queries libvirt interface addresses API

**VNC WebSocket Proxy**
- Bridges WebSocket (browser) to TCP (QEMU VNC)
- Handles bidirectional data streaming
- No external VNC proxy needed

**Multi-Repository Support**
- Aggregate apps from multiple sources
- Enable/disable repositories dynamically
- Stored in `/etc/starlight/repositories.json`

---

## 🔧 Configuration

### Repository Configuration

Create `/etc/starlight/repositories.json` to add VM template repositories:

```json
{
  "repositories": [
    {
      "id": "official",
      "name": "Official Starlight Repository",
      "url": "https://example.com/repo.json",
      "enabled": true,
      "description": "Official VM templates"
    }
  ]
}
```

**Repository JSON Format:**
```json
{
  "name": "My Repository",
  "apps": [
    {
      "name": "Ubuntu 22.04",
      "description": "Ubuntu Server LTS",
      "xml_url": "https://example.com/ubuntu.xml",
      "vcpus": 2,
      "memory_mb": 2048,
      "disk_size_gb": 20,
      "type": "vm",
      "image_source": {
        "type": "qcow2",
        "url": "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img",
        "size_mb": 600
      }
    }
  ]
}
```

### Network Configuration

Edit `/opt/pyback/main.py` to configure network mode:

```python
NETWORK_MODE = 'bridge'  # or 'nat'
BRIDGE_NAME = 'br0'      # for bridge mode
NAT_NETWORK_NAME = 'default'  # for NAT mode
```

---

## 🔐 Authentication & Security

### Overview

Starlight uses a comprehensive authentication system that integrates with Linux PAM (Pluggable Authentication Modules) for unified credentials between SSH and the Web UI. Users can also generate API keys for programmatic access.

### Authentication Methods

1. **Web UI Login (JWT)**
   - Uses PAM to authenticate against system credentials
   - JWT tokens valid for 24 hours (configurable)
   - Tokens stored in browser localStorage
   - Automatic token refresh on API calls

2. **API Keys**
   - Generate secure API keys for scripts and automation
   - Keys are hashed with bcrypt before storage
   - Support for multiple keys per user
   - Track last used date and expiration

### User Roles

- **Admin** - Full access to all features including user management
- **User** - Access to VM management and personal API keys

### User Management

**Creating Users (Admin Only):**
```bash
# Via Web UI: Navigate to User Management page and click "Create User"
# Or via command line:
sudo useradd -m -G starlight-users -s /bin/bash newuser
sudo passwd newuser
```

**Managing API Keys:**
1. Log in to the Web UI
2. Click your username in the top right
3. Select "API Keys"
4. Click "Create API Key"
5. Save the key securely - it won't be shown again

**Using API Keys:**
```bash
# Include API key in request header
curl -H "X-API-Key: stl_your_api_key_here" https://your-server/api/vm_list

# Or use Bearer token authentication
curl -H "Authorization: Bearer stl_your_api_key_here" https://your-server/api/vm_list
```

### Security Features

- **PAM Integration** - System-level authentication
- **bcrypt Hashing** - Secure API key storage
- **JWT Tokens** - Stateless session management
- **Role-Based Access** - Admin and user permissions
- **Rate Limiting** - Protection against brute force (future)
- **Audit Logging** - Track authentication events
- **Secure Configuration** - Files stored with 0600 permissions

### Configuration Files

Authentication configuration is stored in `/etc/starlight/`:

- `auth.json` - JWT secret and session timeout settings
- `api_keys.json` - Hashed API keys with metadata
- `users.json` - User roles and preferences

These files are automatically created with secure permissions on first run.

---

## 🛠️ API Reference

### Authentication Endpoints

**All API endpoints require authentication except `/api/auth/login`**

- `POST /api/auth/login` - Login with username/password
  ```json
  {
    "username": "user",
    "password": "password"
  }
  ```
- `POST /api/auth/logout` - Invalidate current session
- `GET /api/auth/verify` - Verify current authentication status
- `POST /api/auth/refresh` - Refresh JWT token

### User Management (Admin Only)

- `GET /api/users` - List all users
- `POST /api/users` - Create new user
- `PUT /api/users/{username}` - Update user
- `DELETE /api/users/{username}` - Delete user
- `POST /api/users/{username}/password` - Change password

### API Key Management

- `GET /api/auth/api-keys` - List current user's API keys
- `POST /api/auth/api-keys` - Generate new API key
- `DELETE /api/auth/api-keys/{key_id}` - Revoke API key
- `PUT /api/auth/api-keys/{key_id}` - Update API key metadata

### VM Management

- `GET /api/vm_list` - List all VMs
- `POST /api/vm/{name}/{action}` - VM action (start/stop/destroy/delete)
- `POST /api/vm/deploy` - Deploy VM from repository
- `GET /api/vm/{name}/disk-info` - Get disk size info
- `PUT /api/vm/{name}/settings` - Update VM settings

### Repository Management

- `GET /api/repositories` - List repositories
- `GET /api/repositories/apps` - Get all apps from enabled repos
- `POST /api/repositories` - Add repository
- `PUT /api/repositories/{id}` - Update repository
- `DELETE /api/repositories/{id}` - Delete repository

### Console Access

- `GET /vnc-proxy/{port}` - VNC WebSocket proxy
- `GET /lxc-console/{name}` - LXC terminal WebSocket proxy

---

## 🔧 Troubleshooting

### Authentication Issues

**"python3-pam not available" warning**

This warning appears when the PAM package is not installed:

```bash
# Install PAM module via apt
sudo apt install python3-pam

# Restart the service
sudo systemctl restart starlight-backend
```

**Cannot log in to Web UI**

1. Verify you're in the `starlight-users` group:
   ```bash
   groups your-username
   ```

2. If not, add yourself to the group:
   ```bash
   sudo usermod -aG starlight-users your-username
   # Log out and back in for changes to take effect
   ```

3. Check backend logs for authentication errors:
   ```bash
   sudo journalctl -u starlight-backend -f
   ```

**API Keys not working**

1. Ensure `bcrypt` is installed:
   ```bash
   pip3 install bcrypt
   ```

2. API keys require bcrypt - the system will refuse to create keys without it for security reasons.

---

## 🚧 Roadmap

### Recently Implemented ✅

- **User Authentication** - PAM-based authentication with JWT tokens and API keys
- **User Management** - Create, delete, and manage system users
- **Role-Based Access** - Admin and user roles with appropriate permissions
- **API Key System** - Secure API keys for programmatic access

### Future Enhancements

- **Network Management** - UI for managing libvirt networks
- **Snapshot Management** - Create and restore VM snapshots
- **Live Migration** - Move VMs between hosts
- **Docker Integration** - Manage Docker containers alongside VMs
- **Metrics & Monitoring** - Real-time resource usage graphs
- **Rate Limiting** - Enhanced security with rate limiting on login attempts
- **2FA/MFA** - Two-factor authentication support
- **LDAP/AD Integration** - Enterprise authentication options

---

## 📝 License

This project is open source. See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

---

**Made with ❤️ for the homelab community**
