# 💿 Starlight Hypervisor - ISO Build System

This directory contains the build system for creating bootable Debian 13 (trixie) netinst ISOs with Starlight Hypervisor pre-configured.

---

## 📋 Overview

The build system creates a custom Debian installation ISO that:
- Automates the entire Debian installation process
- Pre-installs all Starlight dependencies (KVM, libvirt, LXC, nginx, etc.)
- Includes the Starlight web interface and backend
- Launches a first-run wizard on first boot

## 🔧 Requirements

### Build Machine Requirements

Install the required tools on your build machine:

```bash
apt install genisoimage xorriso syslinux-utils wget libarchive-tools
```

Note: `libarchive-tools` provides `bsdtar` which is used to extract the ISO without requiring root privileges.

### Recommended Build Environment
- Ubuntu 22.04 or Debian 12+
- At least 4GB free disk space (for temporary files during build)
- Internet connection for downloading Debian ISO
- No root/sudo required for building
- Must be run from a clean git repository checkout

**Important**: The build script uses `git archive` to export only tracked repository files. This prevents accidentally including:
- System configuration files
- VM disk images
- Temporary files or build artifacts
- Other untracked content from your working directory

---

## 🚀 Building the ISO

### Quick Build

```bash
cd iso-build
./build-iso.sh
```

The ISO will be created in `iso-build/output/`.

### Build Options

```bash
# Clean all build artifacts
./build-iso.sh --clean

# Show help
./build-iso.sh --help
```

## 📦 Output Files

After a successful build, you'll find:
- `starlight-hypervisor-YYYYMMDD.iso` - The bootable ISO
- `starlight-hypervisor-YYYYMMDD.iso.sha256` - SHA256 checksum

---

## 🧪 Testing

### Testing with QEMU

```bash
qemu-system-x86_64 \
    -cdrom iso-build/output/starlight-hypervisor-*.iso \
    -m 4G \
    -enable-kvm \
    -cpu host \
    -smp 2 \
    -boot d
```

### Testing with VirtualBox

1. Create a new VM (Debian 64-bit)
2. Allocate at least 2GB RAM, 20GB disk
3. Mount the ISO as the boot media
4. Start the VM

---

## 💾 Writing to USB

```bash
# Replace /dev/sdX with your USB device
sudo dd if=iso-build/output/starlight-hypervisor-*.iso of=/dev/sdX bs=4M status=progress
sync
```

⚠️ **Warning**: This will erase all data on the USB drive!

---

## 📥 Installation Process

### Automated Installation

1. Boot from the ISO
2. Select "Install Starlight Hypervisor (Automated)"
3. Wait for installation to complete (~10-15 minutes)
4. System reboots automatically

### First Boot

1. System starts with first-run wizard enabled
2. Access `https://<server-ip>/` from any browser
3. Complete the setup wizard:
   - Change root password (required)
   - Create admin user
   - Configure network (optional)
   - Set storage location (optional)
4. Wizard completes and redirects to main Starlight interface

### Default Credentials

⚠️ **Security Warning**: The default root password is `starlight`. This MUST be changed during the first-run wizard.

---

## ⚙️ Customization

### Preseed Configuration

Edit `preseed.cfg` to customize:
- Default keyboard layout
- Timezone settings
- Partition scheme
- Package selection

### Post-Installation

Edit `install-post.sh` to customize:
- Additional packages
- System configuration
- Service setup

## 📁 File Structure

```
iso-build/
├── build-iso.sh      # Main build script
├── preseed.cfg       # Debian preseed configuration
├── install-post.sh   # Post-installation script
├── README.md         # This file
└── output/           # Built ISO files (created during build)
```

---

## 🔍 Troubleshooting

### Build Fails - Missing Tools

Install all required tools:
```bash
apt install genisoimage xorriso syslinux-utils wget libarchive-tools
```

### ISO Won't Boot

- Ensure `isohybrid` was run (for USB boot)
- Check boot order in BIOS/UEFI
- Try legacy boot mode if UEFI fails

### Network Not Working During Install

- Check network cable connection
- Verify DHCP server is available
- The installer requires internet for package download

### First-Run Wizard Not Accessible

- Wait a few minutes after boot for services to start
- Check that nginx is running: `systemctl status nginx`
- Verify the IP address: `ip addr show`

---

## 🤝 Support

For issues with the build system, please open an issue on the Starlight GitHub repository.
