/**
 * App Store Module
 * App store page logic, app deployment, and app detail modal
 */

const appStoreListEl = document.getElementById('app-store-list');
const repoLoadingIndicator = document.getElementById('repo-loading-indicator');
const appDetailModalEl = document.getElementById('app-detail-modal');
const sidebarDownloadsEl = document.getElementById('sidebar-downloads');
const sidebarDownloadsListEl = document.getElementById('sidebar-downloads-list');

let appStoreData = [];
let currentAppData = null;
let downloadPollInterval = null;
let currentCategory = 'all';

// Category definitions with display names
const APP_CATEGORIES = [
    { id: 'all', name: 'All' },
    { id: 'desktop', name: 'Desktop' },
    { id: 'server', name: 'Server' },
    { id: 'networking', name: 'Networking' },
    { id: 'smart-home', name: 'Smart Home' },
    { id: 'media', name: 'Media' },
    { id: 'downloads', name: 'Downloads' },
    { id: 'gaming', name: 'Gaming' },
    { id: 'monitoring', name: 'Monitoring' },
    { id: 'backup', name: 'Backup' },
    { id: 'utilities', name: 'Utilities' }
];

function getCategoryCounts() {
    const counts = { all: appStoreData.length };
    APP_CATEGORIES.forEach(cat => {
        if (cat.id !== 'all') {
            counts[cat.id] = appStoreData.filter(app => {
                const appCat = (app.category || '').toLowerCase().replace(/\s+/g, '-');
                return appCat === cat.id;
            }).length;
        }
    });
    return counts;
}

function renderCategoryDropdown() {
    const menuEl = document.getElementById('category-dropdown-menu');
    const btnTextEl = document.getElementById('category-dropdown-text');
    if (!menuEl) return;
    
    const counts = getCategoryCounts();
    const currentCatObj = APP_CATEGORIES.find(c => c.id === currentCategory) || APP_CATEGORIES[0];
    
    // Update button text
    if (btnTextEl) {
        btnTextEl.textContent = currentCatObj.name;
    }
    
    // Render dropdown options
    menuEl.innerHTML = APP_CATEGORIES.map(cat => {
        const isActive = cat.id === currentCategory;
        const count = counts[cat.id] || 0;
        return `
            <button onclick="selectCategory('${cat.id}')" 
                    class="w-full text-left px-4 py-2 text-sm hover:bg-gray-100 flex items-center justify-between category-option ${isActive ? 'category-option-active' : ''}"
                    style="color: var(--text-primary);">
                <span class="flex items-center">
                    ${isActive ? '<span class="text-indigo-600 mr-2">✓</span>' : '<span class="mr-2 opacity-0">✓</span>'}
                    ${cat.name}
                </span>
                <span class="text-xs" style="color: var(--text-tertiary);">(${count})</span>
            </button>
        `;
    }).join('');
}

function toggleCategoryDropdown() {
    const menuEl = document.getElementById('category-dropdown-menu');
    if (menuEl) {
        menuEl.classList.toggle('hidden');
    }
}

function selectCategory(categoryId) {
    currentCategory = categoryId;
    renderCategoryDropdown();
    toggleCategoryDropdown();
    filterApps();
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const dropdown = document.querySelector('.category-dropdown');
    const menuEl = document.getElementById('category-dropdown-menu');
    if (dropdown && menuEl && !dropdown.contains(event.target)) {
        menuEl.classList.add('hidden');
    }
});

async function fetchAppStore() {
    if (repoLoadingIndicator) repoLoadingIndicator.classList.remove('hidden');
    if (appStoreListEl) appStoreListEl.innerHTML = '';
    
    const result = await window.API.apiCall('/repositories/apps');
    
    if (result && result.status === 'success') {
        // Filter out themes - only show VMs and LXC containers
        const filteredApps = result.apps.filter(app => {
            const type = app.type || 'vm';
            return type === 'vm' || type === 'lxc';
        });
        renderAppStore(filteredApps);
        renderCategoryDropdown();
        const appCount = filteredApps.length;
        window.UI.showStatus(`Loaded ${appCount} apps from all enabled repositories`, 'success');
    } else if (appStoreListEl) {
        appStoreListEl.innerHTML = `<p class="text-center text-red-500 col-span-full p-4 bg-red-50 rounded-lg">
            Error loading apps from repositories.
        </p>`;
    }
    
    if (repoLoadingIndicator) repoLoadingIndicator.classList.add('hidden');
}

function renderAppStore(apps, storeData = true) {
    if (!appStoreListEl) return;
    appStoreListEl.innerHTML = '';
    if (storeData) {
        appStoreData = apps;
    }
    
    if (apps.length === 0) {
        appStoreListEl.innerHTML = '<p class="text-center text-gray-500 col-span-full">No deployable apps found. Enable repositories in the Settings page.</p>';
        return;
    }

    apps.forEach((app) => {
        // Find the original index in appStoreData for proper lookup
        const originalIndex = appStoreData.indexOf(app);
        
        const appCard = document.createElement('div');
        appCard.className = 'card rounded-xl p-5 border flex flex-col justify-between cursor-pointer hover:shadow-lg transition-shadow relative';
        
        const iconUrl = app.icon || 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%236366f1"%3E%3Cpath d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/%3E%3C/svg%3E';
        
        const appType = app.type || 'vm';
        const typeLabel = appType === 'lxc' ? 'LXC' : 'VM';
        const typeColor = appType === 'lxc' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700';
        const typeIcon = appType === 'lxc' ? 
            `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M20 7h-4V4c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2v3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zM10 4h4v3h-4V4zm10 16H4V9h16v11z"/><path d="M9 12h6v2H9zm0 4h6v2H9z"/></svg>` : 
            `<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M20 18c1.1 0 1.99-.9 1.99-2L22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zM4 6h16v10H4V6z"/></svg>`;
        
        appCard.innerHTML = `
            <div class="absolute top-3 right-3 flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold ${typeColor}">
                ${typeIcon}
                <span>${typeLabel}</span>
            </div>
            
            <div onclick='showAppDetailByIndex(${originalIndex})'>
                <div class="flex items-start mb-3 pr-16">
                    <img src="${iconUrl}" alt="${app.name}" class="app-icon mr-3" onerror="this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22%236366f1%22%3E%3Cpath d=%22M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z%22/%3E%3C/svg%3E'">
                    <div class="flex-1">
                        <h3 class="text-lg font-bold mb-1" style="color: var(--text-primary);">${app.name}</h3>
                        <p class="text-sm mb-2" style="color: var(--text-secondary);">${app.summary || app.description?.substring(0, 100) + '...' || 'No description provided.'}</p>
                    </div>
                </div>
                
                ${app.tags && app.tags.length > 0 ? `
                <div class="flex flex-wrap gap-1 mb-3">
                    ${app.tags.slice(0, 3).map(tag => `<span class="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">${tag}</span>`).join('')}
                </div>
                ` : ''}
                
                <div class="text-xs space-y-1 mb-2 border-t pt-2" style="color: var(--text-tertiary); border-color: var(--border-color);">
                    <div class="flex justify-between">
                        <span><strong>CPU:</strong> ${app.vcpus || '?'} cores</span>
                        <span><strong>RAM:</strong> ${app.memory_mb || '?'} MB</span>
                    </div>
                    <div class="flex justify-between">
                        <span><strong>Disk:</strong> ${app.disk_size_gb || '?'} GB</span>
                        <span class="text-indigo-600 font-semibold">${app.repo_name || 'Unknown'}</span>
                    </div>
                </div>
            </div>
            
            <div class="flex gap-2 mt-4">
                <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold py-2 px-4 rounded-lg transition duration-150"
                        onclick='event.stopPropagation(); showAppDetailByIndex(${originalIndex})'>
                    Details
                </button>
                <button class="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold py-2 px-4 rounded-lg transition duration-150"
                        onclick="event.stopPropagation(); deployAppByIndex(${originalIndex})">
                    Deploy
                </button>
            </div>
        `;
        appStoreListEl.appendChild(appCard);
    });
}

function showAppDetailByIndex(index) {
    if (index >= 0 && index < appStoreData.length) {
        showAppDetail(appStoreData[index]);
    }
}

function deployAppByIndex(index) {
    if (index >= 0 && index < appStoreData.length) {
        const app = appStoreData[index];
        deployApp(app.name, app.xml_url, app.disk_size_gb, app);
    }
}

function showAppDetail(app) {
    currentAppData = app;
    
    const iconUrl = app.icon || 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%236366f1"%3E%3Cpath d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/%3E%3C/svg%3E';
    document.getElementById('detail-app-icon').src = iconUrl;
    document.getElementById('detail-app-icon').alt = app.name;
    
    document.getElementById('detail-app-name').textContent = app.name;
    document.getElementById('detail-app-summary').textContent = app.summary || 'Virtual Machine Application';
    
    const specsEl = document.getElementById('detail-app-specs');
    specsEl.innerHTML = `
        <div class="text-center p-3 spec-box rounded-lg border">
            <div class="text-2xl font-bold text-indigo-600">${app.vcpus || '?'}</div>
            <div class="text-xs" style="color: var(--text-secondary);">vCPUs</div>
        </div>
        <div class="text-center p-3 spec-box rounded-lg border">
            <div class="text-2xl font-bold text-indigo-600">${app.memory_mb || '?'}</div>
            <div class="text-xs" style="color: var(--text-secondary);">MB RAM</div>
        </div>
        <div class="text-center p-3 spec-box rounded-lg border">
            <div class="text-2xl font-bold text-indigo-600">${app.disk_size_gb || '?'}</div>
            <div class="text-xs" style="color: var(--text-secondary);">GB Disk</div>
        </div>
        <div class="text-center p-3 spec-box rounded-lg border">
            <div class="text-2xl font-bold text-indigo-600">${app.category || 'N/A'}</div>
            <div class="text-xs" style="color: var(--text-secondary);">Category</div>
        </div>
    `;
    
    const descEl = document.getElementById('detail-app-description');
    if (app.description && typeof marked !== 'undefined') {
        descEl.innerHTML = marked.parse(app.description);
    } else {
        descEl.innerHTML = `<p>${app.description || 'No detailed description available.'}</p>`;
    }
    
    // Show image source info
    const imageSourceEl = document.getElementById('detail-image-source');
    if (imageSourceEl) {
        if (app.image_source) {
            const source = app.image_source;
            imageSourceEl.innerHTML = `
                <h4 class="font-semibold mb-2 flex items-center" style="color: var(--text-primary);">
                    <svg class="w-5 h-5 mr-2 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path>
                    </svg>
                    Image Source
                </h4>
                <div class="text-sm space-y-1" style="color: var(--text-secondary);">
                    <div><strong>Type:</strong> <span class="font-mono text-indigo-600">${source.type || 'Unknown'}</span></div>
                    <div><strong>Size:</strong> ${source.size_mb ? (source.size_mb >= 1024 ? (source.size_mb/1024).toFixed(1) + ' GB' : source.size_mb + ' MB') : 'Unknown'}</div>
                    ${source.requires_installation ? '<div class="text-amber-600"><strong>⚠️ Requires manual installation</strong></div>' : '<div class="text-green-600"><strong>✓ Pre-configured image</strong></div>'}
                    <div class="mt-2"><strong>URL:</strong> <a href="${source.url}" target="_blank" class="text-indigo-600 hover:underline text-xs break-all">${source.url}</a></div>
                </div>
            `;
        } else {
            imageSourceEl.innerHTML = '<p class="text-sm" style="color: var(--text-secondary);">No image source information available.</p>';
        }
    }
    
    // Show tags
    const tagsEl = document.getElementById('detail-app-tags');
    if (tagsEl) {
        if (app.tags && app.tags.length > 0) {
            tagsEl.innerHTML = `
                <h4 class="font-semibold mb-2" style="color: var(--text-primary);">Tags</h4>
                <div class="flex flex-wrap gap-2">
                    ${app.tags.map(tag => `<span class="text-sm bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full">${tag}</span>`).join('')}
                </div>
            `;
        } else {
            tagsEl.innerHTML = '';
        }
    }
    
    document.getElementById('detail-deploy-btn').onclick = () => {
        hideAppDetail();
        deployApp(app.name, app.xml_url, app.disk_size_gb, app);
    };
    
    appDetailModalEl.classList.remove('hidden');
}

function hideAppDetail() {
    appDetailModalEl.classList.add('hidden');
    currentAppData = null;
}

async function deployApp(appName, xmlUrl, diskSize, app = null) {
    const tempName = appName.toLowerCase().replace(/[^a-z0-9]/g, '-').slice(0, 15);
    const appType = app?.type || 'vm';
    const typeLabel = appType === 'lxc' ? 'LXC container' : 'VM';
    
    window.UI.showModal(
        'Confirm Deployment',
        `Deploy ${typeLabel} ${appName} as ${tempName} with a ${diskSize}GB disk?`,
        async () => {
            window.UI.showStatus(`Deployment of ${typeLabel} ${appName} started...`, 'info');
            
            const data = {
                xml_url: xmlUrl,
                vm_name: tempName,
                disk_size_gb: diskSize,
                type: appType
            };
            
            // Include app metadata (icon, name, etc.)
            if (app) {
                if (app.icon) {
                    data.icon = app.icon;
                }
                if (app.name) {
                    data.app_name = app.name;
                }
            }
            
            if (app && app.image_source && app.image_source.url) {
                if (app.image_source.type === 'qcow2' && !app.image_source.requires_installation) {
                    data.cloud_image_url = app.image_source.url;
                    window.UI.showStatus(`Downloading cloud image for ${appName}... This may take a few minutes.`, 'info');
                    startDownloadPolling();
                } else if (app.image_source.type === 'rootfs' && appType === 'lxc') {
                    data.image_source = app.image_source;
                    window.UI.showStatus(`Downloading rootfs for ${appName}... This may take a few minutes.`, 'info');
                    startDownloadPolling();
                }
            }
            
            const result = await window.API.apiCall('/vm/deploy', 'POST', data);
            if (result && result.status === 'success') {
                window.UI.showStatus(`${typeLabel} ${appName} deployed successfully!`, 'success');
                setTimeout(() => window.VMManager.fetchVms(), 2000);
            }
        },
        false
    );
}

async function checkDownloadProgress() {
    const result = await window.API.apiCall('/downloads');
    // Only render if we got a successful response
    // Silently ignore 404s as this endpoint may not exist in all deployments
    if (result && result.status === 'success') {
        renderDownloadProgress(result.downloads || []);
    }
}

function renderDownloadProgress(downloads) {
    if (!sidebarDownloadsListEl || !sidebarDownloadsEl) return;
    
    // Convert downloads object to array
    const downloadArray = Object.entries(downloads || {}).map(([vm_name, data]) => ({
        vm_name: vm_name,
        ...data
    }));
    
    if (downloadArray.length === 0) {
        sidebarDownloadsEl.classList.add('hidden');
        return;
    }
    
    sidebarDownloadsEl.classList.remove('hidden');
    sidebarDownloadsListEl.innerHTML = '';
    
    downloadArray.forEach(download => {
        const itemEl = document.createElement('div');
        itemEl.className = 'sidebar-download-item';
        
        // Calculate percentage from progress and total
        let percentage = 0;
        if (download.total && download.total > 0) {
            percentage = Math.round((download.progress / download.total) * 100);
        }
        
        const isIndeterminate = download.status === 'downloading' && !percentage;
        
        itemEl.innerHTML = `
            <div class="sidebar-download-name">${download.vm_name}</div>
            <div class="sidebar-download-status">${download.message || download.status}: ${percentage}%</div>
            <div class="sidebar-progress-bar">
                <div class="sidebar-progress-fill ${isIndeterminate ? 'indeterminate' : ''}" 
                     style="width: ${percentage}%"></div>
            </div>
        `;
        
        sidebarDownloadsListEl.appendChild(itemEl);
    });
}

function startDownloadPolling() {
    if (downloadPollInterval) clearInterval(downloadPollInterval);
    checkDownloadProgress();
    downloadPollInterval = setInterval(checkDownloadProgress, 2000);
}

function filterApps() {
    const searchEl = document.getElementById('app-search');
    const term = searchEl ? searchEl.value.toLowerCase().trim() : '';
    
    let filtered = appStoreData;
    
    // Apply category filter first (if not "all")
    if (currentCategory !== 'all') {
        filtered = filtered.filter(app => {
            const appCat = (app.category || '').toLowerCase().replace(/\s+/g, '-');
            return appCat === currentCategory;
        });
    }
    
    // Apply search filter (if term is not empty)
    if (term) {
        filtered = filtered.filter(app => {
            const appType = app.type || 'vm';
            const typeLabel = appType === 'lxc' ? 'lxc' : 'vm';
            
            // Search by name
            if (app.name.toLowerCase().includes(term)) return true;
            
            // Search by summary
            if (app.summary && app.summary.toLowerCase().includes(term)) return true;
            
            // Search by description
            if (app.description && app.description.toLowerCase().includes(term)) return true;
            
            // Search by tags
            if (app.tags && app.tags.some(tag => tag.toLowerCase().includes(term))) return true;
            
            // Search by type
            if (typeLabel.includes(term)) return true;
            
            // Search by category
            if (app.category && app.category.toLowerCase().includes(term)) return true;
            
            return false;
        });
    }
    
    renderAppStore(filtered, false);
}

// Export AppStore functions
window.AppStore = {
    fetchAppStore,
    filterApps,
    showAppDetail,
    hideAppDetail,
    deployApp,
    showAppDetailByIndex,
    deployAppByIndex,
    checkDownloadProgress,
    startDownloadPolling,
    toggleCategoryDropdown,
    selectCategory,
    renderCategoryDropdown
};

// Expose functions globally for onclick handlers
window.fetchAppStore = fetchAppStore;
window.filterApps = filterApps;
window.deployApp = deployApp;
window.showAppDetail = showAppDetail;
window.hideAppDetail = hideAppDetail;
window.showAppDetailByIndex = showAppDetailByIndex;
window.deployAppByIndex = deployAppByIndex;
window.toggleCategoryDropdown = toggleCategoryDropdown;
window.selectCategory = selectCategory;
