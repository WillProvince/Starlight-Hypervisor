/**
 * Storage Settings Module
 * Handles storage configuration management in the Settings page
 */

// Storage settings state
let currentStorageConfig = null;
let storageInfo = null;

/**
 * Format bytes to human readable string
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Calculate percentage
 */
function calculatePercentage(used, total) {
    if (total === 0) return 0;
    return Math.round((used / total) * 100);
}

/**
 * Get progress bar color class based on usage percentage
 */
function getProgressBarColorClass(usedPercent) {
    if (usedPercent > 90) return 'bg-red-600';
    if (usedPercent > 70) return 'bg-yellow-500';
    return 'bg-green-600';
}

/**
 * Load storage configuration from API
 */
async function loadStorageConfig() {
    const result = await window.API.apiCall('/storage/config');
    if (result && result.status === 'success') {
        currentStorageConfig = result.config;
        renderStorageConfig(result.config);
    } else {
        console.error('Failed to load storage config:', result);
    }
}

/**
 * Load storage info (disk space) from API
 */
async function loadStorageInfo() {
    const result = await window.API.apiCall('/storage/info');
    if (result && result.status === 'success') {
        storageInfo = result.info;
        renderStorageInfo(result.info);
    } else {
        console.error('Failed to load storage info:', result);
    }
}

/**
 * Render storage configuration
 */
function renderStorageConfig(config) {
    const vmPathEl = document.getElementById('storage-vm-path');
    const isoPathEl = document.getElementById('storage-iso-path');
    const poolNameEl = document.getElementById('storage-pool-name');
    
    if (vmPathEl) vmPathEl.value = config.vm_storage_path || '/var/lib/libvirt/images';
    if (isoPathEl) isoPathEl.value = config.iso_storage_path || '/var/lib/libvirt/isos';
    if (poolNameEl) poolNameEl.value = config.default_pool_name || 'default';
}

/**
 * Render storage info
 */
function renderStorageInfo(info) {
    const vmInfoEl = document.getElementById('storage-vm-info');
    const isoInfoEl = document.getElementById('storage-iso-info');
    
    if (vmInfoEl && info.vm_storage) {
        const vm = info.vm_storage;
        const usedPercent = calculatePercentage(vm.used_bytes, vm.total_bytes);
        const progressBarColor = getProgressBarColorClass(usedPercent);
        vmInfoEl.innerHTML = `
            <div class="flex justify-between items-center mb-2">
                <span style="color: var(--text-secondary);">Total Space:</span>
                <span style="color: var(--text-primary);">${formatBytes(vm.total_bytes)}</span>
            </div>
            <div class="flex justify-between items-center mb-2">
                <span style="color: var(--text-secondary);">Available:</span>
                <span style="color: var(--text-primary);">${formatBytes(vm.available_bytes)}</span>
            </div>
            <div class="flex justify-between items-center mb-2">
                <span style="color: var(--text-secondary);">Used:</span>
                <span style="color: var(--text-primary);">${formatBytes(vm.used_bytes)} (${usedPercent}%)</span>
            </div>
            <div class="flex justify-between items-center mb-2">
                <span style="color: var(--text-secondary);">VM Files:</span>
                <span style="color: var(--text-primary);">${vm.file_count || 0} files (${formatBytes(vm.content_size_bytes || 0)})</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2.5 mt-2" style="background-color: var(--bg-tertiary);">
                <div class="h-2.5 rounded-full ${progressBarColor}" style="width: ${usedPercent}%"></div>
            </div>
            <div class="flex items-center mt-2 text-sm">
                <span class="${vm.exists ? 'text-green-600' : 'text-red-600'}">
                    ${vm.exists ? '✓ Path exists' : '✗ Path does not exist'}
                </span>
                <span class="mx-2">|</span>
                <span class="${vm.writable ? 'text-green-600' : 'text-red-600'}">
                    ${vm.writable ? '✓ Writable' : '✗ Not writable'}
                </span>
            </div>
        `;
    }
    
    if (isoInfoEl && info.iso_storage) {
        const iso = info.iso_storage;
        const usedPercent = calculatePercentage(iso.used_bytes, iso.total_bytes);
        const progressBarColor = getProgressBarColorClass(usedPercent);
        isoInfoEl.innerHTML = `
            <div class="flex justify-between items-center mb-2">
                <span style="color: var(--text-secondary);">Total Space:</span>
                <span style="color: var(--text-primary);">${formatBytes(iso.total_bytes)}</span>
            </div>
            <div class="flex justify-between items-center mb-2">
                <span style="color: var(--text-secondary);">Available:</span>
                <span style="color: var(--text-primary);">${formatBytes(iso.available_bytes)}</span>
            </div>
            <div class="flex justify-between items-center mb-2">
                <span style="color: var(--text-secondary);">ISO Files:</span>
                <span style="color: var(--text-primary);">${iso.file_count || 0} files (${formatBytes(iso.content_size_bytes || 0)})</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2.5 mt-2" style="background-color: var(--bg-tertiary);">
                <div class="h-2.5 rounded-full ${progressBarColor}" style="width: ${usedPercent}%"></div>
            </div>
            <div class="flex items-center mt-2 text-sm">
                <span class="${iso.exists ? 'text-green-600' : 'text-red-600'}">
                    ${iso.exists ? '✓ Path exists' : '✗ Path does not exist'}
                </span>
                <span class="mx-2">|</span>
                <span class="${iso.writable ? 'text-green-600' : 'text-red-600'}">
                    ${iso.writable ? '✓ Writable' : '✗ Not writable'}
                </span>
            </div>
        `;
    }
}

/**
 * Validate a storage path via API
 */
async function validateStoragePath(path) {
    const result = await window.API.apiCall('/storage/validate', 'POST', { path });
    return result;
}

/**
 * Save storage configuration
 */
async function saveStorageConfig() {
    const vmPath = document.getElementById('storage-vm-path')?.value?.trim();
    const isoPath = document.getElementById('storage-iso-path')?.value?.trim();
    const poolName = document.getElementById('storage-pool-name')?.value?.trim();
    
    if (!vmPath) {
        window.UI.showStatus('VM storage path is required', 'error');
        return;
    }
    
    // Show warning if changing paths
    if (currentStorageConfig && (vmPath !== currentStorageConfig.vm_storage_path || isoPath !== currentStorageConfig.iso_storage_path)) {
        // Use a simpler confirmation approach compatible with the existing modal system
        window.UI.showModal(
            'Confirm Storage Path Change',
            'Changing storage paths will not move existing VM files. Make sure the new paths are accessible and have sufficient space. Continue?',
            async () => {
                await performStorageConfigSave(vmPath, isoPath, poolName);
            },
            false  // Not destructive (green button)
        );
        return;
    }
    
    // If no path changes, save directly
    await performStorageConfigSave(vmPath, isoPath, poolName);
}

/**
 * Perform the actual storage configuration save
 */
async function performStorageConfigSave(vmPath, isoPath, poolName) {
    const config = {
        vm_storage_path: vmPath,
        // Use proper path manipulation instead of string replacement
        iso_storage_path: isoPath || (function() {
            const pathParts = vmPath.split('/');
            pathParts.pop();
            return pathParts.join('/') + '/isos';
        })(),
        default_pool_name: poolName || 'default'
    };
    
    const result = await window.API.apiCall('/storage/config', 'POST', config);
    
    if (result && result.status === 'success') {
        window.UI.showStatus('Storage configuration saved successfully', 'success');
        currentStorageConfig = result.config || config;
        
        // Reload storage info to reflect new paths
        await loadStorageInfo();
    } else {
        const errorMsg = result?.errors?.join(', ') || result?.message || 'Failed to save configuration';
        window.UI.showStatus(errorMsg, 'error');
    }
}

/**
 * Refresh storage information
 */
async function refreshStorageInfo() {
    const refreshBtn = document.getElementById('storage-refresh-btn');
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = `
            <svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
        `;
    }
    
    await Promise.all([loadStorageConfig(), loadStorageInfo()]);
    
    if (refreshBtn) {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
        `;
    }
    
    window.UI.showStatus('Storage information refreshed', 'success');
}

/**
 * Initialize storage settings module
 */
function initStorageSettings() {
    // Load storage configuration when the settings page is shown
    const settingsPage = document.getElementById('page-settings');
    if (settingsPage) {
        // MutationObserver to detect when settings page becomes visible
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    if (settingsPage.classList.contains('active')) {
                        loadStorageConfig();
                        loadStorageInfo();
                    }
                }
            });
        });
        
        observer.observe(settingsPage, { attributes: true });
    }
}

// Export Storage Settings functions
window.StorageSettings = {
    loadStorageConfig,
    loadStorageInfo,
    saveStorageConfig,
    refreshStorageInfo,
    validateStoragePath,
    initStorageSettings
};

// Expose functions globally for onclick handlers
window.saveStorageConfig = saveStorageConfig;
window.refreshStorageInfo = refreshStorageInfo;

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', initStorageSettings);
