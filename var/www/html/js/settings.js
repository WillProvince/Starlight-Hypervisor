/**
 * Settings Module
 * Settings page rendering, repository management, update system, and theme controls
 */

const repositoriesListEl = document.getElementById('repositories-list');
const addRepoModalEl = document.getElementById('add-repository-modal');

async function fetchRepositories() {
    const result = await window.API.apiCall('/repositories');
    if (result && result.status === 'success') {
        renderRepositories(result.repositories || []);
    }
}

function renderRepositories(repos) {
    if (!repositoriesListEl) return;
    repositoriesListEl.innerHTML = '';
    
    if (repos.length === 0) {
        repositoriesListEl.innerHTML = '<p class="text-center text-gray-500 p-4">No repositories configured</p>';
        return;
    }
    
    repos.forEach(repo => {
        const repoCard = document.createElement('div');
        repoCard.className = 'p-4 border rounded-lg';
        repoCard.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex-1">
                    <h4 class="font-bold">${repo.name}</h4>
                    <p class="text-sm text-gray-600">${repo.url}</p>
                </div>
                <div class="flex items-center gap-2">
                    <label class="toggle-switch">
                        <input type="checkbox" ${repo.enabled ? 'checked' : ''} 
                               onchange="toggleRepository('${repo.id}', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>
                    <button onclick="deleteRepository('${repo.id}')" 
                            class="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded">
                        Delete
                    </button>
                </div>
            </div>
        `;
        repositoriesListEl.appendChild(repoCard);
    });
}

async function toggleRepository(repoId, enableState) {
    const result = await window.API.apiCall(`/repositories/${repoId}`, 'PUT', { enabled: enableState });
    if (result && result.status === 'success') {
        window.UI.showStatus(`Repository ${enableState ? 'enabled' : 'disabled'}`, 'success');
    }
}

function deleteRepository(repoId) {
    window.UI.showModal(
        'Confirm Deletion',
        'Are you sure you want to delete this repository?',
        async () => {
            const result = await window.API.apiCall(`/repositories/${repoId}`, 'DELETE');
            if (result && result.status === 'success') {
                window.UI.showStatus('Repository deleted', 'success');
                fetchRepositories();
            }
        },
        true
    );
}

function showAddRepositoryModal() {
    if (addRepoModalEl) addRepoModalEl.classList.remove('hidden');
}

function hideAddRepositoryModal() {
    if (addRepoModalEl) addRepoModalEl.classList.add('hidden');
}

async function loadUpdateStatus() {
    // Placeholder for update status loading
    console.log('Loading update status...');
}

// User Management in Settings
async function loadSettingsUsers() {
    const userManagementSection = document.getElementById('user-management-section');
    const administrationSection = document.getElementById('settings-administration-section');
    const isAdmin = window.AUTH.getIsAdmin();
    const currentUser = window.AUTH.getCurrentUser();
    const isRoot = currentUser === 'root';
    
    // Update host console section visibility (only visible for root user)
    if (window.HostTerminal && window.HostTerminal.updateHostConsoleSectionVisibility) {
        window.HostTerminal.updateHostConsoleSectionVisibility();
    }
    
    // Hide entire administration section if not admin or root
    if (administrationSection) {
        if (!isAdmin && !isRoot) {
            administrationSection.style.display = 'none';
            return;
        }
        administrationSection.style.display = 'block';
    }
    
    // Legacy check: Also handle the user management section visibility separately
    // This maintains compatibility with code that may reference user-management-section directly
    if (!userManagementSection) return;
    
    if (!isAdmin && !isRoot) {
        userManagementSection.style.display = 'none';
        return;
    }
    
    userManagementSection.style.display = 'block';
    
    const result = await window.API.apiCall('/users');
    if (result && result.status === 'success') {
        let users = result.users || [];
        
        // If current user is root and not in the list, add it manually
        // (backend filters out system users with UID < 1000, including root)
        if (isRoot && !users.find(u => u.username === 'root')) {
            users.unshift({
                username: 'root',
                role: 'admin',
                uid: 0
            });
        }
        
        renderSettingsUsers(users);
    }
}

function renderSettingsUsers(users) {
    const listEl = document.getElementById('settings-users-list');
    if (!listEl) return;
    
    listEl.innerHTML = '';
    
    // Filter out system users that should be hidden
    const hiddenUsers = ['nobody', 'anybody', 'libvirt-qemu'];
    const filteredUsers = users.filter(user => !hiddenUsers.includes(user.username));
    
    if (filteredUsers.length === 0) {
        listEl.innerHTML = '<p class="text-center p-4" style="color: var(--text-tertiary);">No users found</p>';
        return;
    }
    
    const currentUser = window.AUTH.getCurrentUser();
    const isRoot = currentUser === 'root';
    const isAdmin = window.AUTH.getIsAdmin();
    
    filteredUsers.forEach(user => {
        const userCard = document.createElement('div');
        userCard.className = 'p-4 border rounded-lg flex items-center justify-between';
        userCard.style.borderColor = 'var(--border-color)';
        
        // Prevent users from deleting themselves or root user
        const isSelf = user.username === currentUser;
        const isRootUser = user.username === 'root';
        // Show delete button for non-admin users, or for admin users if current user is root
        const canDelete = !isSelf && !isRootUser && (user.role !== 'admin' || isRoot);
        
        // Determine if user can change this password
        // Any user can change their own password
        // Admin users can change any password except root (only root can change root password)
        // Non-admin users can only change their own password
        let canChangePassword = false;
        if (isSelf) {
            canChangePassword = true; // Anyone can change their own password
        } else if (isAdmin) {
            // Admin can change anyone's password except root (unless they are root)
            canChangePassword = (user.username !== 'root') || isRoot;
        }
        // else: non-admin cannot change other users' passwords
        
        // Determine label for non-deletable users
        let label = '';
        if (isSelf) {
            label = '<span class="text-sm" style="color: var(--text-tertiary);">Current User</span>';
        } else if (isRootUser) {
            label = '<span class="text-sm" style="color: var(--text-tertiary);">System User</span>';
        } else if (user.role === 'admin') {
            label = '<span class="text-sm" style="color: var(--text-tertiary);">Admin</span>';
        }
        
        userCard.innerHTML = `
            <div>
                <h4 class="font-bold" style="color: var(--text-primary);">${user.username}</h4>
                <p class="text-sm" style="color: var(--text-tertiary);">Role: ${user.role || 'user'}</p>
            </div>
            <div class="flex gap-2">
                ${canChangePassword ? `
                    <button onclick="showChangePasswordModal('${user.username}')" 
                            class="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded transition duration-150">
                        Change Password
                    </button>
                ` : ''}
                ${canDelete ? `
                    <button onclick="deleteSettingsUser('${user.username}')" 
                            class="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded transition duration-150">
                        Delete
                    </button>
                ` : label}
            </div>
        `;
        listEl.appendChild(userCard);
    });
}

function showCreateUserModal() {
    const modal = document.getElementById('create-user-modal');
    if (modal) modal.classList.remove('hidden');
}

function hideCreateUserModal() {
    const modal = document.getElementById('create-user-modal');
    if (modal) modal.classList.add('hidden');
    // Reset form
    const form = document.getElementById('create-user-form');
    if (form) form.reset();
}

function showChangePasswordModal(username) {
    const modal = document.getElementById('change-password-modal');
    const usernameInput = document.getElementById('change-password-username');
    const usernameDisplay = document.getElementById('change-password-username-display');
    const currentPasswordContainer = document.getElementById('modal-current-password-container');
    const currentPasswordInput = document.getElementById('change-password-current');
    
    if (modal && usernameInput && usernameDisplay) {
        usernameInput.value = username;
        usernameDisplay.value = username;
        
        // Show current password field only when user is changing their own password and is not admin
        const currentUser = window.AUTH.getCurrentUser();
        const isAdmin = window.AUTH.getIsAdmin();
        const isSelf = username === currentUser;
        
        if (currentPasswordContainer && currentPasswordInput) {
            // Show current password field if user is changing their own password and is not admin
            if (isSelf && !isAdmin) {
                currentPasswordContainer.classList.remove('hidden');
                currentPasswordInput.required = true;
            } else {
                currentPasswordContainer.classList.add('hidden');
                currentPasswordInput.required = false;
                currentPasswordInput.value = '';
            }
        }
        
        modal.classList.remove('hidden');
    }
}

function hideChangePasswordModal() {
    const modal = document.getElementById('change-password-modal');
    if (modal) modal.classList.add('hidden');
    // Reset form
    const form = document.getElementById('change-password-form');
    if (form) form.reset();
    // Hide current password container
    const currentPasswordContainer = document.getElementById('modal-current-password-container');
    if (currentPasswordContainer) {
        currentPasswordContainer.classList.add('hidden');
    }
}

function showUserChangePasswordModal() {
    // Open change password modal for the current logged-in user
    const currentUser = window.AUTH.getCurrentUser();
    if (currentUser) {
        showChangePasswordModal(currentUser);
    }
}

async function deleteSettingsUser(username) {
    window.UI.showModal(
        'Delete User',
        `Are you sure you want to delete user ${username}?`,
        async () => {
            const result = await window.API.apiCall(`/users/${username}`, 'DELETE');
            if (result && result.status === 'success') {
                window.UI.showStatus('User deleted', 'success');
                loadSettingsUsers();
            }
        },
        true
    );
}

// Handle create user form submission
document.addEventListener('DOMContentLoaded', () => {
    const createUserForm = document.getElementById('create-user-form');
    if (createUserForm) {
        createUserForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('new-username').value;
            const password = document.getElementById('new-password').value;
            const fullname = document.getElementById('new-fullname').value;
            const role = document.getElementById('new-user-role').value;
            
            const result = await window.API.apiCall('/users', 'POST', {
                username,
                password,
                fullname,
                role
            });
            
            if (result && result.status === 'success') {
                window.UI.showStatus('User created successfully', 'success');
                hideCreateUserModal();
                loadSettingsUsers();
            }
        });
    }
    
    // Handle change password form submission
    const changePasswordForm = document.getElementById('change-password-form');
    if (changePasswordForm) {
        changePasswordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('change-password-username').value;
            const newPassword = document.getElementById('change-password-new').value;
            const confirmPassword = document.getElementById('change-password-confirm').value;
            const currentPasswordInput = document.getElementById('change-password-current');
            const currentPassword = currentPasswordInput ? currentPasswordInput.value : '';
            
            // Check if current password is required (changing own password and not admin)
            const currentUser = window.AUTH.getCurrentUser();
            const isAdmin = window.AUTH.getIsAdmin();
            const isSelf = username === currentUser;
            const requireCurrentPassword = isSelf && !isAdmin;
            
            // Validate current password is provided if required
            if (requireCurrentPassword && !currentPassword) {
                window.UI.showStatus('Current password is required', 'error');
                return;
            }
            
            // Validate passwords match
            if (newPassword !== confirmPassword) {
                window.UI.showStatus('Passwords do not match', 'error');
                return;
            }
            
            // Validate password length (minimum 4 characters for PAM compatibility)
            if (newPassword.length < 4) {
                window.UI.showStatus('Password must be at least 4 characters long', 'error');
                return;
            }
            
            // Build request body
            const requestBody = { new_password: newPassword };
            if (requireCurrentPassword && currentPassword) {
                requestBody.current_password = currentPassword;
            }
            
            const result = await window.API.apiCall(`/users/${username}/password`, 'POST', requestBody);
            
            if (result && result.status === 'success') {
                window.UI.showStatus('Password changed successfully', 'success');
                hideChangePasswordModal();
            } else {
                // Show error message if password change failed
                const errorMessage = result?.message || 'Failed to change password';
                window.UI.showStatus(errorMessage, 'error');
            }
        });
    }
    
    // Handle inline password form submission
    const inlinePasswordForm = document.getElementById('inline-password-form');
    if (inlinePasswordForm) {
        inlinePasswordForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const currentUser = window.AUTH.getCurrentUser();
            const isAdmin = window.AUTH.getIsAdmin();
            const currentPasswordInput = document.getElementById('inline-current-password');
            const currentPassword = currentPasswordInput ? currentPasswordInput.value : '';
            const newPassword = document.getElementById('inline-new-password').value;
            const confirmPassword = document.getElementById('inline-confirm-password').value;
            
            // Current password is required for non-admin users changing their own password
            const requireCurrentPassword = !isAdmin;
            
            // Validate current password is provided if required
            if (requireCurrentPassword && !currentPassword) {
                window.UI.showStatus('Current password is required', 'error');
                return;
            }
            
            // Validate passwords match
            if (newPassword !== confirmPassword) {
                window.UI.showStatus('Passwords do not match', 'error');
                return;
            }
            
            // Validate password length (minimum 4 characters for PAM compatibility)
            if (newPassword.length < 4) {
                window.UI.showStatus('Password must be at least 4 characters long', 'error');
                return;
            }
            
            // Build request body
            const requestBody = { new_password: newPassword };
            if (requireCurrentPassword && currentPassword) {
                requestBody.current_password = currentPassword;
            }
            
            const result = await window.API.apiCall(`/users/${currentUser}/password`, 'POST', requestBody);
            
            if (result && result.status === 'success') {
                window.UI.showStatus('Password changed successfully', 'success');
                inlinePasswordForm.reset();
            } else {
                const errorMessage = result?.message || 'Failed to change password';
                window.UI.showStatus(errorMessage, 'error');
            }
        });
    }
    
    // Update inline current password field visibility based on user role
    updateInlineCurrentPasswordVisibility();
});

// Update inline current password field visibility
function updateInlineCurrentPasswordVisibility() {
    const currentPasswordContainer = document.getElementById('inline-current-password-container');
    const currentPasswordInput = document.getElementById('inline-current-password');
    const isAdmin = window.AUTH.getIsAdmin();
    
    if (currentPasswordContainer && currentPasswordInput) {
        // Show current password field only for non-admin users
        if (isAdmin) {
            currentPasswordContainer.style.display = 'none';
            currentPasswordInput.required = false;
        } else {
            currentPasswordContainer.style.display = 'block';
            currentPasswordInput.required = true;
        }
    }
}

// Toggle expandable settings sections
function toggleSettingsSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (!section) return;
    
    const parentSection = section.closest('.expandable-section');
    if (parentSection) {
        parentSection.classList.toggle('collapsed');
    }
}

// Load storage settings when settings page is activated
function loadStorageSettings() {
    if (window.StorageSettings) {
        window.StorageSettings.loadStorageConfig();
        window.StorageSettings.loadStorageInfo();
    }
}

// Export Settings functions
window.Settings = {
    fetchRepositories,
    toggleRepository,
    deleteRepository,
    showAddRepositoryModal,
    hideAddRepositoryModal,
    loadUpdateStatus,
    loadSettingsUsers,
    toggleSettingsSection,
    updateInlineCurrentPasswordVisibility,
    loadStorageSettings
};

// Expose functions globally for onclick handlers
window.fetchRepositories = fetchRepositories;
window.toggleRepository = toggleRepository;
window.deleteRepository = deleteRepository;
window.showAddRepositoryModal = showAddRepositoryModal;
window.hideAddRepositoryModal = hideAddRepositoryModal;
window.showCreateUserModal = showCreateUserModal;
window.hideCreateUserModal = hideCreateUserModal;
window.showChangePasswordModal = showChangePasswordModal;
window.hideChangePasswordModal = hideChangePasswordModal;
window.showUserChangePasswordModal = showUserChangePasswordModal;
window.deleteSettingsUser = deleteSettingsUser;
window.toggleSettingsSection = toggleSettingsSection;
window.updateInlineCurrentPasswordVisibility = updateInlineCurrentPasswordVisibility;
window.loadStorageSettings = loadStorageSettings;
