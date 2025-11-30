/**
 * API Keys Module
 * API key CRUD operations
 */

async function fetchApiKeys() {
    const result = await window.API.apiCall('/auth/api-keys');
    if (result && result.status === 'success') {
        renderApiKeys(result.api_keys || []);
    }
}

function renderApiKeys(keys) {
    const listEl = document.getElementById('api-keys-list');
    if (!listEl) return;
    
    listEl.innerHTML = '';
    
    if (keys.length === 0) {
        listEl.innerHTML = '<p class="text-center text-gray-500 p-4">No API keys configured</p>';
        return;
    }
    
    keys.forEach(key => {
        const keyCard = document.createElement('div');
        keyCard.className = 'p-4 border rounded-lg flex items-center justify-between';
        keyCard.innerHTML = `
            <div>
                <h4 class="font-bold">${key.name || 'API Key'}</h4>
                <p class="text-sm text-gray-600">Created: ${new Date(key.created_at).toLocaleDateString()}</p>
            </div>
            <button onclick="deleteApiKey('${key.id}')" 
                    class="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded">
                Revoke
            </button>
        `;
        listEl.appendChild(keyCard);
    });
}

async function createApiKey() {
    const name = prompt('Enter a name for this API key:');
    if (!name) return;
    
    const result = await window.API.apiCall('/auth/api-keys', 'POST', { name });
    if (result && result.status === 'success') {
        alert(`API Key created: ${result.api_key}\n\nPlease save this key - it won't be shown again!`);
        fetchApiKeys();
    }
}

async function deleteApiKey(keyId) {
    window.UI.showModal(
        'Revoke API Key',
        'Are you sure you want to revoke this API key?',
        async () => {
            const result = await window.API.apiCall(`/auth/api-keys/${keyId}`, 'DELETE');
            if (result && result.status === 'success') {
                window.UI.showStatus('API key revoked', 'success');
                fetchApiKeys();
            }
        },
        true
    );
}

// Export API Keys functions
window.APIKeys = {
    fetchApiKeys,
    createApiKey,
    deleteApiKey
};

// Expose functions globally for onclick handlers
window.fetchApiKeys = fetchApiKeys;
window.createApiKey = createApiKey;
window.deleteApiKey = deleteApiKey;
