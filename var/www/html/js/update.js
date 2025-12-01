/**
 * Update Module
 * Handles system update checks, triggers, and status display
 * 
 * Note: Authorization headers are automatically added by window.API.apiCall()
 * which reads the token from window.AUTH.getAuthToken(). No additional header
 * handling is needed in this module.
 */

// Constants for timeout delays (in milliseconds)
const UPDATE_STATUS_LOAD_DELAY = 1000;
const UPDATE_SUCCESS_DISPLAY_DELAY = 2000;
const PAGE_RELOAD_DELAY = 3000;

/**
 * Extract a display version string from version info object.
 * Prefers 'version' field, falls back to 'commit', then 'Unknown'.
 * @param {Object} versionInfo - Version info object with version/commit fields
 * @returns {string} Display version string
 */
function getDisplayVersion(versionInfo) {
    if (!versionInfo) {
        return 'Unknown';
    }
    // Prefer explicit version field, fall back to commit hash
    return versionInfo.version || versionInfo.commit || 'Unknown';
}

/**
 * Load and display the current update status
 */
async function loadUpdateStatus() {
    try {
        const result = await window.API.apiCall('/updates/status');
        
        if (result && result.status === 'success') {
            // Update current version display
            const versionEl = document.getElementById('current-version');
            if (versionEl && result.current_version) {
                versionEl.textContent = getDisplayVersion(result.current_version);
            }
            
            // Update last checked display
            const lastCheckedEl = document.getElementById('last-checked');
            if (lastCheckedEl && result.config) {
                const lastCheck = result.config.last_check;
                if (lastCheck) {
                    const date = new Date(lastCheck);
                    lastCheckedEl.textContent = date.toLocaleString();
                } else {
                    lastCheckedEl.textContent = 'Never';
                }
            }
            
            // Update auto-update toggle
            const autoUpdateToggle = document.getElementById('auto-update-toggle');
            if (autoUpdateToggle && result.config) {
                autoUpdateToggle.checked = result.config.auto_update_enabled || false;
            }
        }
    } catch (error) {
        console.error('Error loading update status:', error);
    }
}

/**
 * Check for available updates
 */
async function checkForUpdates() {
    const statusTextEl = document.getElementById('update-status-text');
    const updateAvailableSection = document.getElementById('update-available-section');
    const updateInfoText = document.getElementById('update-info-text');
    
    try {
        // Show checking status
        if (statusTextEl) {
            statusTextEl.textContent = 'Checking for updates...';
        }
        
        const result = await window.API.apiCall('/updates/check');
        
        if (result && result.status === 'success') {
            const updateInfo = result.update_info;
            
            // Update last checked time
            const lastCheckedEl = document.getElementById('last-checked');
            if (lastCheckedEl) {
                lastCheckedEl.textContent = new Date().toLocaleString();
            }
            
            if (updateInfo && updateInfo.available) {
                // Updates are available
                if (statusTextEl) {
                    statusTextEl.textContent = `${updateInfo.commit_count} update(s) available`;
                }
                
                if (updateAvailableSection) {
                    updateAvailableSection.classList.remove('hidden');
                }
                
                if (updateInfoText) {
                    let infoMessage = `${updateInfo.commit_count} new commit(s) available`;
                    if (updateInfo.latest_message) {
                        infoMessage += `: ${updateInfo.latest_message}`;
                    }
                    // Show version mismatch info if available
                    if (updateInfo.version_mismatch && updateInfo.remote_version) {
                        const remoteVer = getDisplayVersion(updateInfo.remote_version);
                        if (remoteVer !== 'Unknown') {
                            infoMessage += ` (Remote version: ${remoteVer})`;
                        }
                    }
                    updateInfoText.textContent = infoMessage;
                }
                
                window.UI.showStatus('Updates available!', 'info');
            } else {
                // No updates available
                if (statusTextEl) {
                    statusTextEl.textContent = 'System is up to date';
                }
                
                if (updateAvailableSection) {
                    updateAvailableSection.classList.add('hidden');
                }
                
                window.UI.showStatus('System is up to date', 'success');
            }
        } else {
            // Error checking for updates
            if (statusTextEl) {
                statusTextEl.textContent = 'Failed to check for updates';
            }
            
            window.UI.showStatus(result?.message || 'Failed to check for updates', 'error');
        }
    } catch (error) {
        console.error('Error checking for updates:', error);
        
        if (statusTextEl) {
            statusTextEl.textContent = 'Error checking for updates';
        }
        
        window.UI.showStatus('Error checking for updates', 'error');
    }
}

/**
 * Trigger the system update process
 */
async function triggerUpdate() {
    const updateProgressSection = document.getElementById('update-progress-section');
    const updateAvailableSection = document.getElementById('update-available-section');
    const updateNowBtn = document.getElementById('update-now-btn');
    const progressText = document.getElementById('update-progress-text');
    
    try {
        // Show progress UI
        if (updateAvailableSection) {
            updateAvailableSection.classList.add('hidden');
        }
        
        if (updateProgressSection) {
            updateProgressSection.classList.remove('hidden');
        }
        
        if (updateNowBtn) {
            updateNowBtn.disabled = true;
        }
        
        if (progressText) {
            progressText.textContent = 'Installing update...';
        }
        
        const result = await window.API.apiCall('/updates/trigger', 'POST');
        
        if (result && result.status === 'success') {
            if (progressText) {
                progressText.textContent = 'Update completed successfully!';
            }
            
            window.UI.showStatus('Update completed successfully!', 'success');
            
            // If restart is required, inform the user
            if (result.restart_required) {
                if (progressText) {
                    progressText.textContent = 'Update completed. Restarting service...';
                }
                
                // Wait a moment then reload the page
                setTimeout(() => {
                    window.UI.showStatus('Service is restarting. Page will reload...', 'info');
                    setTimeout(() => {
                        window.location.reload();
                    }, PAGE_RELOAD_DELAY);
                }, UPDATE_SUCCESS_DISPLAY_DELAY);
            } else {
                // Hide progress after a moment
                setTimeout(() => {
                    if (updateProgressSection) {
                        updateProgressSection.classList.add('hidden');
                    }
                    // Refresh status
                    loadUpdateStatus();
                }, UPDATE_SUCCESS_DISPLAY_DELAY);
            }
        } else {
            // Error during update
            if (progressText) {
                progressText.textContent = 'Update failed';
            }
            
            if (updateProgressSection) {
                updateProgressSection.classList.add('hidden');
            }
            
            if (updateAvailableSection) {
                updateAvailableSection.classList.remove('hidden');
            }
            
            if (updateNowBtn) {
                updateNowBtn.disabled = false;
            }
            
            const errorMsg = result?.message || 'Update failed';
            window.UI.showStatus(errorMsg, 'error');
            
            // Show rollback info if available
            if (result?.rollback_attempted) {
                const rollbackStatus = result.rollback_success ? 'successful' : 'failed';
                window.UI.showStatus(`Rollback ${rollbackStatus}`, result.rollback_success ? 'info' : 'error');
            }
        }
    } catch (error) {
        console.error('Error triggering update:', error);
        
        if (progressText) {
            progressText.textContent = 'Error during update';
        }
        
        if (updateProgressSection) {
            updateProgressSection.classList.add('hidden');
        }
        
        if (updateAvailableSection) {
            updateAvailableSection.classList.remove('hidden');
        }
        
        if (updateNowBtn) {
            updateNowBtn.disabled = false;
        }
        
        window.UI.showStatus('Error triggering update', 'error');
    }
}

/**
 * Toggle auto-update setting
 */
async function toggleAutoUpdate() {
    const toggle = document.getElementById('auto-update-toggle');
    if (!toggle) return;
    
    const enabled = toggle.checked;
    
    try {
        const result = await window.API.apiCall('/updates/config', 'POST', {
            auto_update_enabled: enabled
        });
        
        if (result && result.status === 'success') {
            window.UI.showStatus(`Auto-update ${enabled ? 'enabled' : 'disabled'}`, 'success');
        } else {
            // Revert toggle on failure
            toggle.checked = !enabled;
            window.UI.showStatus('Failed to update auto-update setting', 'error');
        }
    } catch (error) {
        console.error('Error toggling auto-update:', error);
        toggle.checked = !enabled;
        window.UI.showStatus('Error updating auto-update setting', 'error');
    }
}

// Auto-invoke loadUpdateStatus after a short delay when the page loads
document.addEventListener('DOMContentLoaded', () => {
    // Delay loading update status to allow other initialization to complete
    setTimeout(() => {
        // Only load if user is authenticated
        if (window.AUTH.getAuthToken()) {
            loadUpdateStatus();
        }
    }, UPDATE_STATUS_LOAD_DELAY);
});

// Update Settings.loadUpdateStatus to use our implementation
if (window.Settings) {
    window.Settings.loadUpdateStatus = loadUpdateStatus;
}

// Export update functions globally for onclick handlers
window.checkForUpdates = checkForUpdates;
window.triggerUpdate = triggerUpdate;
window.toggleAutoUpdate = toggleAutoUpdate;
window.loadUpdateStatus = loadUpdateStatus;

// Export as module
window.Update = {
    loadUpdateStatus,
    checkForUpdates,
    triggerUpdate,
    toggleAutoUpdate
};
