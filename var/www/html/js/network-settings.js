/**
 * Network Settings Module
 * Handles network configuration management in the Settings page
 */

// Network settings state
let currentNetworkConfig = null;
let networkStatus = null;
let lastNetworkDataLoad = 0;
const NETWORK_DATA_CACHE_MS = 5000; // 5 seconds cache to prevent excessive API calls

/**
 * Load network configuration from API
 */
async function loadNetworkConfig() {
    const result = await window.API.apiCall('/network/config');
    if (result && result.status === 'success') {
        currentNetworkConfig = result.config;
        renderNetworkConfig(result.config);
    } else {
        console.error('Failed to load network config:', result);
    }
}

/**
 * Load network status (current system state) from API
 */
async function loadNetworkStatus() {
    const result = await window.API.apiCall('/network/status');
    if (result && result.status === 'success') {
        networkStatus = result.network_status;
        renderNetworkStatus(result.network_status);
    } else {
        console.error('Failed to load network status:', result);
    }
}

/**
 * Load network data with caching to prevent excessive API calls
 */
async function loadNetworkDataIfNeeded() {
    const now = Date.now();
    if (now - lastNetworkDataLoad > NETWORK_DATA_CACHE_MS) {
        lastNetworkDataLoad = now;
        await Promise.all([loadNetworkConfig(), loadNetworkStatus()]);
    }
}

/**
 * Render network configuration into form fields
 */
function renderNetworkConfig(config) {
    const modeEl = document.getElementById('network-mode');
    const hostnameEl = document.getElementById('network-hostname');
    const ipEl = document.getElementById('network-ip');
    const netmaskEl = document.getElementById('network-netmask');
    const gatewayEl = document.getElementById('network-gateway');
    const dnsPrimaryEl = document.getElementById('network-dns-primary');
    const dnsSecondaryEl = document.getElementById('network-dns-secondary');
    
    if (modeEl) modeEl.value = config.mode || 'dhcp';
    if (hostnameEl) hostnameEl.value = config.hostname || '';
    if (ipEl) ipEl.value = config.ip_address || '';
    if (netmaskEl) netmaskEl.value = config.netmask || '255.255.255.0';
    if (gatewayEl) gatewayEl.value = config.gateway || '';
    if (dnsPrimaryEl) dnsPrimaryEl.value = config.dns_primary || '8.8.8.8';
    if (dnsSecondaryEl) dnsSecondaryEl.value = config.dns_secondary || '1.1.1.1';
    
    // Update static fields visibility
    toggleStaticNetworkFields();
}

/**
 * Render current network status
 */
function renderNetworkStatus(status) {
    const statusEl = document.getElementById('network-status-info');
    
    if (statusEl && status) {
        const dnsServers = status.dns_servers && status.dns_servers.length > 0 
            ? status.dns_servers.join(', ') 
            : 'Not configured';
        
        statusEl.innerHTML = `
            <div class="flex justify-between items-center">
                <span style="color: var(--text-secondary);">Current IP:</span>
                <span class="font-mono" style="color: var(--text-primary);">${status.ip_address || 'Unknown'}</span>
            </div>
            <div class="flex justify-between items-center">
                <span style="color: var(--text-secondary);">Hostname:</span>
                <span class="font-mono" style="color: var(--text-primary);">${status.hostname || 'Unknown'}</span>
            </div>
            <div class="flex justify-between items-center">
                <span style="color: var(--text-secondary);">Interface:</span>
                <span class="font-mono" style="color: var(--text-primary);">${status.interface || 'Unknown'}</span>
            </div>
            <div class="flex justify-between items-center">
                <span style="color: var(--text-secondary);">DNS Servers:</span>
                <span class="font-mono" style="color: var(--text-primary);">${dnsServers}</span>
            </div>
        `;
    }
}

/**
 * Toggle visibility of static IP fields based on mode selection
 */
function toggleStaticNetworkFields() {
    const modeEl = document.getElementById('network-mode');
    const staticFieldsEl = document.getElementById('static-network-fields');
    
    if (modeEl && staticFieldsEl) {
        if (modeEl.value === 'static') {
            staticFieldsEl.classList.remove('hidden');
        } else {
            staticFieldsEl.classList.add('hidden');
        }
    }
}

/**
 * Validate IP address format
 */
function validateIpAddress(ip) {
    if (!ip) return true; // Empty is allowed for optional fields
    const ipPattern = /^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return ipPattern.test(ip);
}

/**
 * Validate hostname format
 * Regex ensures: starts/ends with alphanumeric, max 63 chars, allows hyphens in middle
 */
function validateHostname(hostname) {
    if (!hostname) return true; // Empty is allowed
    const hostnamePattern = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$/;
    return hostnamePattern.test(hostname);
}

/**
 * Save network configuration
 */
async function saveNetworkConfig() {
    const mode = document.getElementById('network-mode')?.value || 'dhcp';
    const hostname = document.getElementById('network-hostname')?.value?.trim() || '';
    const ipAddress = document.getElementById('network-ip')?.value?.trim() || '';
    const netmask = document.getElementById('network-netmask')?.value?.trim() || '255.255.255.0';
    const gateway = document.getElementById('network-gateway')?.value?.trim() || '';
    const dnsPrimary = document.getElementById('network-dns-primary')?.value?.trim() || '8.8.8.8';
    const dnsSecondary = document.getElementById('network-dns-secondary')?.value?.trim() || '1.1.1.1';
    
    // Client-side validation
    const errors = [];
    
    if (hostname && !validateHostname(hostname)) {
        errors.push('Invalid hostname format. Use only letters, numbers, and hyphens.');
    }
    
    if (mode === 'static') {
        if (!ipAddress) {
            errors.push('IP address is required for static mode.');
        } else if (!validateIpAddress(ipAddress)) {
            errors.push('Invalid IP address format.');
        }
        
        if (netmask && !validateIpAddress(netmask)) {
            errors.push('Invalid netmask format.');
        }
        
        if (gateway && !validateIpAddress(gateway)) {
            errors.push('Invalid gateway format.');
        }
    }
    
    if (dnsPrimary && !validateIpAddress(dnsPrimary)) {
        errors.push('Invalid primary DNS format.');
    }
    
    if (dnsSecondary && !validateIpAddress(dnsSecondary)) {
        errors.push('Invalid secondary DNS format.');
    }
    
    if (errors.length > 0) {
        window.UI.showStatus(errors.join(' '), 'error');
        return;
    }
    
    const config = {
        mode: mode,
        hostname: hostname,
        ip_address: ipAddress,
        netmask: netmask,
        gateway: gateway,
        dns_primary: dnsPrimary,
        dns_secondary: dnsSecondary
    };
    
    const result = await window.API.apiCall('/network/config', 'POST', config);
    
    if (result && result.status === 'success') {
        window.UI.showStatus('Network configuration saved successfully', 'success');
        currentNetworkConfig = result.config || config;
        
        if (result.apply_required) {
            // Show additional info about applying changes
            setTimeout(() => {
                window.UI.showStatus('Note: Some changes may require a system restart to take effect.', 'info');
            }, 2000);
        }
    } else {
        const errorMsg = result?.errors?.join(', ') || result?.message || 'Failed to save configuration';
        window.UI.showStatus(errorMsg, 'error');
    }
}

/**
 * Refresh network status information
 */
async function refreshNetworkStatus() {
    const refreshBtn = document.getElementById('network-refresh-btn');
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = `
            <svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
        `;
    }
    
    await Promise.all([loadNetworkConfig(), loadNetworkStatus()]);
    
    if (refreshBtn) {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
        `;
    }
    
    window.UI.showStatus('Network information refreshed', 'success');
}

/**
 * Initialize network settings module
 */
function initNetworkSettings() {
    // Load network configuration when the settings page is shown
    const settingsPage = document.getElementById('page-settings');
    if (settingsPage) {
        // MutationObserver to detect when settings page becomes visible
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    if (settingsPage.classList.contains('active')) {
                        // Use cached loader to prevent excessive API calls
                        loadNetworkDataIfNeeded();
                    }
                }
            });
        });
        
        observer.observe(settingsPage, { attributes: true });
    }
}

// Export Network Settings functions
window.NetworkSettings = {
    loadNetworkConfig,
    loadNetworkStatus,
    loadNetworkDataIfNeeded,
    saveNetworkConfig,
    refreshNetworkStatus,
    toggleStaticNetworkFields,
    initNetworkSettings
};

// Expose functions globally for onclick handlers
window.saveNetworkConfig = saveNetworkConfig;
window.refreshNetworkStatus = refreshNetworkStatus;
window.toggleStaticNetworkFields = toggleStaticNetworkFields;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', initNetworkSettings);
