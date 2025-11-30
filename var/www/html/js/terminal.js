/**
 * Terminal Module  
 * xterm.js terminal functionality for LXC containers
 */

let termInstance = null;
let termSocket = null;
let termFitAddon = null;
let currentTerminalVm = null;

// Support for multiple terminal instances (for console manager)
const termInstances = new Map();
const termSockets = new Map();
const termFitAddons = new Map();
const termSessions = new Map();

// Constants
const CONNECTION_ERROR_DELAY = 2000; // Delay before closing terminal after connection error
const CONNECTION_CLOSE_DELAY = 2000; // Delay before closing terminal after connection closes

function setTerminalStatus(text, type = 'info') {
    const statusEl = document.getElementById('terminal-status');
    if (!statusEl) return;
    
    statusEl.textContent = text;
    statusEl.className = 'text-xs font-semibold px-2 py-1 rounded-full';
    
    switch (type) {
        case 'connecting':
            statusEl.classList.add('vnc-status-connecting');
            break;
        case 'connected':
            statusEl.classList.add('vnc-status-connected');
            break;
        case 'error':
        case 'disconnected':
            statusEl.classList.add('vnc-status-error');
            break;
        default:
            statusEl.classList.add('vnc-status-info');
            break;
    }
}

async function launchTerminal(containerName) {
    console.log('Terminal: launchTerminal called for', containerName);
    
    // Check if Terminal library is loaded
    if (typeof Terminal === 'undefined') {
        console.error('Terminal: xterm.js Terminal class not found');
        window.UI.showStatus('Error: The terminal library (xterm.js) is not loaded.', 'error');
        return;
    }
    console.log('Terminal: xterm.js Terminal class is available');
    
    // Check if FitAddon is available
    if (typeof FitAddon === 'undefined') {
        console.error('Terminal: FitAddon not found');
        window.UI.showStatus('Error: The terminal FitAddon is not loaded.', 'error');
        return;
    }
    console.log('Terminal: FitAddon is available');
    
    currentTerminalVm = containerName;
    
    const terminalEl = document.getElementById('terminal-viewer-inline');
    const terminalVmNameEl = document.getElementById('terminal-vm-name');
    const terminalTitleEl = document.getElementById('terminal-title');
    
    if (terminalEl) {
        terminalEl.classList.remove('hidden');
        terminalEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    
    if (terminalTitleEl) {
        terminalTitleEl.textContent = `Terminal Console: ${containerName}`;
    }
    
    if (terminalVmNameEl) {
        terminalVmNameEl.textContent = `Connected to: ${containerName}`;
    }
    
    setTerminalStatus('Connecting...', 'connecting');
    
    // Close existing connections
    if (termSocket) {
        termSocket.close();
        termSocket = null;
    }
    
    if (termInstance) {
        termInstance.dispose();
        termInstance = null;
    }
    
    const host = window.location.hostname || 'localhost';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const path = `/lxc-console/${containerName}`;
    const authToken = window.AUTH.getAuthToken();
    const tokenParam = authToken ? `?token=${encodeURIComponent(authToken)}` : '';
    const url = `${protocol}//${host}${path}${tokenParam}`;
    
    try {
        const termContainer = document.getElementById('terminal-container');
        if (!termContainer) {
            throw new Error('Terminal container not found');
        }
        
        // Clear the terminal container
        termContainer.innerHTML = '';
        
        console.log('Terminal: Creating xterm.js terminal');
        
        // Create terminal with rows and cols specified
        termInstance = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#000000',
                foreground: '#ffffff'
            },
            rows: 30,
            cols: 100
        });
        
        // Create fit addon
        termFitAddon = new FitAddon.FitAddon();
        termInstance.loadAddon(termFitAddon);
        
        // Open terminal in container
        termInstance.open(termContainer);
        
        // Fit terminal to container
        setTimeout(() => {
            if (termFitAddon) {
                termFitAddon.fit();
            }
        }, 100);
        
        // Handle window resize
        window.addEventListener('resize', () => {
            if (termFitAddon && termInstance) {
                termFitAddon.fit();
            }
        });
        
        // Connect to WebSocket
        console.log('Terminal: Connecting to', url);
        termSocket = new WebSocket(url);
        
        termSocket.onopen = () => {
            console.log('Terminal: WebSocket connected');
            setTerminalStatus('Connected', 'connected');
            if (termInstance) {
                termInstance.writeln('Connected to ' + containerName);
                termInstance.writeln('');
            }
        };
        
        termSocket.onmessage = (event) => {
            if (termInstance) {
                termInstance.write(event.data);
            }
        };
        
        termSocket.onerror = (error) => {
            console.error('Terminal: WebSocket error:', error);
            setTerminalStatus('Connection Error', 'error');
            if (termInstance) {
                termInstance.writeln('\r\n\x1b[1;31mConnection error\x1b[0m\r\n');
            }
            // Close the terminal viewer after showing error
            setTimeout(() => closeTerminal(true), 2000);
        };
        
        termSocket.onclose = () => {
            console.log('Terminal: WebSocket closed');
            setTerminalStatus('Disconnected', 'disconnected');
            if (termInstance) {
                termInstance.writeln('\r\n\x1b[1;33mConnection closed\x1b[0m\r\n');
            }
            // Automatically close the terminal viewer when connection is lost
            setTimeout(() => closeTerminal(true), 2000);
        };
        
        // Send terminal input to WebSocket
        termInstance.onData((data) => {
            if (termSocket && termSocket.readyState === WebSocket.OPEN) {
                termSocket.send(data);
            }
        });
        
    } catch (error) {
        console.error('Terminal initialization error:', error);
        setTerminalStatus('Error', 'error');
        window.UI.showStatus(`Terminal failed: ${error.message}`, 'error');
    }
}

function closeTerminal(skipDisconnect = false) {
    if (termSocket && !skipDisconnect) {
        termSocket.close();
    }
    
    if (termInstance) {
        termInstance.dispose();
    }
    
    termSocket = null;
    termInstance = null;
    termFitAddon = null;
    currentTerminalVm = null;
    
    const terminalEl = document.getElementById('terminal-viewer-inline');
    if (terminalEl) {
        terminalEl.classList.add('hidden');
    }
}

async function terminalControlVm(action) {
    if (!currentTerminalVm) return;
    
    const endpoint = `/vm/${currentTerminalVm}/${action}`;
    const result = await window.API.apiCall(endpoint, 'POST');
    
    if (result && result.status === 'success') {
        window.UI.showStatus(`Container ${action} command sent`, 'success');
        if (action === 'stop' || action === 'destroy') {
            setTimeout(() => closeTerminal(true), 2000);
        }
    }
}

/**
 * Launch Terminal in a specific container (for console manager)
 */
async function launchTerminalInContainer(sessionId, containerName, terminalContainerId, statusElementId) {
    console.log(`Terminal: Launching terminal for ${containerName} in container ${terminalContainerId}`);
    
    // Check if Terminal library is loaded
    if (typeof Terminal === 'undefined') {
        throw new Error('xterm.js Terminal class not found');
    }
    
    if (typeof FitAddon === 'undefined') {
        throw new Error('FitAddon not found');
    }
    
    const termContainer = document.getElementById(terminalContainerId);
    const statusEl = document.getElementById(statusElementId);
    
    if (!termContainer) {
        throw new Error('Terminal container not found');
    }
    
    // Store session info
    termSessions.set(sessionId, {
        containerName: containerName,
        terminalContainerId: terminalContainerId,
        statusElementId: statusElementId
    });
    
    // Update status
    if (statusEl) {
        statusEl.textContent = 'Connecting...';
        statusEl.className = 'console-status console-status-connecting';
    }
    
    try {
        // Clear the terminal container
        termContainer.innerHTML = '';
        
        console.log('Terminal: Creating xterm.js terminal for session', sessionId);
        
        // Create terminal with rows and cols specified
        const terminal = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#000000',
                foreground: '#ffffff'
            },
            rows: 30,
            cols: 100
        });
        
        // Create fit addon
        const fitAddon = new FitAddon.FitAddon();
        terminal.loadAddon(fitAddon);
        
        // Open terminal in container
        terminal.open(termContainer);
        
        // Fit terminal to container
        setTimeout(() => {
            if (fitAddon) {
                fitAddon.fit();
            }
        }, 100);
        
        // Handle window resize
        const resizeHandler = () => {
            if (fitAddon && terminal) {
                fitAddon.fit();
            }
        };
        window.addEventListener('resize', resizeHandler);
        
        // Store resize handler for cleanup
        termSessions.get(sessionId).resizeHandler = resizeHandler;
        
        // Connect to WebSocket
        const host = window.location.hostname || 'localhost';
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const path = `/lxc-console/${containerName}`;
        const authToken = window.AUTH.getAuthToken();
        const tokenParam = authToken ? `?token=${encodeURIComponent(authToken)}` : '';
        const url = `${protocol}//${host}${path}${tokenParam}`;
        
        console.log('Terminal: Connecting to', url);
        const socket = new WebSocket(url);
        
        socket.onopen = () => {
            console.log('Terminal: WebSocket connected for session', sessionId);
            if (statusEl) {
                statusEl.textContent = 'Connected';
                statusEl.className = 'console-status console-status-connected';
            }
            if (terminal) {
                terminal.writeln('Connected to ' + containerName);
                terminal.writeln('');
            }
        };
        
        socket.onmessage = (event) => {
            if (terminal) {
                terminal.write(event.data);
            }
        };
        
        socket.onerror = (error) => {
            console.error('Terminal: WebSocket error for session', sessionId, error);
            if (statusEl) {
                statusEl.textContent = 'Connection Error';
                statusEl.className = 'console-status console-status-error';
            }
            if (terminal) {
                terminal.writeln('\r\n\x1b[1;31mConnection error\x1b[0m\r\n');
            }
            // Close the tab after showing error
            setTimeout(() => {
                if (window.ConsoleManager) {
                    window.ConsoleManager.closeTab(sessionId);
                }
            }, CONNECTION_ERROR_DELAY);
        };
        
        socket.onclose = () => {
            console.log('Terminal: WebSocket closed for session', sessionId);
            if (statusEl) {
                statusEl.textContent = 'Disconnected';
                statusEl.className = 'console-status console-status-error';
            }
            if (terminal) {
                terminal.writeln('\r\n\x1b[1;33mConnection closed\x1b[0m\r\n');
            }
            // Automatically close the tab when connection is lost
            setTimeout(() => {
                if (window.ConsoleManager) {
                    window.ConsoleManager.closeTab(sessionId);
                }
            }, CONNECTION_CLOSE_DELAY);
        };
        
        // Send terminal input to WebSocket
        terminal.onData((data) => {
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(data);
            }
        });
        
        // Store instances
        termInstances.set(sessionId, terminal);
        termSockets.set(sessionId, socket);
        termFitAddons.set(sessionId, fitAddon);
        
    } catch (error) {
        console.error('Terminal initialization error:', error);
        if (statusEl) {
            statusEl.textContent = 'Error';
            statusEl.className = 'console-status console-status-error';
        }
        throw error;
    }
}

/**
 * Get terminal instance for a session
 */
function getTermInstance(sessionId) {
    return termInstances.get(sessionId);
}

/**
 * Cleanup a terminal session
 */
function cleanupSession(sessionId) {
    const socket = termSockets.get(sessionId);
    if (socket) {
        socket.close();
        termSockets.delete(sessionId);
    }
    
    const terminal = termInstances.get(sessionId);
    if (terminal) {
        terminal.dispose();
        termInstances.delete(sessionId);
    }
    
    termFitAddons.delete(sessionId);
    
    const session = termSessions.get(sessionId);
    if (session && session.resizeHandler) {
        window.removeEventListener('resize', session.resizeHandler);
    }
    
    termSessions.delete(sessionId);
}

// Export Terminal functions (use TerminalManager to avoid conflict with xterm.js Terminal class)
window.TerminalManager = {
    launchTerminal,
    closeTerminal,
    terminalControlVm,
    // New functions for console manager
    launchTerminalInContainer,
    getTermInstance,
    cleanupSession
};

// Expose functions globally for onclick handlers
window.launchTerminal = launchTerminal;
window.closeTerminal = closeTerminal;
window.terminalControlVm = terminalControlVm;
