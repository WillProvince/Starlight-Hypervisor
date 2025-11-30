#!/bin/bash
# Starlight Hypervisor - ISO Build Script
# Creates a bootable Debian netinst ISO with Starlight pre-configured
# Uses Debian 13 (trixie) as the base

set -e

# Configuration
DEBIAN_VERSION="trixie"
DEBIAN_ARCH="amd64"
DEBIAN_MIRROR="https://cdimage.debian.org/debian-cd/current/amd64/iso-cd"
ISO_NAME="starlight-hypervisor"
WORK_DIR="/tmp/starlight-iso-build"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="${REPO_DIR}/iso-build/output"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check for required tools
check_requirements() {
    echo_info "Checking required tools..."
    
    local missing_tools=()
    
    for tool in genisoimage xorriso isohybrid wget bsdtar; do
        if ! command -v $tool &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        echo_error "Missing required tools: ${missing_tools[*]}"
        echo_info "Install with: apt install genisoimage xorriso syslinux-utils wget libarchive-tools"
        exit 1
    fi
    
    echo_info "All required tools found."
}

# Download Debian netinst ISO
download_debian_iso() {
    echo_info "Checking for Debian netinst ISO..."
    
    mkdir -p "${WORK_DIR}"
    
    # Find latest netinst ISO
    local iso_file="${WORK_DIR}/debian-netinst.iso"
    
    if [ -f "$iso_file" ]; then
        echo_info "Using existing Debian ISO: $iso_file"
        return
    fi
    
    echo_info "Downloading Debian ${DEBIAN_VERSION} netinst ISO..."
    
    # Download Debian 13 (trixie) netinst ISO
    local iso_url="${DEBIAN_MIRROR}/debian-13.2.0-amd64-netinst.iso"
    
    wget -O "$iso_file" "$iso_url" || {
        echo_error "Failed to download Debian ISO"
        echo_info "Please manually download and place at: $iso_file"
        exit 1
    }
    
    echo_info "Downloaded Debian ISO successfully."
}

# Extract ISO contents
extract_iso() {
    echo_info "Extracting ISO contents..."
    
    local iso_file="${WORK_DIR}/debian-netinst.iso"
    local extract_dir="${WORK_DIR}/iso-extract"
    
    # Clean previous extraction
    rm -rf "$extract_dir"
    mkdir -p "$extract_dir"
    
    # Extract ISO using bsdtar (no root/sudo required)
    echo_info "Extracting with bsdtar (no root privileges needed)..."
    bsdtar -xf "$iso_file" -C "$extract_dir"
    
    # Make extracted files writable
    chmod -R u+w "$extract_dir"
    
    echo_info "ISO extracted to: $extract_dir"
}

# Add preseed configuration
add_preseed() {
    echo_info "Adding preseed configuration..."
    
    local extract_dir="${WORK_DIR}/iso-extract"
    
    # Copy preseed file
    cp "${SCRIPT_DIR}/preseed.cfg" "${extract_dir}/preseed.cfg"
    
    echo_info "Preseed configuration added."
}

# Package Starlight files
package_starlight() {
    echo_info "Packaging Starlight files..."
    
    local extract_dir="${WORK_DIR}/iso-extract"
    local starlight_dir="${extract_dir}/starlight"
    
    # Clean and recreate starlight directory to avoid conflicts
    rm -rf "$starlight_dir"
    mkdir -p "$starlight_dir"
    
    # Copy repository files to ISO using git to only include tracked files
    # This avoids copying system files, VM images, or other untracked content
    echo_info "Copying Starlight files from git repository..."
    
    cd "${REPO_DIR}"
    
    # Use git archive to export only tracked files
    if git rev-parse --git-dir > /dev/null 2>&1; then
        echo_info "Using git archive to copy only repository files..."
        git archive HEAD | tar -x -C "$starlight_dir"
    else
        # Fallback: manually copy known directories if not a git repo
        echo_warn "Not a git repository, copying specific directories..."
        cp -r "${REPO_DIR}/opt" "$starlight_dir/"
        mkdir -p "$starlight_dir/var"
        cp -r "${REPO_DIR}/var/www" "$starlight_dir/var/"
        
        # Only copy specific etc subdirectories to avoid system files
        mkdir -p "$starlight_dir/etc"
        [ -d "${REPO_DIR}/etc/systemd" ] && cp -r "${REPO_DIR}/etc/systemd" "$starlight_dir/etc/"
        [ -d "${REPO_DIR}/etc/nginx" ] && cp -r "${REPO_DIR}/etc/nginx" "$starlight_dir/etc/"
        [ -d "${REPO_DIR}/etc/starlight" ] && cp -r "${REPO_DIR}/etc/starlight" "$starlight_dir/etc/" 2>/dev/null || mkdir -p "$starlight_dir/etc/starlight"
        [ -f "${REPO_DIR}/etc/motd" ] && cp "${REPO_DIR}/etc/motd" "$starlight_dir/etc/"
        
        cp -r "${REPO_DIR}/iso-build" "$starlight_dir/"
        [ -d "${REPO_DIR}/scripts" ] && cp -r "${REPO_DIR}/scripts" "$starlight_dir/"
        cp "${REPO_DIR}/requirements.txt" "$starlight_dir/"
        [ -f "${REPO_DIR}/install.sh" ] && cp "${REPO_DIR}/install.sh" "$starlight_dir/"
    fi
    
    echo_info "Starlight files packaged."
}

# Configure boot loader for automated install
configure_bootloader() {
    echo_info "Configuring boot loader for automated installation..."
    
    local extract_dir="${WORK_DIR}/iso-extract"
    
    # Modify ISOLINUX configuration for automatic install
    if [ -f "${extract_dir}/isolinux/isolinux.cfg" ]; then
        cat > "${extract_dir}/isolinux/isolinux.cfg" << 'EOF'
# Starlight Hypervisor Installer - ISOLINUX Configuration
DEFAULT starlight
TIMEOUT 50
PROMPT 0

MENU TITLE Starlight Hypervisor Installer

LABEL starlight
    MENU LABEL ^Install Starlight Hypervisor (Automated)
    KERNEL /install.amd/vmlinuz
    APPEND initrd=/install.amd/initrd.gz auto=true priority=critical preseed/file=/cdrom/preseed.cfg --- quiet

LABEL expert
    MENU LABEL ^Expert Install
    KERNEL /install.amd/vmlinuz
    APPEND initrd=/install.amd/initrd.gz priority=low ---
EOF
    fi
    
    # Modify GRUB configuration for UEFI systems
    if [ -f "${extract_dir}/boot/grub/grub.cfg" ]; then
        cat > "${extract_dir}/boot/grub/grub.cfg" << 'EOF'
# Starlight Hypervisor Installer - GRUB Configuration
set timeout=5
set default=0

menuentry "Install Starlight Hypervisor (Automated)" {
    linux /install.amd/vmlinuz auto=true priority=critical preseed/file=/cdrom/preseed.cfg --- quiet
    initrd /install.amd/initrd.gz
}

menuentry "Expert Install" {
    linux /install.amd/vmlinuz priority=low ---
    initrd /install.amd/initrd.gz
}
EOF
    fi
    
    echo_info "Boot loader configured."
}

# Rebuild ISO
rebuild_iso() {
    echo_info "Rebuilding ISO..."
    
    local extract_dir="${WORK_DIR}/iso-extract"
    mkdir -p "$OUTPUT_DIR"
    
    local output_iso="${OUTPUT_DIR}/${ISO_NAME}-$(date +%F%T).iso"
    
    # Regenerate md5sums
    cd "$extract_dir"
    find . -type f ! -name "md5sum.txt" ! -path "./isolinux/*" -exec md5sum {} \; > md5sum.txt
    
    # Create ISO using xorriso
    xorriso -as mkisofs \
        -r -V "Starlight Hypervisor" \
        -o "$output_iso" \
        -J -joliet-long \
        -b isolinux/isolinux.bin \
        -c isolinux/boot.cat \
        -no-emul-boot \
        -boot-load-size 4 \
        -boot-info-table \
        -eltorito-alt-boot \
        -e boot/grub/efi.img \
        -no-emul-boot \
        -isohybrid-gpt-basdat \
        -isohybrid-mbr /usr/lib/ISOLINUX/isohdpfx.bin \
        "$extract_dir" 2>/dev/null || {
        
        # Fallback to genisoimage if xorriso fails
        echo_warn "xorriso failed, falling back to genisoimage..."
        genisoimage \
            -r -V "Starlight Hypervisor" \
            -o "$output_iso" \
            -J -joliet-long \
            -b isolinux/isolinux.bin \
            -c isolinux/boot.cat \
            -no-emul-boot \
            -boot-load-size 4 \
            -boot-info-table \
            "$extract_dir"
        
        # Make hybrid for USB boot
        isohybrid "$output_iso" 2>/dev/null || echo_warn "isohybrid not available, USB boot may not work"
    }
    
    # Generate checksum
    cd "$OUTPUT_DIR"
    sha256sum "$(basename "$output_iso")" > "$(basename "$output_iso").sha256"
    
    echo_info "ISO created: $output_iso"
    echo_info "Checksum: ${output_iso}.sha256"
}

# Cleanup
cleanup() {
    echo_info "Cleaning up temporary files..."
    rm -rf "${WORK_DIR}/iso-extract"
    echo_info "Cleanup complete. Debian ISO kept for future builds."
}

# Main execution
main() {
    echo "========================================"
    echo "  Starlight Hypervisor ISO Builder"
    echo "========================================"
    echo ""
    
    check_requirements
    download_debian_iso
    extract_iso
    add_preseed
    package_starlight
    configure_bootloader
    rebuild_iso
    cleanup
    
    echo ""
    echo "========================================"
    echo "  Build Complete!"
    echo "========================================"
    echo ""
    echo "Output files in: $OUTPUT_DIR"
    echo ""
    echo "To test with QEMU:"
    echo "  qemu-system-x86_64 -cdrom ${OUTPUT_DIR}/${ISO_NAME}-$(date +%Y%m%d).iso -m 2G -enable-kvm"
    echo ""
    echo "To write to USB:"
    echo "  sudo dd if=${OUTPUT_DIR}/${ISO_NAME}-$(date +%Y%m%d).iso of=/dev/sdX bs=4M status=progress"
    echo ""
}

# Handle arguments
case "${1:-}" in
    --clean)
        echo_info "Full cleanup..."
        rm -rf "${WORK_DIR}"
        rm -rf "${OUTPUT_DIR}"
        echo_info "Done."
        ;;
    --help|-h)
        echo "Usage: $0 [options]"
        echo ""
        echo "Options:"
        echo "  --clean    Remove all build artifacts including cached ISO"
        echo "  --help     Show this help message"
        echo ""
        ;;
    *)
        main
        ;;
esac
