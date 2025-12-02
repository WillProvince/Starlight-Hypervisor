/**
 * UI Helpers Module
 * Navigation, modals, status messages, and general UI utilities
 */

const statusMessageEl = document.getElementById('status-message');
const modalEl = document.getElementById('confirmation-modal');
const modalTitleEl = document.getElementById('modal-title');
const modalMessageEl = document.getElementById('modal-message');
const modalConfirmBtn = document.getElementById('modal-confirm');
const modalCancelBtn = document.getElementById('modal-cancel');

let pendingAction = null;
let vmRefreshInterval = null;

function showStatus(message, type = 'info') {
    statusMessageEl.textContent = message;
    statusMessageEl.className = `p-4 rounded-lg font-medium text-sm`;

    switch (type) {
        case 'success':
            statusMessageEl.classList.add('bg-green-100', 'text-green-800');
            break;
        case 'error':
            statusMessageEl.classList.add('bg-red-100', 'text-red-800');
            break;
        case 'info':
        default:
            statusMessageEl.classList.add('bg-blue-100', 'text-blue-800');
            break;
    }
    statusMessageEl.classList.remove('hidden');
    setTimeout(() => {
        statusMessageEl.classList.add('hidden');
    }, 5000);
}

function formatStatus(state) {
    switch (state) {
        case 1: return { text: 'Running', class: 'status-running' };
        case 2: return { text: 'Blocked', class: 'status-defined' };
        case 3: return { text: 'Paused', class: 'status-defined' };
        case 4: return { text: 'Shutdown', class: 'status-shutdown' };
        case 5: return { text: 'Shut Off', class: 'status-shutdown' };
        case 6: return { text: 'Crashed', class: 'status-error' };
        case 7: return { text: 'PMSuspended', class: 'status-defined' };
        case 0: return { text: 'No State / Defined', class: 'status-defined' };
        default: return { text: 'Unknown', class: 'status-error' };
    }
}

function showModal(title, message, confirmCallback, isDestructive = true) {
    modalTitleEl.textContent = title;
    modalMessageEl.textContent = message;
    modalConfirmBtn.className = `font-semibold py-2 px-4 rounded-lg transition duration-150 ${isDestructive ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-green-600 hover:bg-green-700 text-white'}`;
    modalEl.classList.remove('hidden');
    pendingAction = confirmCallback;
}

function hideModal() {
    modalEl.classList.add('hidden');
    pendingAction = null;
}

function navigateTo(page) {
    // Hide all pages
    document.querySelectorAll('.page-view').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
    
    // Show selected page
    document.getElementById(`page-${page}`).classList.add('active');
    
    // Activate nav item if it exists (some pages like themestore don't have nav items)
    const navItem = document.querySelector(`[data-page="${page}"]`);
    if (navItem) {
        navItem.classList.add('active');
    }
    
    // Update page title
    const titles = {
        'vms': 'Deployed',
        'appstore': 'App Store',
        'themestore': 'Theme Store',
        'settings': 'Settings',
        'api-keys': 'API Keys'
    };
    document.getElementById('page-title').textContent = titles[page] || 'Starlight';
    
    // Stop VM auto-refresh when leaving VMs page
    if (vmRefreshInterval) {
        clearInterval(vmRefreshInterval);
        vmRefreshInterval = null;
    }
    
    // Load data for the page
    if (page === 'vms') {
        window.VMManager.fetchVms(); // Initial load with loading message
        // Start auto-refresh every 5 seconds for VMs list (silent)
        vmRefreshInterval = setInterval(() => {
            window.VMManager.fetchVms(true); // Silent refresh
        }, 5000);
    } else if (page === 'appstore') {
        window.AppStore.fetchAppStore();
    } else if (page === 'themestore') {
        window.ThemeStore.fetchThemeStore();
    } else if (page === 'settings') {
        window.Settings.fetchRepositories();
        window.Settings.loadSettingsUsers();
        // Load storage settings
        if (window.Settings.loadStorageSettings) {
            window.Settings.loadStorageSettings();
        }
        // Load update status when navigating to settings
        try {
            window.Settings.loadUpdateStatus();
        } catch (error) {
            console.error('Error loading update status:', error);
        }
    } else if (page === 'api-keys') {
        window.APIKeys.fetchApiKeys();
    }
    
    // Close mobile sidebar
    if (window.innerWidth < 768) {
        document.getElementById('sidebar').classList.remove('mobile-open');
    }
}

function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('mobile-open');
}

// Setup modal button handlers
if (modalCancelBtn) {
    modalCancelBtn.onclick = hideModal;
}
if (modalConfirmBtn) {
    modalConfirmBtn.onclick = () => {
        if (pendingAction) {
            pendingAction();
        }
        hideModal();
    };
}

// Export UI functions
window.UI = {
    showStatus,
    formatStatus,
    showModal,
    hideModal,
    navigateTo,
    toggleSidebar
};

// Expose individual functions to global scope for onclick handlers
window.navigateTo = navigateTo;
window.toggleSidebar = toggleSidebar;
window.showModal = showModal;
window.hideModal = hideModal;
