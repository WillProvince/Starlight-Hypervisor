/**
 * Main Entry Point
 * Application initialization and startup logic
 */

// Initialize the application when DOM is loaded
async function startApplicationLogic() {
    console.log('Starlight application starting...');
    
    // Initialize theme system
    window.ThemeManager.initTheme();
    
    // Update theme selector if it exists
    const themeSelector = document.getElementById('theme-selector');
    if (themeSelector) {
        window.ThemeManager.updateThemeSelector();
    }
    
    // Load authentication token
    window.AUTH.loadAuthToken();
    
    // Setup login form handler
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', window.AUTH.handleLogin);
    }
    
    // Close user menu when clicking outside
    document.addEventListener('click', function(event) {
        const userMenu = document.getElementById('user-menu');
        const dropdown = document.getElementById('user-dropdown');
        if (userMenu && dropdown && !userMenu.contains(event.target)) {
            dropdown.classList.add('hidden');
        }
    });
    
    // Check authentication
    const authToken = window.AUTH.getAuthToken();
    if (authToken) {
        const result = await window.API.apiCall('/auth/verify');
        if (result && result.authenticated) {
            window.AUTH.updateAuthUI();
            window.AUTH.hideLoginModal();
        } else {
            window.AUTH.clearAuthToken();
            window.AUTH.showLoginModal();
        }
    } else {
        window.AUTH.showLoginModal();
    }
    
    // Check if noVNC is loaded
    await window.VNCViewer.checkNoVNCLoaded();
    
    // Only navigate if authenticated
    if (window.AUTH.getAuthToken()) {
        window.UI.navigateTo('vms');
        // Check for any existing downloads on startup
        window.AppStore.checkDownloadProgress();
    }
    
    console.log('Starlight application started');
}

// Start the application when window loads
window.onload = startApplicationLogic;

// Expose start function globally if needed
window.startApplicationLogic = startApplicationLogic;
