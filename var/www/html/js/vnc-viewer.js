/**
 * VNC Viewer Module
 * VNC connection, RFB management, clipboard handling
 */

const vncInlineEl = document.getElementById('vnc-viewer-inline');
const vncStatusEl = document.getElementById('vnc-status');
const vncCanvasContainerEl = document.getElementById('vnc-canvas-container');
const vncVmNameEl = document.getElementById('vnc-vm-name');

let rfbClient = null;
let currentVncVm = null;

// Support for multiple VNC instances (for console manager)
const rfbClients = new Map();
const vncSessions = new Map();

// This module contains VNC-related functions
// Full implementation extracted from index.html lines 1890-2530

function setVncStatus(text, type = 'info') {
    vncStatusEl.textContent = text;
    vncStatusEl.className = 'text-xs font-semibold px-2 py-1 rounded-full';
    
    switch (type) {
        case 'connecting':
            vncStatusEl.classList.add('vnc-status-connecting');
            break;
        case 'connected':
            vncStatusEl.classList.add('vnc-status-connected');
            break;
        case 'error':
        case 'disconnected':
            vncStatusEl.classList.add('vnc-status-error');
            break;
        case 'info':
        default:
            vncStatusEl.classList.add('vnc-status-info');
            break;
    }
}

// Constants for VNC loading
const VNC_LOAD_MAX_ATTEMPTS = 50;
const VNC_LOAD_RETRY_DELAY_MS = 100;

async function checkNoVNCLoaded() {
    // Wait for RFB to be loaded
    let attempts = 0;
    while (!window.RFB && attempts < VNC_LOAD_MAX_ATTEMPTS) {
        await new Promise(resolve => setTimeout(resolve, VNC_LOAD_RETRY_DELAY_MS));
        attempts++;
    }
    if (!window.RFB) {
        console.error('noVNC RFB library failed to load');
    }
}

// Request clipboard permissions proactively
async function requestClipboardPermissions() {
    try {
        // Check if Clipboard API is available
        if (!navigator.clipboard) {
            console.warn('VNC: Clipboard API not available in this browser');
            return false;
        }

        // Try to request permission by attempting to read
        try {
            await navigator.clipboard.readText();
            console.log('VNC: Clipboard permissions granted');
            return true;
        } catch (err) {
            // Permission denied or not yet granted
            console.warn('VNC: Clipboard permission not granted yet:', err.message);
            
            // Show one-time notification about clipboard permissions
            const notificationKey = 'clipboard_notification_shown';
            if (!localStorage.getItem(notificationKey)) {
                window.UI.showStatus('💡 Tip: Allow clipboard access when prompted to enable copy/paste between your computer and VNC', 'info');
                localStorage.setItem(notificationKey, 'true');
            }
            return false;
        }
    } catch (err) {
        console.error('VNC: Error checking clipboard permissions:', err);
        return false;
    }
}

async function launchVnc(vmName, vncPort) {
    if (!vncPort) {
        window.UI.showStatus('VNC port not available for this VM', 'error');
        return;
    }
    
    // Verify container exists
    if (!vncCanvasContainerEl) {
        console.error('VNC canvas container element not found');
        window.UI.showStatus('VNC viewer initialization error', 'error');
        return;
    }

    currentVncVm = vmName;
    if (vncVmNameEl) {
        vncVmNameEl.textContent = vmName;
    }
    vncInlineEl.classList.remove('hidden');
    vncInlineEl.scrollIntoView({ behavior: 'smooth' });
    
    if (rfbClient) {
        try {
            rfbClient.disconnect();
        } catch (e) {
            console.warn('Error disconnecting previous VNC session:', e);
        }
        rfbClient = null;
    }

    setVncStatus('Connecting...', 'connecting');

    try {
        // Request clipboard permissions before connecting
        await requestClipboardPermissions();
        
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const authToken = window.AUTH.getAuthToken();
        const wsUrl = `${protocol}${window.location.host}/vnc-proxy/${vncPort}${authToken ? '?token=' + encodeURIComponent(authToken) : ''}`;
        
        console.log('VNC: Connecting to', wsUrl.replace(/token=[^&]+/, 'token=***'));
        
        // Clear the container before creating new RFB client
        vncCanvasContainerEl.innerHTML = '';
        
        rfbClient = new window.RFB(vncCanvasContainerEl, wsUrl, {
            credentials: { password: '' },
            shared: true
        });

        // Set display options - must be done after creation
        rfbClient.scaleViewport = false;  // Disable scaling for now to debug
        rfbClient.resizeSession = false;  // Don't resize remote session
        rfbClient.viewOnly = false;       // Allow mouse/keyboard input
        rfbClient.focusOnClick = true;    // Focus on click
        rfbClient.clipViewport = false;   // Show full desktop
        rfbClient.dragViewport = true;    // Enable drag to pan
        
        console.log('VNC: RFB client created and configured');
        console.log('VNC: scaleViewport:', rfbClient.scaleViewport);
        console.log('VNC: Waiting for connection...');

        rfbClient.addEventListener('connect', () => {
            console.log('VNC: Connected successfully');
            const canvas = vncCanvasContainerEl.querySelector('canvas');
            console.log('VNC: Canvas element:', canvas);
            console.log('VNC: Canvas dimensions:', canvas?.width, canvas?.height);
            console.log('VNC: Canvas style:', canvas?.style?.cssText);
            setVncStatus('Connected', 'connected');
            window.UI.showStatus(`VNC connected to ${vmName}`, 'success');
        });

        rfbClient.addEventListener('disconnect', (e) => {
            console.log('VNC: Disconnected', e.detail);
            const statusMsg = e.detail.clean ? 'Clean Disconnect' : 'Disconnected';
            setVncStatus(statusMsg, 'disconnected');
            
            // Close VNC console on clean disconnect
            if (e.detail.clean) {
                closeVnc();
            } else {
                window.UI.showStatus(`VNC disconnected from ${vmName}`, 'info');
            }
        });

        rfbClient.addEventListener('securityfailure', (e) => {
            console.error('VNC: Security failure', e.detail);
            setVncStatus('Security Error', 'error');
            window.UI.showStatus(`VNC Security Failure: ${e.detail.status}`, 'error');
        });

        rfbClient.addEventListener('credentialsrequired', () => {
            console.log('VNC: Credentials required');
            // For now, just send empty credentials
            // In future, could show password prompt
            rfbClient.sendCredentials({ password: '' });
        });
        
        rfbClient.addEventListener('desktopname', (e) => {
            console.log('VNC: Desktop name received', e.detail.name);
        });
        
        rfbClient.addEventListener('capabilities', (e) => {
            console.log('VNC: Capabilities received', e.detail);
        });
        
        // Add clipboard support - VNC server to host
        rfbClient.addEventListener('clipboard', async (e) => {
            console.log('VNC: Clipboard data received from server:', e.detail.text);
            try {
                // Write clipboard data to system clipboard using Clipboard API
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(e.detail.text);
                    console.log('VNC: Clipboard data written to system clipboard');
                } else {
                    console.warn('VNC: Clipboard API not available');
                }
            } catch (err) {
                console.error('VNC: Failed to write clipboard data:', err);
            }
        });

    } catch (error) {
        console.error('VNC connection error:', error);
        setVncStatus('Error', 'error');
        window.UI.showStatus(`VNC connection failed: ${error.message}`, 'error');
    }
}

function closeVncViewer(skipDisconnect = false) {
    if (rfbClient && !skipDisconnect) {
        rfbClient.disconnect();
    }
    rfbClient = null;
    currentVncVm = null;
    vncInlineEl.classList.add('hidden');
}

async function vncControlVm(action) {
    if (!currentVncVm) return;
    
    const endpoint = `/vm/${currentVncVm}/${action}`;
    const result = await window.API.apiCall(endpoint, 'POST');
    
    if (result && result.status === 'success') {
        window.UI.showStatus(`VM ${action} command sent`, 'success');
        if (action === 'stop' || action === 'destroy') {
            setTimeout(() => closeVncViewer(true), 2000);
        }
    }
}

/**
 * Launch VNC in a specific container (for console manager)
 */
async function launchVncInContainer(sessionId, vmName, vncPort, canvasContainerId, statusElementId) {
    console.log(`VNC: Launching VNC for ${vmName} in container ${canvasContainerId}`);
    
    if (!vncPort) {
        throw new Error('VNC port not available for this VM');
    }
    
    const canvasContainer = document.getElementById(canvasContainerId);
    const statusEl = document.getElementById(statusElementId);
    
    if (!canvasContainer) {
        throw new Error('VNC canvas container element not found');
    }
    
    // Store session info
    vncSessions.set(sessionId, {
        vmName: vmName,
        port: vncPort,
        canvasContainerId: canvasContainerId,
        statusElementId: statusElementId
    });
    
    // Update status
    if (statusEl) {
        statusEl.textContent = 'Connecting...';
        statusEl.className = 'console-status console-status-connecting';
    }
    
    try {
        // Request clipboard permissions before connecting
        await requestClipboardPermissions();
        
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const authToken = window.AUTH.getAuthToken();
        const wsUrl = `${protocol}${window.location.host}/vnc-proxy/${vncPort}${authToken ? '?token=' + encodeURIComponent(authToken) : ''}`;
        
        console.log('VNC: Connecting to', wsUrl.replace(/token=[^&]+/, 'token=***'));
        
        // Clear the container before creating new RFB client
        canvasContainer.innerHTML = '';
        
        const client = new window.RFB(canvasContainer, wsUrl, {
            credentials: { password: '' },
            shared: true
        });
        
        // Set display options
        client.scaleViewport = false;
        client.resizeSession = false;
        client.viewOnly = false;
        client.focusOnClick = true;
        client.clipViewport = false;
        client.dragViewport = true;
        
        console.log('VNC: RFB client created for session', sessionId);
        
        client.addEventListener('connect', () => {
            console.log('VNC: Connected successfully for session', sessionId);
            if (statusEl) {
                statusEl.textContent = 'Connected';
                statusEl.className = 'console-status console-status-connected';
            }
            window.UI.showStatus(`VNC connected to ${vmName}`, 'success');
        });
        
        client.addEventListener('disconnect', (e) => {
            console.log('VNC: Disconnected for session', sessionId, e.detail);
            if (statusEl) {
                const statusMsg = e.detail.clean ? 'Clean Disconnect' : 'Disconnected';
                statusEl.textContent = statusMsg;
                statusEl.className = 'console-status console-status-error';
            }
            
            // Notify console manager if clean disconnect
            if (e.detail.clean && window.ConsoleManager) {
                window.ConsoleManager.closeTab(sessionId);
            }
        });
        
        client.addEventListener('securityfailure', (e) => {
            console.error('VNC: Security failure for session', sessionId, e.detail);
            if (statusEl) {
                statusEl.textContent = 'Security Error';
                statusEl.className = 'console-status console-status-error';
            }
            window.UI.showStatus(`VNC Security Failure: ${e.detail.status}`, 'error');
        });
        
        client.addEventListener('credentialsrequired', () => {
            console.log('VNC: Credentials required for session', sessionId);
            client.sendCredentials({ password: '' });
        });
        
        client.addEventListener('desktopname', (e) => {
            console.log('VNC: Desktop name received for session', sessionId, e.detail.name);
        });
        
        // Add clipboard support
        client.addEventListener('clipboard', async (e) => {
            console.log('VNC: Clipboard data received from server (session', sessionId, '):', e.detail.text);
            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(e.detail.text);
                    console.log('VNC: Clipboard data written to system clipboard');
                }
            } catch (err) {
                console.error('VNC: Failed to write clipboard data:', err);
            }
        });
        
        // Store the client
        rfbClients.set(sessionId, client);
        
    } catch (error) {
        console.error('VNC connection error:', error);
        if (statusEl) {
            statusEl.textContent = 'Error';
            statusEl.className = 'console-status console-status-error';
        }
        throw error;
    }
}

/**
 * Get RFB client for a session
 */
function getRfbClient(sessionId) {
    return rfbClients.get(sessionId);
}

/**
 * Cleanup a VNC session
 */
function cleanupSession(sessionId) {
    const client = rfbClients.get(sessionId);
    if (client) {
        try {
            client.disconnect();
        } catch (e) {
            console.warn('Error disconnecting VNC client:', e);
        }
        rfbClients.delete(sessionId);
    }
    vncSessions.delete(sessionId);
}

// Export VNC functions
window.VNCViewer = {
    launchVnc,
    closeVncViewer,
    vncControlVm,
    checkNoVNCLoaded,
    // New functions for console manager
    launchVncInContainer,
    getRfbClient,
    cleanupSession
};

// Expose functions globally for onclick handlers
window.launchVnc = launchVnc;
window.closeVncViewer = closeVncViewer;
window.vncControlVm = vncControlVm;
window.checkNoVNCLoaded = checkNoVNCLoaded;
