/**
 * User Management Module
 * User CRUD operations (admin only)
 */

async function fetchUsers() {
    const result = await window.API.apiCall('/users');
    if (result && result.status === 'success') {
        renderUsers(result.users || []);
    }
}

function renderUsers(users) {
    const listEl = document.getElementById('users-list');
    if (!listEl) return;
    
    listEl.innerHTML = '';
    
    if (users.length === 0) {
        listEl.innerHTML = '<p class="text-center text-gray-500 p-4">No users found</p>';
        return;
    }
    
    users.forEach(user => {
        const userCard = document.createElement('div');
        userCard.className = 'p-4 border rounded-lg flex items-center justify-between';
        userCard.innerHTML = `
            <div>
                <h4 class="font-bold">${user.username}</h4>
                <p class="text-sm text-gray-600">Role: ${user.role || 'user'}</p>
            </div>
            <div class="flex gap-2">
                ${user.role !== 'admin' ? `
                    <button onclick="deleteUser('${user.username}')" 
                            class="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded">
                        Delete
                    </button>
                ` : '<span class="text-gray-500 text-sm">Admin</span>'}
            </div>
        `;
        listEl.appendChild(userCard);
    });
}

async function createUser() {
    const username = prompt('Enter username:');
    if (!username) return;
    
    const password = prompt('Enter password:');
    if (!password) return;
    
    const result = await window.API.apiCall('/users', 'POST', { username, password });
    if (result && result.status === 'success') {
        window.UI.showStatus('User created successfully', 'success');
        fetchUsers();
    }
}

async function deleteUser(username) {
    window.UI.showModal(
        'Delete User',
        `Are you sure you want to delete user ${username}?`,
        async () => {
            const result = await window.API.apiCall(`/users/${username}`, 'DELETE');
            if (result && result.status === 'success') {
                window.UI.showStatus('User deleted', 'success');
                fetchUsers();
            }
        },
        true
    );
}

// Export User Management functions
window.UserManagement = {
    fetchUsers,
    createUser,
    deleteUser
};

// Expose functions globally for onclick handlers
window.fetchUsers = fetchUsers;
window.createUser = createUser;
window.deleteUser = deleteUser;
