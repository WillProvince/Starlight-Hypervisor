"""
VM management API handlers.

This module provides HTTP request handlers for VM operations including
listing, creating, getting disk info, and updating VM settings.
"""

import os
import json
import logging
import asyncio
import random
import libvirt
from aiohttp import web
from xml.etree import ElementTree as ET

from ..config_loader import (
    get_network_mode, get_bridge_name, get_nat_network_name,
    get_vm_storage_path, get_default_pool_name
)
from ..utils.libvirt_connection import get_connection, get_domain_by_name
from ..utils.file_operations import sanitize_vm_name
from ..models.vm import get_domain_info, get_vm_metadata, set_vm_metadata, rename_vm_metadata
from ..models.lxc import get_lxc_metadata
from ..storage.volume import create_storage_volume

logger = logging.getLogger(__name__)


async def list_vms(request):
    """Returns a list of all defined and running VMs and LXC containers."""
    vm_list = []
    
    # Get VMs from QEMU
    conn = get_connection('qemu')
    if conn:
        try:
            domains = conn.listAllDomains(libvirt.VIR_CONNECT_LIST_DOMAINS_ACTIVE | libvirt.VIR_CONNECT_LIST_DOMAINS_INACTIVE)
            
            for domain in domains:
                info = get_domain_info(domain)
                if info:
                    # Mark as VM type and include metadata
                    vm_metadata = get_vm_metadata(domain.name())
                    info['type'] = vm_metadata.get('type', 'vm')
                    if 'icon' in vm_metadata:
                        info['icon'] = vm_metadata['icon']
                    if 'app_name' in vm_metadata:
                        info['app_name'] = vm_metadata['app_name']
                    vm_list.append(info)
            
            conn.close()
        except Exception as e:
            logger.error(f"Error listing VMs: {e}")
    
    # Get LXC containers
    lxc_conn = get_connection('lxc')
    if lxc_conn:
        try:
            containers = lxc_conn.listAllDomains(libvirt.VIR_CONNECT_LIST_DOMAINS_ACTIVE | libvirt.VIR_CONNECT_LIST_DOMAINS_INACTIVE)
            
            for container in containers:
                info = get_domain_info(container)
                if info:
                    # Mark as LXC type and include metadata
                    lxc_metadata = get_lxc_metadata(container.name())
                    info['type'] = 'lxc'
                    info['description'] = lxc_metadata.get('description', '')
                    if 'icon' in lxc_metadata:
                        info['icon'] = lxc_metadata['icon']
                    if 'app_name' in lxc_metadata:
                        info['app_name'] = lxc_metadata['app_name']
                    vm_list.append(info)
            
            lxc_conn.close()
        except Exception as e:
            logger.error(f"Error listing LXC containers: {e}")
    
    if not conn and not lxc_conn:
        return web.json_response({'status': 'error', 'message': 'Could not connect to libvirt.'}, status=500)
    
    return web.json_response({'status': 'success', 'vms': vm_list})


async def create_vm(request):
    """Defines a persistent VM and starts it immediately."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({'status': 'error', 'message': 'Invalid JSON body.'}, status=400)
        
    name = data.get('name')
    memory_mb = data.get('memory_mb')
    vcpus = data.get('vcpus')
    iso_path = data.get('iso_path') 
    disk_size_gb = data.get('disk_size_gb')

    if not all([name, memory_mb, vcpus, disk_size_gb]):
        return web.json_response({'status': 'error', 'message': 'Missing name, memory, vcpus, or disk_size_gb.'}, status=400)

    conn = get_connection()
    if not conn:
        return web.json_response({'status': 'error', 'message': 'Could not connect to libvirt.'}, status=500)
    
    if get_domain_by_name(conn, name):
        conn.close()
        return web.json_response({'status': 'error', 'message': f'VM named {name} already exists.'}, status=409)

    # 1. Create the virtual disk image
    try:
        disk_path = create_storage_volume(conn, name, disk_size_gb)
    except Exception as e:
        conn.close()
        return web.json_response({'status': 'error', 'message': f'Disk creation failed: {e}'}, status=500)
        
    # 2. Build XML Configuration
    memory_kib = memory_mb * 1024
    
    disk_config = f"""
        <disk type='file' device='disk'>
          <driver name='qemu' type='qcow2'/>
          <source file='{disk_path}'/>
          <target dev='vda' bus='virtio'/>
        </disk>
    """
    
    boot_devices = "<boot dev='hd'/>" 

    if iso_path:
        if not os.path.isfile(iso_path):
            conn.close()
            return web.json_response({'status': 'error', 'message': f"ISO file not found at path: {iso_path}."}, status=400)

        disk_config += f"""
        <disk type='file' device='cdrom'>
          <driver name='qemu' type='raw'/>
          <source file='{iso_path}'/>
          <target dev='hdc' bus='sata'/>
          <readonly/>
        </disk>
        """
        boot_devices = "<boot dev='cdrom'/><boot dev='hd'/>" 

    mac_prefix = "52:54:00" 
    mac_suffix = ":".join(["{:02x}".format(random.randint(0x00, 0xff)) for _ in range(3)])
    mac_address = f"{mac_prefix}:{mac_suffix}"

    # Configure network interface based on mode (loaded dynamically)
    network_mode = get_network_mode()
    bridge_name = get_bridge_name()
    nat_network_name = get_nat_network_name()
    
    if network_mode == 'bridge':
        network_interface = f"""
        <interface type='bridge'>
          <source bridge='{bridge_name}'/>
          <model type='virtio'/>
          <mac address='{mac_address}'/>
        </interface>"""
    else:
        network_interface = f"""
        <interface type='network'>
          <source network='{nat_network_name}'/>
          <model type='virtio'/>
          <mac address='{mac_address}'/>
        </interface>"""

    xml_config = f"""
    <domain type='kvm'>
      <name>{name}</name>
      <memory unit='KiB'>{memory_kib}</memory>
      <currentMemory unit='KiB'>{memory_kib}</currentMemory>
      <vcpu placement='static'>{vcpus}</vcpu>
      <os>
        <type arch='x86_64' machine='pc'>hvm</type>
        {boot_devices} 
      </os>
      <features>
        <acpi/>
        <apic/>
        <pae/>
      </features>
      <seclabel type='none' model='apparmor'/>
      <devices>
        <emulator>/usr/bin/qemu-system-x86_64</emulator>
        {disk_config} 
        {network_interface}
        <!-- VNC graphics: port=-1 enables automatic port assignment (5900+) -->
        <graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0'/>
        <console type='pty'/>
        <input type='mouse' bus='ps2'/>
        <input type='keyboard' bus='ps2'/>
        <memballoon model='virtio'/>
      </devices>
    </domain>
    """
    
    try:
        # 3. Define and Start the domain
        domain = conn.defineXML(xml_config)
        
        if domain is None:
            raise Exception("Libvirt failed to define the domain from XML.")
        
        domain.create()
        
        conn.close()
        return web.json_response({'status': 'success', 'message': f'Domain {name} defined and started persistently with a {disk_size_gb}GB disk.'})
    
    except libvirt.libvirtError as e:
        conn.close()
        return web.json_response({'status': 'error', 'message': f'Libvirt operation failed: {e}'}, status=500)
    except Exception as e:
        conn.close()
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)


async def get_vm_disk_info(request):
    """Gets disk size information for a VM."""
    name = request.match_info.get('name')
    
    conn = get_connection()
    if not conn:
        return web.json_response({'status': 'error', 'message': 'Could not connect to libvirt.'}, status=500)
    
    domain = get_domain_by_name(conn, name)
    if not domain:
        conn.close()
        return web.json_response({'status': 'error', 'message': f'VM named {name} not found.'}, status=404)
    
    try:
        # Get XML and extract disk path
        xml_desc = domain.XMLDesc(libvirt.VIR_DOMAIN_XML_INACTIVE)
        root = ET.fromstring(xml_desc)
        
        disk_element = root.find("./devices/disk[@type='file'][@device='disk']")
        if disk_element is None:
            conn.close()
            return web.json_response({'status': 'error', 'message': 'No disk found for this VM.'}, status=404)
        
        source_element = disk_element.find('source')
        if source_element is None:
            conn.close()
            return web.json_response({'status': 'error', 'message': 'Disk has no source path.'}, status=404)
        
        disk_path = source_element.get('file')
        if not disk_path or not os.path.exists(disk_path):
            conn.close()
            return web.json_response({'status': 'error', 'message': f'Disk file not found at {disk_path}'}, status=404)
        
        # Use qemu-img to get disk size
        process = await asyncio.create_subprocess_exec(
            'qemu-img', 'info', '--output=json', disk_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            conn.close()
            return web.json_response({'status': 'error', 'message': f'Failed to get disk info: {stderr.decode()}'}, status=500)
        
        import json as json_module
        disk_info = json_module.loads(stdout.decode())
        virtual_size_bytes = disk_info.get('virtual-size', 0)
        virtual_size_gb = virtual_size_bytes / (1024**3)
        
        conn.close()
        return web.json_response({
            'status': 'success',
            'disk_size_gb': round(virtual_size_gb, 2),
            'disk_path': disk_path,
            'format': disk_info.get('format', 'unknown')
        })
        
    except Exception as e:
        conn.close()
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)


async def update_vm_settings(request):
    """Updates VM settings (memory, vcpus, disk size, name, description, autostart, vram, audio, resolution)."""
    name = request.match_info.get('name')
    
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return web.json_response({'status': 'error', 'message': 'Invalid JSON body.'}, status=400)
    
    memory_mb = data.get('memory_mb')
    vcpus = data.get('vcpus')
    disk_size_gb = data.get('disk_size_gb')
    new_name = data.get('new_name')
    description = data.get('description')
    autostart = data.get('autostart')
    vram_mb = data.get('vram_mb')
    audio_enabled = data.get('audio_enabled')
    resolution = data.get('resolution')
    
    if not any([memory_mb, vcpus, disk_size_gb, new_name, description is not None, 
                autostart is not None, vram_mb, audio_enabled is not None, resolution]):
        return web.json_response({'status': 'error', 'message': 'No settings to update.'}, status=400)
    
    conn = get_connection()
    if not conn:
        return web.json_response({'status': 'error', 'message': 'Could not connect to libvirt.'}, status=500)
    
    domain = get_domain_by_name(conn, name)
    if not domain:
        conn.close()
        return web.json_response({'status': 'error', 'message': f'VM named {name} not found.'}, status=404)
    
    # Check if VM is running for operations that require shutdown
    is_running = domain.isActive()
    requires_shutdown = memory_mb or vcpus or disk_size_gb or new_name or vram_mb or audio_enabled is not None
    
    if is_running and requires_shutdown:
        conn.close()
        return web.json_response({'status': 'error', 'message': f'VM {name} must be shut down before modifying these settings.'}, status=400)
    
    # Handle metadata updates (can be done while running)
    if description is not None or resolution:
        metadata_updates = {}
        if description is not None:
            metadata_updates['description'] = description
        if resolution:
            metadata_updates['resolution'] = resolution
        set_vm_metadata(name, metadata_updates)
        logger.info(f"Updated metadata for VM {name}")
    
    # Handle autostart toggle (can be done while running)
    if autostart is not None:
        try:
            if autostart:
                domain.setAutostart(1)
                logger.info(f"Enabled autostart for VM {name}")
            else:
                domain.setAutostart(0)
                logger.info(f"Disabled autostart for VM {name}")
        except libvirt.libvirtError as e:
            logger.error(f"Failed to set autostart for VM {name}: {e}")
    
    # If no XML changes needed, return success
    if not (memory_mb or vcpus or disk_size_gb or new_name or vram_mb or audio_enabled is not None):
        conn.close()
        changes = []
        if description is not None:
            changes.append('Description')
        if resolution:
            changes.append(f'Resolution: {resolution}')
        if autostart is not None:
            changes.append(f'Autostart: {"enabled" if autostart else "disabled"}')
        return web.json_response({
            'status': 'success',
            'message': f'VM {name} settings updated successfully. Changes: {", ".join(changes)}'
        })
    
    try:
        # Get current XML configuration
        xml_desc = domain.XMLDesc(libvirt.VIR_DOMAIN_XML_INACTIVE)
        root = ET.fromstring(xml_desc)
        
        # Handle disk resizing first (if requested)
        if disk_size_gb:
            disk_element = root.find("./devices/disk[@type='file'][@device='disk']")
            if disk_element is not None:
                source_element = disk_element.find('source')
                if source_element is not None:
                    disk_path = source_element.get('file')
                    if disk_path and os.path.exists(disk_path):
                        logger.info(f"Resizing disk {disk_path} to {disk_size_gb}GB")
                        
                        # Use qemu-img to resize the disk
                        process = await asyncio.create_subprocess_exec(
                            'qemu-img', 'resize', disk_path, f'{disk_size_gb}G',
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await process.communicate()
                        
                        if process.returncode != 0:
                            error_msg = stderr.decode() if stderr else "Unknown error"
                            # Check if it's a "shrink" error
                            if "shrink" in error_msg.lower():
                                conn.close()
                                return web.json_response({
                                    'status': 'error', 
                                    'message': 'Cannot shrink disk. Disk can only be expanded.'
                                }, status=400)
                            else:
                                conn.close()
                                return web.json_response({
                                    'status': 'error', 
                                    'message': f'Failed to resize disk: {error_msg}'
                                }, status=500)
                        
                        logger.info(f"Disk resized successfully to {disk_size_gb}GB")
        
        # Update memory if provided
        if memory_mb:
            memory_kib = memory_mb * 1024
            
            memory_element = root.find('memory')
            if memory_element is not None:
                memory_element.text = str(memory_kib)
                memory_element.set('unit', 'KiB')
            
            current_memory_element = root.find('currentMemory')
            if current_memory_element is not None:
                current_memory_element.text = str(memory_kib)
                current_memory_element.set('unit', 'KiB')
        
        # Update vCPUs if provided
        if vcpus:
            vcpu_element = root.find('vcpu')
            if vcpu_element is not None:
                vcpu_element.text = str(vcpus)
        
        # Update video RAM if provided
        if vram_mb:
            devices = root.find('devices')
            if devices is not None:
                # Find or create video device
                video = devices.find('video')
                if video is None:
                    video = ET.SubElement(devices, 'video')
                
                model = video.find('model')
                if model is None:
                    model = ET.SubElement(video, 'model')
                    model.set('type', 'qxl')  # Use QXL for better performance
                
                # VRAM is in KiB for libvirt
                model.set('vram', str(vram_mb * 1024))
                model.set('heads', '1')
                logger.info(f"Set VRAM to {vram_mb}MB for VM {name}")
        
        # Update audio device if provided
        if audio_enabled is not None:
            devices = root.find('devices')
            if devices is not None:
                # Remove existing sound devices
                for sound in devices.findall('sound'):
                    devices.remove(sound)
                
                # Add sound device if enabled
                if audio_enabled:
                    sound = ET.SubElement(devices, 'sound')
                    sound.set('model', 'ich9')  # Modern audio controller
                    logger.info(f"Enabled audio for VM {name}")
                else:
                    logger.info(f"Disabled audio for VM {name}")
        
        # Handle VM renaming (disk file must be renamed before XML update)
        disk_renamed = False
        sanitized_new_name = None
        if new_name and new_name != name:
            # Sanitize the new name for filesystem
            sanitized_new_name = sanitize_vm_name(new_name)
            logger.info(f"Sanitized VM name: {new_name} -> {sanitized_new_name}")
            
            # Get storage path dynamically
            storage_path = get_vm_storage_path()
            
            # Get current disk path from XML
            disk_element = root.find("./devices/disk[@type='file'][@device='disk']")
            if disk_element is not None:
                source_element = disk_element.find('source')
                if source_element is not None:
                    old_disk_path = source_element.get('file')
                    
                    if old_disk_path and os.path.exists(old_disk_path):
                        # Rename the disk file before updating the XML configuration
                        new_disk_path = f"{storage_path}/{sanitized_new_name}.qcow2"
                        try:
                            os.rename(old_disk_path, new_disk_path)
                            logger.info(f"Renamed disk from {old_disk_path} to {new_disk_path}")
                            disk_renamed = True
                            
                            # Update the disk path in XML to match the renamed file
                            source_element.set('file', new_disk_path)
                            logger.info(f"Updated disk path in XML to {new_disk_path}")
                        except Exception as e:
                            logger.error(f"Could not rename disk file: {e}")
                            conn.close()
                            return web.json_response({'status': 'error', 'message': f'Failed to rename disk file: {e}'}, status=500)
            
            # Update VM name in XML
            name_element = root.find('name')
            if name_element is not None:
                name_element.text = new_name
                logger.info(f"Updated VM name in XML from {name} to {new_name}")
        
        # Convert back to XML string
        modified_xml = ET.tostring(root, encoding='unicode')
        
        # Undefine the old domain and define with new settings
        # Use flags to handle NVRAM (UEFI) VMs properly
        try:
            # Try to undefine while keeping NVRAM (important for UEFI VMs)
            undefine_flags = (libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE | 
                             libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA | 
                             libvirt.VIR_DOMAIN_UNDEFINE_KEEP_NVRAM)  # Keep NVRAM when updating settings
            domain.undefineFlags(undefine_flags)
            logger.info(f"Successfully undefined VM {name} with NVRAM preservation")
        except libvirt.libvirtError as e:
            # If KEEP_NVRAM fails, the VM might not have NVRAM - try regular undefine
            logger.warning(f"Could not undefine with KEEP_NVRAM flag, trying regular undefine: {e}")
            try:
                domain.undefine()
            except libvirt.libvirtError as e2:
                # Last resort: try without any flags
                logger.error(f"Regular undefine also failed: {e2}")
                # If we renamed the disk, try to rename it back
                if disk_renamed and sanitized_new_name:
                    storage_path = get_vm_storage_path()
                    try:
                        os.rename(f"{storage_path}/{sanitized_new_name}.qcow2", 
                                 f"{storage_path}/{name}.qcow2")
                        logger.info(f"Rolled back disk rename")
                    except:
                        pass
                raise Exception(f"Could not undefine VM for settings update: {e2}")
        
        new_domain = conn.defineXML(modified_xml)
        
        if new_domain is None:
            raise Exception("Failed to redefine VM with new settings.")
        
        # Update metadata for renamed VM
        if new_name and new_name != name:
            rename_vm_metadata(name, new_name)
            logger.info(f"Updated metadata from {name} to {new_name}")
        
        conn.close()
        
        # Build changes list
        changes = []
        if new_name and new_name != name:
            changes.append(f'Name: {name} → {new_name}')
        if description is not None:
            changes.append('Description updated')
        if memory_mb:
            changes.append(f'Memory: {memory_mb}MB')
        if vcpus:
            changes.append(f'vCPUs: {vcpus}')
        if disk_size_gb:
            changes.append(f'Disk: {disk_size_gb}GB')
        if autostart is not None:
            changes.append(f'Autostart: {"enabled" if autostart else "disabled"}')
        if vram_mb:
            changes.append(f'VRAM: {vram_mb}MB')
        if audio_enabled is not None:
            changes.append(f'Audio: {"enabled" if audio_enabled else "disabled"}')
        if resolution:
            changes.append(f'Resolution hint: {resolution}')
        
        final_name = new_name if new_name and new_name != name else name
        return web.json_response({
            'status': 'success', 
            'message': f'VM settings updated successfully. Changes: {", ".join(changes)}'
        })
        
    except libvirt.libvirtError as e:
        conn.close()
        return web.json_response({'status': 'error', 'message': f'Libvirt operation failed: {e}'}, status=500)
    except Exception as e:
        conn.close()
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)


async def get_host_specs(request):
    """
    Get host system specifications for setting slider maximums.
    
    Returns CPU count and total memory of the host system.
    """
    conn = None
    try:
        conn = get_connection('qemu')
        if not conn:
            return web.json_response({
                'status': 'error', 
                'message': 'Could not connect to libvirt.'
            }, status=500)
        
        # Get host info: returns tuple (model, memory_mb, cpus, mhz, nodes, sockets, cores, threads)
        host_info = conn.getInfo()
        
        # Total memory in MB
        total_memory_mb = host_info[1]
        
        # Total CPU cores
        total_cpus = host_info[2]
        
        conn.close()
        
        return web.json_response({
            'status': 'success',
            'total_memory_mb': total_memory_mb,
            'total_cpus': total_cpus
        })
        
    except libvirt.libvirtError as e:
        logger.error(f"Libvirt error getting host specs: {e}")
        if conn:
            conn.close()
        return web.json_response({
            'status': 'error', 
            'message': f'Libvirt operation failed: {e}'
        }, status=500)
    except Exception as e:
        logger.error(f"Error getting host specs: {e}")
        if conn:
            conn.close()
        return web.json_response({
            'status': 'error', 
            'message': str(e)
        }, status=500)
