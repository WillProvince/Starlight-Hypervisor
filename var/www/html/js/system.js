/**
 * System Module
 * Server power management functionality
 */

async function rebootServer() {
    window.UI.showModal(
        'Confirm Server Reboot',
        '⚠️ WARNING: This will reboot the entire server and all VMs will be affected. Are you sure you want to reboot the server?',
        async () => {
            window.UI.showStatus('Sending reboot command to server...', 'info');
            
            const result = await window.API.apiCall('/system/reboot', 'POST');
            if (result && result.status === 'success') {
                window.UI.showStatus('Server reboot initiated. The system will restart shortly.', 'success');
            } else {
                window.UI.showStatus('Failed to reboot server. Check your permissions.', 'error');
            }
        },
        true
    );
}

async function shutdownServer() {
    window.UI.showModal(
        'Confirm Server Shutdown',
        '⚠️ WARNING: This will shutdown the entire server and all VMs will be stopped. Are you sure you want to shutdown the server?',
        async () => {
            window.UI.showStatus('Sending shutdown command to server...', 'info');
            
            const result = await window.API.apiCall('/system/shutdown', 'POST');
            if (result && result.status === 'success') {
                window.UI.showStatus('Server shutdown initiated. The system will power off shortly.', 'success');
            } else {
                window.UI.showStatus('Failed to shutdown server. Check your permissions.', 'error');
            }
        },
        true
    );
}

// Export System functions
window.System = {
    rebootServer,
    shutdownServer
};

// Expose functions globally for onclick handlers
window.rebootServer = rebootServer;
window.shutdownServer = shutdownServer;
