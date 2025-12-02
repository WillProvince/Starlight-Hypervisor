/**
 * Authentication Module
 * Handles login, logout, token management, and authentication state
 */

// Authentication state
let authToken = null;
let currentUser = null;
let isAdmin = false;

function loadAuthToken() {
    authToken = localStorage.getItem('starlight_auth_token');
    const userData = localStorage.getItem('starlight_user');
    if (userData) {
        try {
            const user = JSON.parse(userData);
            currentUser = user.username;
            isAdmin = user.role === 'admin';
        } catch (e) {
            console.error('Error parsing user data:', e);
        }
    }
}

function saveAuthToken(token, user) {
    authToken = token;
    currentUser = user.username;
    isAdmin = user.role === 'admin';
    localStorage.setItem('starlight_auth_token', token);
    localStorage.setItem('starlight_user', JSON.stringify(user));
}

function clearAuthToken() {
    authToken = null;
    currentUser = null;
    isAdmin = false;
    localStorage.removeItem('starlight_auth_token');
    localStorage.removeItem('starlight_user');
}

function showLoginModal() {
    document.getElementById('login-modal').style.display = 'flex';
    document.getElementById('login-error').classList.add('hidden');
    document.getElementById('login-username').value = '';
    document.getElementById('login-password').value = '';
}

function hideLoginModal() {
    document.getElementById('login-modal').style.display = 'none';
}

async function handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const submitBtn = document.getElementById('login-submit-btn');
    const errorDiv = document.getElementById('login-error');
    
    submitBtn.disabled = true;
    submitBtn.textContent = 'Signing in...';
    errorDiv.classList.add('hidden');
    
    try {
        const result = await window.API.apiCall('/auth/login', 'POST', { username, password });
        
        if (result && result.status === 'success') {
            saveAuthToken(result.token, result.user);
            updateAuthUI();
            hideLoginModal();
            window.UI.showStatus('Login successful!', 'success');
            window.UI.navigateTo('vms');
        } else {
            errorDiv.textContent = result?.message || 'Login failed';
            errorDiv.classList.remove('hidden');
        }
    } catch (error) {
        errorDiv.textContent = 'An error occurred during login';
        errorDiv.classList.remove('hidden');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Sign In';
    }
}

async function logout() {
    try {
        await window.API.apiCall('/auth/logout', 'POST');
    } catch (e) {
        console.error('Logout error:', e);
    }
    clearAuthToken();
    updateAuthUI();
    showLoginModal();
    window.UI.showStatus('Logged out successfully', 'info');
}

function updateAuthUI() {
    const userMenu = document.getElementById('user-menu');
    const usernameEl = document.getElementById('current-username');
    const rebootServerLink = document.getElementById('reboot-server-link');
    const shutdownServerLink = document.getElementById('shutdown-server-link');
    const administrationSection = document.getElementById('settings-administration-section');
    
    if (authToken && currentUser) {
        if (userMenu) userMenu.classList.remove('hidden');
        if (usernameEl) usernameEl.textContent = currentUser;
        const isRootUser = currentUser === 'root';
        if (isAdmin || isRootUser) {
            if (rebootServerLink) rebootServerLink.classList.remove('hidden');
            if (shutdownServerLink) shutdownServerLink.classList.remove('hidden');
            if (administrationSection) administrationSection.style.display = 'block';
        } else {
            if (rebootServerLink) rebootServerLink.classList.add('hidden');
            if (shutdownServerLink) shutdownServerLink.classList.add('hidden');
            if (administrationSection) administrationSection.style.display = 'none';
        }
        
        // Update settings page elements based on user role
        if (window.Settings && window.Settings.updateInlineCurrentPasswordVisibility) {
            window.Settings.updateInlineCurrentPasswordVisibility();
        }
        if (window.HostTerminal && window.HostTerminal.updateHostConsoleSectionVisibility) {
            window.HostTerminal.updateHostConsoleSectionVisibility();
        }
    } else {
        if (userMenu) userMenu.classList.add('hidden');
    }
}

function toggleUserMenu() {
    const dropdown = document.getElementById('user-dropdown');
    dropdown.classList.toggle('hidden');
}

function getAuthToken() {
    return authToken;
}

function getCurrentUser() {
    return currentUser;
}

function getIsAdmin() {
    return isAdmin;
}

// Export authentication functions
window.AUTH = {
    loadAuthToken,
    saveAuthToken,
    clearAuthToken,
    showLoginModal,
    hideLoginModal,
    handleLogin,
    logout,
    updateAuthUI,
    toggleUserMenu,
    getAuthToken,
    getCurrentUser,
    getIsAdmin
};

// Expose individual functions to global scope for onclick handlers
window.logout = logout;
window.toggleUserMenu = toggleUserMenu;
