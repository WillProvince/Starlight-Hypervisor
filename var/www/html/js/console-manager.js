/**
 * Console Manager Module
 * Manages unified tabbed console interface for both VNC and Terminal sessions
 */

// Active console sessions
let consoleSessions = new Map();
let activeSessionId = null;

// Constants
const CONTROL_ACTION_DELAY = 2000; // Delay before closing console after stop/destroy action

/**
 * Initialize the console manager
 */
function initConsoleManager() {
    console.log('Console Manager: Initializing...');
    
    // Hide old console viewers if they exist
    const oldVnc = document.getElementById('vnc-viewer-inline');
    const oldTerminal = document.getElementById('terminal-viewer-inline');
    if (oldVnc) oldVnc.style.display = 'none';
    if (oldTerminal) oldTerminal.style.display = 'none';
}

/**
 * Open a console session (VNC or Terminal)
 * @param {string} name - VM/Container name
 * @param {string} type - 'vnc' or 'terminal'
 * @param {number} port - VNC port (only for VNC type)
 * @param {string} icon - Optional icon URL
 */
function openConsole(name, type, port = null, icon = null) {
    console.log(`Console Manager: Opening ${type} console for ${name}`);
    
    // Check if session already exists
    const existingSessionId = findSessionByName(name);
    if (existingSessionId) {
        console.log(`Console Manager: Session already exists, switching to it`);
        switchToTab(existingSessionId);
        return;
    }
    
    // Generate unique session ID
    const sessionId = `console-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;
    
    // Create session object
    const session = {
        id: sessionId,
        name: name,
        type: type,
        port: port,
        icon: icon,
        instance: null // Will hold VNC rfbClient or terminal instance
    };
    
    // Add to sessions map
    consoleSessions.set(sessionId, session);
    
    // Show console viewer if hidden
    const consoleViewer = document.getElementById('console-viewer');
    if (consoleViewer) {
        consoleViewer.classList.remove('hidden');
        consoleViewer.scrollIntoView({ behavior: 'smooth' });
    }
    
    // Create tab
    createTab(sessionId, name, type, icon);
    
    // Switch to new tab
    switchToTab(sessionId);
    
    // Initialize the appropriate console type
    if (type === 'vnc') {
        initVncSession(sessionId, name, port);
    } else if (type === 'terminal') {
        initTerminalSession(sessionId, name);
    }
}

/**
 * Find session by VM/Container name
 */
function findSessionByName(name) {
    for (const [sessionId, session] of consoleSessions.entries()) {
        if (session.name === name) {
            return sessionId;
        }
    }
    return null;
}

/**
 * Create a tab for a console session
 */
function createTab(sessionId, name, type = 'vnc', icon = null) {
    const tabBar = document.getElementById('console-tabs');
    if (!tabBar) {
        console.error('Console Manager: Tab bar not found');
        return;
    }
    
    // Determine if this is an LXC container (terminal) or VM (vnc)
    const isLxc = type === 'terminal';
    const fallbackIconSvg = isLxc ? 
        '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M20 7h-4V4c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2v3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zM10 4h4v3h-4V4zm10 16H4V9h16v11z"/><path d="M9 12h6v2H9zm0 4h6v2H9z"/></svg>' :
        '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M20 18c1.1 0 1.99-.9 1.99-2L22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zM4 6h16v10H4V6z"/></svg>';
    
    const iconHtml = icon ? 
        `<img src="${icon}" alt="${name}" class="w-4 h-4 rounded object-cover" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';" />
         <span style="display: none;">${fallbackIconSvg}</span>` :
        fallbackIconSvg;
    
    const tab = document.createElement('button');
    tab.id = `tab-${sessionId}`;
    tab.className = 'console-tab';
    tab.setAttribute('data-session-id', sessionId);
    tab.innerHTML = `
        <span class="console-tab-label flex items-center gap-2">
            ${iconHtml}
            <span>Console: ${name}</span>
        </span>
        <button class="console-tab-close" onclick="event.stopPropagation(); window.ConsoleManager.closeTab('${sessionId}')">×</button>
    `;
    tab.onclick = () => switchToTab(sessionId);
    
    tabBar.appendChild(tab);
}

/**
 * Switch to a specific tab
 */
function switchToTab(sessionId) {
    console.log(`Console Manager: Switching to tab ${sessionId}`);
    
    // Update active session
    activeSessionId = sessionId;
    
    // Update tab styles
    const tabs = document.querySelectorAll('.console-tab');
    tabs.forEach(tab => {
        if (tab.getAttribute('data-session-id') === sessionId) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });
    
    // Show/hide console containers
    const containers = document.querySelectorAll('.console-content');
    containers.forEach(container => {
        if (container.getAttribute('data-session-id') === sessionId) {
            container.classList.remove('hidden');
        } else {
            container.classList.add('hidden');
        }
    });
}

/**
 * Close a tab and its console session
 */
function closeTab(sessionId) {
    console.log(`Console Manager: Closing tab ${sessionId}`);
    
    const session = consoleSessions.get(sessionId);
    if (!session) {
        console.warn(`Console Manager: Session ${sessionId} not found`);
        return;
    }
    
    // Clean up based on type
    if (session.type === 'vnc') {
        cleanupVncSession(sessionId);
    } else if (session.type === 'terminal') {
        cleanupTerminalSession(sessionId);
    }
    
    // Remove tab from DOM
    const tab = document.getElementById(`tab-${sessionId}`);
    if (tab) {
        tab.remove();
    }
    
    // Remove container from DOM
    const container = document.querySelector(`.console-content[data-session-id="${sessionId}"]`);
    if (container) {
        container.remove();
    }
    
    // Remove from sessions map
    consoleSessions.delete(sessionId);
    
    // If this was the active session, switch to another or hide console viewer
    if (activeSessionId === sessionId) {
        if (consoleSessions.size > 0) {
            // Switch to the first remaining session
            const firstSessionId = consoleSessions.keys().next().value;
            switchToTab(firstSessionId);
        } else {
            // No more sessions, hide console viewer
            const consoleViewer = document.getElementById('console-viewer');
            if (consoleViewer) {
                consoleViewer.classList.add('hidden');
            }
            activeSessionId = null;
        }
    }
}

/**
 * Initialize VNC session
 */
async function initVncSession(sessionId, name, port) {
    console.log(`Console Manager: Initializing VNC session ${sessionId}`);
    
    const session = consoleSessions.get(sessionId);
    if (!session) return;
    
    // Create container for this VNC session
    const consoleArea = document.getElementById('console-area');
    if (!consoleArea) {
        console.error('Console Manager: Console area not found');
        return;
    }
    
    const container = document.createElement('div');
    container.className = 'console-content vnc-content';
    container.setAttribute('data-session-id', sessionId);
    container.innerHTML = `
        <div class="console-header">
            <div class="flex items-center">
                <h3 class="console-title">VNC Console: ${name}</h3>
                <span id="status-${sessionId}" class="console-status console-status-info">Connecting...</span>
            </div>
        </div>
        <div id="canvas-${sessionId}" class="console-canvas-container">
            <!-- RFB will create and insert canvas here -->
        </div>
        <div class="console-controls">
            <div class="console-controls-buttons">
                <button onclick="window.ConsoleManager.vncControl('${sessionId}', 'start')" class="console-btn console-btn-green">▶ Start</button>
                <button onclick="window.ConsoleManager.vncControl('${sessionId}', 'restart')" class="console-btn console-btn-yellow">🔄 Restart</button>
                <button onclick="window.ConsoleManager.vncControl('${sessionId}', 'stop')" class="console-btn console-btn-red">⏹ Stop</button>
                <button onclick="window.ConsoleManager.vncControl('${sessionId}', 'destroy')" class="console-btn console-btn-dark-red">⚠️ Force Stop</button>
                <button onclick="window.ConsoleManager.handleVncPaste('${sessionId}')" class="console-btn console-btn-indigo" title="Paste text into VNC">📋 Paste</button>
            </div>
        </div>
    `;
    
    consoleArea.appendChild(container);
    
    // Now initialize VNC using the VNCViewer module
    try {
        await window.VNCViewer.launchVncInContainer(sessionId, name, port, `canvas-${sessionId}`, `status-${sessionId}`);
        session.instance = window.VNCViewer.getRfbClient(sessionId);
    } catch (error) {
        console.error(`Console Manager: Failed to initialize VNC session`, error);
        window.UI.showStatus(`VNC connection failed: ${error.message}`, 'error');
    }
}

/**
 * Initialize Terminal session
 */
async function initTerminalSession(sessionId, name) {
    console.log(`Console Manager: Initializing Terminal session ${sessionId}`);
    
    const session = consoleSessions.get(sessionId);
    if (!session) return;
    
    // Create container for this Terminal session
    const consoleArea = document.getElementById('console-area');
    if (!consoleArea) {
        console.error('Console Manager: Console area not found');
        return;
    }
    
    const container = document.createElement('div');
    container.className = 'console-content terminal-content';
    container.setAttribute('data-session-id', sessionId);
    container.innerHTML = `
        <div class="console-header">
            <div class="flex items-center">
                <h3 class="console-title">Terminal Console: ${name}</h3>
                <span id="status-${sessionId}" class="console-status console-status-info">Connecting...</span>
            </div>
        </div>
        <div id="terminal-${sessionId}" class="console-terminal-container">
            <!-- xterm.js terminal will be inserted here -->
        </div>
        <div class="console-controls">
            <div class="console-controls-buttons">
                <button onclick="window.ConsoleManager.terminalControl('${sessionId}', 'stop')" class="console-btn console-btn-red">⏹ Stop</button>
                <button onclick="window.ConsoleManager.terminalControl('${sessionId}', 'destroy')" class="console-btn console-btn-dark-red">⚠️ Force Stop</button>
            </div>
            <div class="console-info">
                <span>Connected to: ${name}</span>
            </div>
        </div>
    `;
    
    consoleArea.appendChild(container);
    
    // Now initialize Terminal using the TerminalManager module
    try {
        await window.TerminalManager.launchTerminalInContainer(sessionId, name, `terminal-${sessionId}`, `status-${sessionId}`);
        session.instance = window.TerminalManager.getTermInstance(sessionId);
    } catch (error) {
        console.error(`Console Manager: Failed to initialize Terminal session`, error);
        window.UI.showStatus(`Terminal connection failed: ${error.message}`, 'error');
    }
}

/**
 * Cleanup VNC session
 */
function cleanupVncSession(sessionId) {
    console.log(`Console Manager: Cleaning up VNC session ${sessionId}`);
    // Delegate cleanup to VNCViewer module
    window.VNCViewer.cleanupSession(sessionId);
}

/**
 * Cleanup Terminal session
 */
function cleanupTerminalSession(sessionId) {
    console.log(`Console Manager: Cleaning up Terminal session ${sessionId}`);
    // Delegate cleanup to TerminalManager module
    window.TerminalManager.cleanupSession(sessionId);
}

/**
 * VNC Control actions
 */
async function vncControl(sessionId, action) {
    const session = consoleSessions.get(sessionId);
    if (!session || session.type !== 'vnc') return;
    
    const endpoint = `/vm/${session.name}/${action}`;
    const result = await window.API.apiCall(endpoint, 'POST');
    
    if (result && result.status === 'success') {
        window.UI.showStatus(`VM ${action} command sent`, 'success');
        if (action === 'stop' || action === 'destroy') {
            setTimeout(() => closeTab(sessionId), CONTROL_ACTION_DELAY);
        }
    }
}

/**
 * Terminal Control actions
 */
async function terminalControl(sessionId, action) {
    const session = consoleSessions.get(sessionId);
    if (!session || session.type !== 'terminal') return;
    
    const endpoint = `/vm/${session.name}/${action}`;
    const result = await window.API.apiCall(endpoint, 'POST');
    
    if (result && result.status === 'success') {
        window.UI.showStatus(`Container ${action} command sent`, 'success');
        if (action === 'stop' || action === 'destroy') {
            setTimeout(() => closeTab(sessionId), CONTROL_ACTION_DELAY);
        }
    }
}

/**
 * Handle VNC paste button
 */
async function handleVncPaste(sessionId) {
    const session = consoleSessions.get(sessionId);
    if (!session || session.type !== 'vnc' || !session.instance) return;
    
    try {
        const text = await navigator.clipboard.readText();
        if (text) {
            session.instance.clipboardPasteFrom(text);
            window.UI.showStatus('Text pasted to VNC', 'success');
        }
    } catch (err) {
        console.error('Failed to read clipboard:', err);
        window.UI.showStatus('Failed to read clipboard. Please grant permission.', 'error');
    }
}

// Export Console Manager functions
window.ConsoleManager = {
    initConsoleManager,
    openConsole,
    closeTab,
    vncControl,
    terminalControl,
    handleVncPaste
};

// Initialize on load
window.addEventListener('DOMContentLoaded', initConsoleManager);
