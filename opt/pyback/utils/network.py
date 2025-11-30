"""
Network utilities.

This module provides network-related utility functions including IP address lookup by MAC.
"""

import os
import logging
import libvirt
from .libvirt_connection import get_connection, get_domain_by_name

logger = logging.getLogger(__name__)


def get_vm_ip_by_mac(mac_address, domain_name=None):
    """
    Looks up the IP address of a VM based on its MAC address.
    For NAT networks: checks the DHCP leases file of the default libvirt NAT network.
    For bridged networks: uses ARP table and optionally libvirt DHCP leases API.
    
    Args:
        mac_address: MAC address to lookup
        domain_name: optional domain name for libvirt API lookup
        
    Returns:
        IP address string or None if not found
    """
    # Try libvirt DHCP leases API first (works for both NAT and some bridge setups)
    if domain_name:
        try:
            conn = get_connection()
            if conn:
                domain = get_domain_by_name(conn, domain_name)
                if domain and domain.isActive():
                    # Get DHCP leases from libvirt (works if using libvirt-managed network)
                    ifaces = domain.interfaceAddresses(libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE)
                    for iface_name, iface_info in ifaces.items():
                        if iface_info.get('addrs'):
                            for addr in iface_info['addrs']:
                                if addr.get('type') == 0:  # IPv4
                                    ip = addr.get('addr')
                                    if ip and not ip.startswith('127.'):
                                        conn.close()
                                        return ip
                conn.close()
        except Exception as e:
            logger.debug(f"Could not get IP via libvirt API: {e}")
    
    # Try ARP table (works well for bridged VMs)
    try:
        with open('/proc/net/arp', 'r') as f:
            arp_content = f.read()
        
        # ARP format: IP address, HW type, Flags, HW address, Mask, Device
        for line in arp_content.splitlines()[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 4:
                arp_mac = parts[3].lower()
                arp_ip = parts[0]
                # Check if MAC matches and it's not incomplete/invalid
                if arp_mac == mac_address.lower() and parts[2] != '0x0':
                    return arp_ip
    except Exception as e:
        logger.debug(f"Error reading ARP table: {e}")
    
    # Fallback: Try legacy leases file for NAT networks
    leases_file = '/var/lib/libvirt/dnsmasq/default.leases'
    try:
        if os.path.exists(leases_file):
            with open(leases_file, 'r') as f:
                content = f.read()
            # Leases format: expiry_time mac_address ip_address hostname client_id
            for line in content.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[1].lower() == mac_address.lower():
                    return parts[2]  # IP address is the third part
    except Exception as e:
        logger.debug(f"Error reading DHCP leases file: {e}")
    
    return None
