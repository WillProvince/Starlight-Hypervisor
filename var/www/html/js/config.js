/**
 * Configuration Constants
 * Global configuration values used throughout the application
 */

const API_BASE = '/api';

// Constants for update system
const UPDATE_SERVICE_RESTART_DELAY = 3000; // Wait 3 seconds for service to restart
const UPDATE_PAGE_RELOAD_DELAY = 2000; // Wait 2 seconds before reloading page

// Update check interval (if needed)
const UPDATE_CHECK_INTERVAL = 300000; // 5 minutes

// Export for use in other modules
window.CONFIG = {
    API_BASE,
    UPDATE_SERVICE_RESTART_DELAY,
    UPDATE_PAGE_RELOAD_DELAY,
    UPDATE_CHECK_INTERVAL
};
