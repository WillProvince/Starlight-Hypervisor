/**
 * Host Terminal Module  
 * xterm.js terminal functionality for host system console (root only)
 */

let hostTermInstance = null;
let hostTermSocket = null;
let hostTermFitAddon = null;

function setHostTerminalStatus(text, type = 'info') {
    const statusEl = document.getElementById('host-terminal-status');
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

async function launchHostTerminal() {
    console.log('Host Terminal: launchHostTerminal called');
    
    // Check if Terminal library is loaded
    if (typeof Terminal === 'undefined') {
        console.error('Host Terminal: xterm.js Terminal class not found');
        window.UI.showStatus('Error: The terminal library (xterm.js) is not loaded.', 'error');
        return;
    }
    console.log('Host Terminal: xterm.js Terminal class is available');
    
    // Check if FitAddon is available
    if (typeof FitAddon === 'undefined') {
        console.error('Host Terminal: FitAddon not found');
        window.UI.showStatus('Error: The terminal FitAddon is not loaded.', 'error');
        return;
    }
    console.log('Host Terminal: FitAddon is available');
    
    const terminalViewerEl = document.getElementById('host-terminal-viewer');
    const openBtn = document.getElementById('open-host-console-btn');
    
    if (terminalViewerEl) {
        terminalViewerEl.classList.remove('hidden');
    }
    
    if (openBtn) {
        openBtn.style.display = 'none';
    }
    
    setHostTerminalStatus('Connecting...', 'connecting');
    
    // Close existing connections
    if (hostTermSocket) {
        hostTermSocket.close();
        hostTermSocket = null;
    }
    
    if (hostTermInstance) {
        hostTermInstance.dispose();
        hostTermInstance = null;
    }
    
    const host = window.location.hostname || 'localhost';
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const path = '/host-console';
    const authToken = window.AUTH.getAuthToken();
    const tokenParam = authToken ? `?token=${encodeURIComponent(authToken)}` : '';
    const url = `${protocol}//${host}${path}${tokenParam}`;
    
    try {
        const termContainer = document.getElementById('host-terminal-container');
        if (!termContainer) {
            throw new Error('Host terminal container not found');
        }
        
        // Clear the terminal container
        termContainer.innerHTML = '';
        
        console.log('Host Terminal: Creating xterm.js terminal');
        
        // Create terminal with rows and cols specified
        hostTermInstance = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: 'Menlo, Monaco, "Courier New", monospace',
            theme: {
                background: '#000000',
                foreground: '#ffffff'
            },
            rows: 24,
            cols: 100
        });
        
        // Create fit addon
        hostTermFitAddon = new FitAddon.FitAddon();
        hostTermInstance.loadAddon(hostTermFitAddon);
        
        // Open terminal in container
        hostTermInstance.open(termContainer);
        
        // Fit terminal to container
        setTimeout(() => {
            if (hostTermFitAddon) {
                hostTermFitAddon.fit();
            }
        }, 100);
        
        // Handle window resize
        const resizeHandler = () => {
            if (hostTermFitAddon && hostTermInstance) {
                hostTermFitAddon.fit();
            }
        };
        window.addEventListener('resize', resizeHandler);
        
        // Store resize handler for cleanup
        window._hostTermResizeHandler = resizeHandler;
        
        // Connect to WebSocket
        console.log('Host Terminal: Connecting to', url);
        hostTermSocket = new WebSocket(url);
        
        hostTermSocket.onopen = () => {
            console.log('Host Terminal: WebSocket connected');
            setHostTerminalStatus('Connected', 'connected');
            if (hostTermInstance) {
                hostTermInstance.writeln('Connected to host console');
                hostTermInstance.writeln('');
            }
        };
        
        hostTermSocket.onmessage = (event) => {
            if (hostTermInstance) {
                hostTermInstance.write(event.data);
            }
        };
        
        hostTermSocket.onerror = (error) => {
            console.error('Host Terminal: WebSocket error:', error);
            setHostTerminalStatus('Connection Error', 'error');
            if (hostTermInstance) {
                hostTermInstance.writeln('\r\n\x1b[1;31mConnection error\x1b[0m\r\n');
            }
            // Close the terminal viewer after showing error
            setTimeout(() => closeHostTerminal(true), 2000);
        };
        
        hostTermSocket.onclose = () => {
            console.log('Host Terminal: WebSocket closed');
            setHostTerminalStatus('Disconnected', 'disconnected');
            if (hostTermInstance) {
                hostTermInstance.writeln('\r\n\x1b[1;33mConnection closed\x1b[0m\r\n');
            }
            // Automatically close the terminal viewer when connection is lost
            setTimeout(() => closeHostTerminal(true), 2000);
        };
        
        // Send terminal input to WebSocket
        hostTermInstance.onData((data) => {
            if (hostTermSocket && hostTermSocket.readyState === WebSocket.OPEN) {
                hostTermSocket.send(data);
            }
        });
        
    } catch (error) {
        console.error('Host Terminal initialization error:', error);
        setHostTerminalStatus('Error', 'error');
        window.UI.showStatus(`Host terminal failed: ${error.message}`, 'error');
    }
}

function closeHostTerminal(skipDisconnect = false) {
    if (hostTermSocket && !skipDisconnect) {
        hostTermSocket.close();
    }
    
    if (hostTermInstance) {
        hostTermInstance.dispose();
    }
    
    // Remove resize handler
    if (window._hostTermResizeHandler) {
        window.removeEventListener('resize', window._hostTermResizeHandler);
        delete window._hostTermResizeHandler;
    }
    
    hostTermSocket = null;
    hostTermInstance = null;
    hostTermFitAddon = null;
    
    const terminalViewerEl = document.getElementById('host-terminal-viewer');
    const openBtn = document.getElementById('open-host-console-btn');
    
    if (terminalViewerEl) {
        terminalViewerEl.classList.add('hidden');
    }
    
    if (openBtn) {
        openBtn.style.display = 'flex';
    }
}

// Function to show/hide host console section based on user
function updateHostConsoleSectionVisibility() {
    const hostConsoleSection = document.getElementById('host-console-section');
    const currentUser = window.AUTH.getCurrentUser();
    const isRoot = currentUser === 'root';
    
    if (hostConsoleSection) {
        if (isRoot) {
            hostConsoleSection.classList.remove('hidden');
        } else {
            hostConsoleSection.classList.add('hidden');
        }
    }
}

// Export Host Terminal functions
window.HostTerminal = {
    launchHostTerminal,
    closeHostTerminal,
    updateHostConsoleSectionVisibility
};

// Expose functions globally for onclick handlers
window.launchHostTerminal = launchHostTerminal;
window.closeHostTerminal = closeHostTerminal;
window.updateHostConsoleSectionVisibility = updateHostConsoleSectionVisibility;
