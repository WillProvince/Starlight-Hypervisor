"""
VM data models and metadata management.

This module provides functions for managing VM metadata and extracting
domain information from libvirt.
"""

import os
import json
import logging
import libvirt
from xml.etree import ElementTree as ET
from ..config_loader import VM_METADATA_PATH, get_config_file_path
from ..utils.network import get_vm_ip_by_mac

logger = logging.getLogger(__name__)


def _get_vm_metadata_path():
    """Get the VM metadata path with fallback to legacy."""
    from pathlib import Path
    new_path = VM_METADATA_PATH
    legacy_path = get_config_file_path('vm_metadata', use_legacy=True)
    
    # Return new path if it exists, otherwise check legacy
    if Path(new_path).exists():
        return new_path
    if Path(legacy_path).exists():
        return legacy_path
    # Default to new path for new installations
    return new_path


def load_vm_metadata():
    """Loads VM metadata from JSON file.
    
    Returns:
        dict: VM metadata dictionary
    """
    try:
        metadata_path = _get_vm_metadata_path()
        if not os.path.exists(metadata_path):
            return {}
        with open(metadata_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading VM metadata: {e}")
        return {}


def save_vm_metadata(metadata):
    """Saves VM metadata to JSON file.
    
    Args:
        metadata: VM metadata dictionary to save
        
    Returns:
        bool: True if save succeeded, False otherwise
    """
    try:
        # Always save to new location
        os.makedirs(os.path.dirname(VM_METADATA_PATH), exist_ok=True)
        with open(VM_METADATA_PATH, 'w') as f:
            json.dump(metadata, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving VM metadata: {e}")
        return False


def get_vm_metadata(vm_name):
    """Gets metadata for a specific VM.
    
    Args:
        vm_name: name of the VM
        
    Returns:
        dict: VM metadata or empty dict if not found
    """
    metadata = load_vm_metadata()
    return metadata.get(vm_name, {})


def set_vm_metadata(vm_name, data):
    """Sets metadata for a specific VM.
    
    Args:
        vm_name: name of the VM
        data: metadata dictionary to set/update
    """
    metadata = load_vm_metadata()
    if vm_name not in metadata:
        metadata[vm_name] = {}
    metadata[vm_name].update(data)
    save_vm_metadata(metadata)


def rename_vm_metadata(old_name, new_name):
    """Renames VM in metadata.
    
    Args:
        old_name: current VM name
        new_name: new VM name
    """
    metadata = load_vm_metadata()
    if old_name in metadata:
        metadata[new_name] = metadata.pop(old_name)
        save_vm_metadata(metadata)


def get_domain_info(domain):
    """Extracts relevant info from a virDomain object.
    
    Args:
        domain: libvirt domain object
        
    Returns:
        dict: domain information or None on error
    """
    try:
        info = domain.info()
        state = info[0] 
        xml_desc = domain.XMLDesc(0)
        root = ET.fromstring(xml_desc)
        uuid = root.find('uuid').text

        mac_address = None
        interface = root.find("./devices/interface[@type='network']/mac")
        if interface is not None:
            mac_address = interface.get('address')
            
        vm_ip = None
        if domain.isActive() and mac_address:
            vm_ip = get_vm_ip_by_mac(mac_address, domain.name())
            
        vnc_port = None
        graphics = root.find("./devices/graphics[@type='vnc']")
        if graphics is not None and domain.isActive():
            vnc_port_str = graphics.get('port')
            if vnc_port_str is not None and vnc_port_str != '-1':
                try:
                    vnc_port = int(vnc_port_str)
                except ValueError:
                    vnc_port = None
        
        # Get video RAM
        video = root.find("./devices/video/model")
        vram = 128  # Default
        if video is not None:
            vram_attr = video.get('vram')
            if vram_attr:
                vram = int(vram_attr) // 1024  # Convert KiB to MiB
        
        # Check for audio device
        audio = root.find("./devices/sound") is not None
        
        # Get metadata
        vm_metadata = get_vm_metadata(domain.name())

        return {
            'name': domain.name(),
            'id': domain.ID() if domain.isActive() else None,
            'uuid': uuid,
            'state': state,
            'vnc_port': vnc_port, 
            'ip_address': vm_ip, 
            'memory': info[2] / 1024, 
            'vcpus': info[3],
            'autostart': domain.autostart(),
            'vram': vram,
            'audio': audio,
            'description': vm_metadata.get('description', ''),
            'resolution': vm_metadata.get('resolution', '1920x1080'),
        }
    except libvirt.libvirtError as e:
        logger.error(f"Error getting info for domain {domain.name()}: {e}")
        return None
