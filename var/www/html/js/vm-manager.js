/**
 * VM Manager Module
 * VM list, actions, rendering, and management functionality
 */

const vmListEl = document.getElementById('vm-list');
const loadingIndicator = document.getElementById('loading-indicator');
const vmSettingsModalEl = document.getElementById('vm-settings-modal');
let currentVmSettings = null;
let allVms = [];

function performVmAction(name, action) {
    const apiExecute = async () => {
        const endpoint = `/vm/${name}/${action}`;
        let verb = '';
        let timeout = 2000;

        switch(action) {
            case 'eject': verb = 'Ejecting ISO'; break;
            case 'start': verb = 'Starting'; break;
            case 'stop': verb = 'Stopping (Graceful)'; timeout = 5000; break;
            case 'destroy': verb = 'Force Stopping'; break;
            case 'delete': verb = 'Deleting Configuration'; break;
            default: verb = 'Sending command';
        }

        window.UI.showStatus(`${verb} ${name}...`, 'info');

        const result = await window.API.apiCall(endpoint, 'POST');
        if (result && result.status === 'success') {
            window.UI.showStatus(`VM ${name} successfully received ${action} command.`, 'success');
            setTimeout(fetchVms, timeout);
        }
    };
    
    if (action === 'delete') {
        window.UI.showModal(
            'Confirm Deletion',
            `Are you sure you want to permanently UNDEFINE VM: ${name} and DELETE its virtual disk?`,
            apiExecute,
            true
        );
    } else if (action === 'destroy') {
        window.UI.showModal(
            'Confirm Force Stop',
            `Are you sure you want to FORCE SHUTDOWN VM: ${name}? This may cause data loss.`,
            apiExecute,
            true
        );
    } else {
        apiExecute();
    }
}

function renderVms(vms) {
    allVms = vms;
    vmListEl.innerHTML = '';
    if (loadingIndicator) loadingIndicator.classList.add('hidden');

    if (vms.length === 0) {
        vmListEl.innerHTML = '<p class="text-center p-8 rounded-lg" style="color: var(--text-secondary); background-color: var(--bg-tertiary);">No virtual machines found on the hypervisor.</p>';
        return;
    }

    vms.forEach(vm => {
        const { text: statusText, class: statusClass } = window.UI.formatStatus(vm.state);
        const isRunning = vm.state === 1;
        const ipDisplay = vm.ip_address ? vm.ip_address : 'Not Found';
        const ipClass = vm.ip_address ? 'text-green-600' : 'text-gray-400';
        const vncPortDisplay = vm.vnc_port ? vm.vnc_port : 'N/A';

        // Type badge
        const vmType = vm.type || 'vm';
        const typeLabel = vmType === 'lxc' ? 'LXC' : 'VM';
        const typeColor = vmType === 'lxc' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700';
        const typeIcon = vmType === 'lxc' ? 
            `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M20 7h-4V4c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2v3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zM10 4h4v3h-4V4zm10 16H4V9h16v11z"/><path d="M9 12h6v2H9zm0 4h6v2H9z"/></svg>` : 
            `<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24"><path d="M20 18c1.1 0 1.99-.9 1.99-2L22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zM4 6h16v10H4V6z"/></svg>`;

        const vmCard = document.createElement('div');
        vmCard.className = 'vm-card flex flex-col lg:flex-row items-start lg:items-center justify-between p-4 rounded-lg border transition duration-150 relative';
        
        vmCard.innerHTML = `
            <!-- Type indicator badge in top right -->
            <div class="absolute top-3 right-3 flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${typeColor}">
                ${typeIcon}
                <span>${typeLabel}</span>
            </div>
            
            <div class="mb-3 lg:mb-0 lg:w-1/4 pr-16 flex items-start gap-3">
                <div class="flex-shrink-0 mt-1">
                    ${vm.icon ? `
                        <img src="${vm.icon}" alt="${vm.name}" class="w-10 h-10 rounded-lg object-cover" 
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                        <div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background-color: var(--bg-tertiary); display: none;">
                            <svg class="w-6 h-6 text-indigo-600" fill="currentColor" viewBox="0 0 24 24">
                                ${vmType === 'lxc' ? 
                                    '<path d="M20 7h-4V4c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2v3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zM10 4h4v3h-4V4zm10 16H4V9h16v11z"/><path d="M9 12h6v2H9zm0 4h6v2H9z"/>' :
                                    '<path d="M20 18c1.1 0 1.99-.9 1.99-2L22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zM4 6h16v10H4V6z"/>'
                                }
                            </svg>
                        </div>
                    ` : `
                        <div class="w-10 h-10 rounded-lg flex items-center justify-center" style="background-color: var(--bg-tertiary);">
                            <svg class="w-6 h-6 text-indigo-600" fill="currentColor" viewBox="0 0 24 24">
                                ${vmType === 'lxc' ? 
                                    '<path d="M20 7h-4V4c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2v3H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V9c0-1.1-.9-2-2-2zM10 4h4v3h-4V4zm10 16H4V9h16v11z"/><path d="M9 12h6v2H9zm0 4h6v2H9z"/>' :
                                    '<path d="M20 18c1.1 0 1.99-.9 1.99-2L22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zM4 6h16v10H4V6z"/>'
                                }
                            </svg>
                        </div>
                    `}
                </div>
                <div class="flex-1">
                    <p class="text-lg font-bold" style="color: var(--text-primary);">${vm.name}</p>
                    <p class="text-sm" style="color: var(--text-secondary);">UUID: ${vm.uuid.slice(0, 8)}...</p>
                    <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${statusClass}">${statusText}</span>
                </div>
            </div>
            
            <div class="flex flex-col text-sm w-full lg:w-1/6 mb-3 lg:mb-0" style="color: var(--text-secondary);">
                <span><strong class="font-medium">vCPUs:</strong> ${vm.vcpus}</span>
                <span><strong class="font-medium">RAM:</strong> ${(vm.memory / 1024).toFixed(1)} GB</span>
            </div>

            <div class="flex flex-col text-sm w-full lg:w-1/4 mb-3 lg:mb-0" style="color: var(--text-secondary);">
                ${isRunning ? 
                    `<span><strong class="font-medium">VNC Port:</strong> <span class="text-indigo-600">${vncPortDisplay}</span></span>
                     <span><strong class="font-medium">VM IP:</strong> <span class="${ipClass} font-mono">${ipDisplay}</span></span>`
                    : 
                    `<span style="color: var(--text-tertiary);">VM is Shut Off / Defined</span>`
                }
            </div>

            <div class="mt-3 lg:mt-0 lg:w-1/4 flex flex-wrap gap-2 justify-end">
            </div>
        `;

        const actionsDiv = vmCard.querySelector('.justify-end');

        // Settings button (available for all VMs)
        const settingsBtn = createActionButton('⚙️', 'bg-gray-600 hover:bg-gray-700', () => showVmSettings(vm.name, vm));
        settingsBtn.title = 'VM Settings';
        actionsDiv.appendChild(settingsBtn);

        if (isRunning) {
            // Unified "Take Over" button for both VMs and LXC
            const takeOverBtn = createActionButton('Take Over', 'bg-indigo-600 hover:bg-indigo-700', () => {
                if (vm.type === 'lxc') {
                    // Use unified console manager for terminal
                    if (window.ConsoleManager) {
                        window.ConsoleManager.openConsole(vm.name, 'terminal', null, vm.icon);
                    } else {
                        // Fallback to old method
                        window.TerminalManager.launchTerminal(vm.name);
                    }
                } else {
                    // Use unified console manager for VNC
                    if (window.ConsoleManager) {
                        window.ConsoleManager.openConsole(vm.name, 'vnc', vm.vnc_port, vm.icon);
                    } else {
                        // Fallback to old method
                        window.VNCViewer.launchVnc(vm.name, vm.vnc_port);
                    }
                }
            });
            actionsDiv.appendChild(takeOverBtn);
            
            const stopBtn = createActionButton('Stop', 'bg-yellow-500 hover:bg-yellow-600', () => performVmAction(vm.name, 'stop'));
            actionsDiv.appendChild(stopBtn);
            
            const destroyBtn = createActionButton('Force Stop', 'bg-red-500 hover:bg-red-600', () => performVmAction(vm.name, 'destroy'));
            actionsDiv.appendChild(destroyBtn);

        } else {
            const startBtn = createActionButton('Start', 'bg-green-600 hover:bg-green-700', () => performVmAction(vm.name, 'start'));
            actionsDiv.appendChild(startBtn);

            const deleteBtn = createActionButton('Delete', 'bg-gray-500 hover:bg-gray-600', () => performVmAction(vm.name, 'delete'));
            actionsDiv.appendChild(deleteBtn);
        }

        vmListEl.appendChild(vmCard);
    });
}

function createActionButton(text, colors, action) {
    const btn = document.createElement('button');
    btn.textContent = text;
    btn.className = `text-white text-xs font-semibold py-1 px-2 rounded-md transition duration-150 ${colors}`;
    btn.onclick = action;
    return btn;
}

async function fetchVms(silent = false) {
    // Only show loading message on manual refresh, not auto-refresh
    if (!silent && vmListEl) {
        vmListEl.innerHTML = '<p class="text-center text-gray-500 p-8 bg-gray-50 rounded-lg"><span class="status-loading font-medium px-2 py-0.5 rounded-full">Refreshing...</span></p>';
    }
    
    const data = await window.API.apiCall('/vm_list');
    if (data) {
        renderVms(data.vms);
    } else if (vmListEl) {
        vmListEl.innerHTML = '<p class="text-center text-red-500 p-8 bg-red-50 rounded-lg">Failed to load virtual machines.</p>';
    }
}

function filterVms(searchTerm) {
    const term = searchTerm.toLowerCase().trim();
    
    if (!term) {
        renderVms(allVms);
        return;
    }
    
    const filtered = allVms.filter(vm => {
        const { text: statusText } = window.UI.formatStatus(vm.state);
        const vmType = vm.type || 'vm';
        const typeLabel = vmType === 'lxc' ? 'lxc' : 'vm';
        
        return vm.name.toLowerCase().includes(term) ||
               vm.uuid.toLowerCase().includes(term) ||
               statusText.toLowerCase().includes(term) ||
               typeLabel.includes(term) ||
               (vm.ip_address && vm.ip_address.toLowerCase().includes(term));
    });
    
    renderVms(filtered);
}

// VM Settings Functions
function showVmSettings(vmName, vmData) {
    currentVmSettings = vmData;
    
    document.getElementById('settings-vm-name').textContent = vmName;
    document.getElementById('settings-vm-name-input').value = vmName;
    document.getElementById('settings-vm-description').value = vmData.description || '';
    
    // RAM
    const ramMB = vmData.memory || 512;
    document.getElementById('settings-ram-slider').value = ramMB;
    document.getElementById('settings-ram-input').value = ramMB;
    document.getElementById('settings-ram-value').textContent = `${ramMB} MB`;
    
    // vCPU
    const vcpus = vmData.vcpus || 1;
    document.getElementById('settings-vcpu-slider').value = vcpus;
    document.getElementById('settings-vcpu-input').value = vcpus;
    document.getElementById('settings-vcpu-value').textContent = vcpus;
    
    // Fetch and display disk info
    fetchVmDiskSize(vmName);
    
    // VRAM (default to 16 if not set)
    const vram = vmData.vram || 16;
    document.getElementById('settings-vram-slider').value = vram;
    document.getElementById('settings-vram-input').value = vram;
    document.getElementById('settings-vram-value').textContent = `${vram} MB`;
    
    // Audio
    document.getElementById('settings-audio').checked = vmData.audio !== false;
    
    // Autostart
    document.getElementById('settings-autostart').checked = vmData.autostart === true;
    
    vmSettingsModalEl.classList.remove('hidden');
}

function hideVmSettings() {
    vmSettingsModalEl.classList.add('hidden');
    currentVmSettings = null;
}

function toggleAdvancedSettings() {
    const advancedSection = document.getElementById('advanced-settings');
    const toggleBtn = document.getElementById('advanced-toggle-btn');
    const isHidden = advancedSection.classList.contains('hidden');
    
    if (isHidden) {
        advancedSection.classList.remove('hidden');
        toggleBtn.textContent = '▼ Advanced Options';
    } else {
        advancedSection.classList.add('hidden');
        toggleBtn.textContent = '▶ Advanced Options';
    }
}

function updateRamDisplay(value) {
    document.getElementById('settings-ram-value').textContent = `${value} MB`;
    document.getElementById('settings-ram-input').value = value;
}

function updateRamFromInput(value) {
    const numValue = parseInt(value) || 512;
    const clampedValue = Math.max(128, Math.min(65536, numValue));
    document.getElementById('settings-ram-slider').value = clampedValue;
    document.getElementById('settings-ram-value').textContent = `${clampedValue} MB`;
}

function updateVcpuDisplay(value) {
    document.getElementById('settings-vcpu-value').textContent = value;
    document.getElementById('settings-vcpu-input').value = value;
}

function updateVcpuFromInput(value) {
    const numValue = parseInt(value) || 1;
    const clampedValue = Math.max(1, Math.min(32, numValue));
    document.getElementById('settings-vcpu-slider').value = clampedValue;
    document.getElementById('settings-vcpu-value').textContent = clampedValue;
}

function updateDiskDisplay(value) {
    document.getElementById('settings-disk-value').textContent = `${value} GB`;
    document.getElementById('settings-disk-input').value = value;
}

function updateDiskFromInput(value) {
    const numValue = parseInt(value) || 10;
    const minSize = currentVmSettings?.current_disk_size_gb || 10;
    const clampedValue = Math.max(minSize, Math.min(1000, numValue));
    document.getElementById('settings-disk-slider').value = clampedValue;
    document.getElementById('settings-disk-value').textContent = `${clampedValue} GB`;
}

function updateVramDisplay(value) {
    document.getElementById('settings-vram-value').textContent = `${value} MB`;
    document.getElementById('settings-vram-input').value = value;
}

function updateVramFromInput(value) {
    const numValue = parseInt(value) || 16;
    const clampedValue = Math.max(8, Math.min(512, numValue));
    document.getElementById('settings-vram-slider').value = clampedValue;
    document.getElementById('settings-vram-value').textContent = `${clampedValue} MB`;
}

async function fetchVmDiskSize(vmName) {
    const result = await window.API.apiCall(`/vm/${vmName}/disk-info`);
    if (result && result.status === 'success') {
        const currentSizeGB = result.current_size_gb;
        currentVmSettings.current_disk_size_gb = currentSizeGB;
        
        document.getElementById('settings-disk-slider').min = currentSizeGB;
        document.getElementById('settings-disk-slider').value = currentSizeGB;
        document.getElementById('settings-disk-input').value = currentSizeGB;
        document.getElementById('settings-disk-value').textContent = `${currentSizeGB} GB`;
        document.getElementById('settings-disk-current').textContent = `Current: ${currentSizeGB} GB`;
    }
}

async function saveVmSettings() {
    const vmName = document.getElementById('settings-vm-name-input').value;
    const newName = vmName; // Name changes could be added here
    const description = document.getElementById('settings-vm-description').value;
    const ramMB = parseInt(document.getElementById('settings-ram-input').value);
    const vcpus = parseInt(document.getElementById('settings-vcpu-input').value);
    const diskGB = parseInt(document.getElementById('settings-disk-input').value);
    const vramMB = parseInt(document.getElementById('settings-vram-input').value);
    const audio = document.getElementById('settings-audio').checked;
    const autostart = document.getElementById('settings-autostart').checked;
    
    const settings = {
        name: newName,
        description,
        memory_mb: ramMB,
        vcpus,
        disk_size_gb: diskGB,
        vram_mb: vramMB,
        audio,
        autostart
    };
    
    const result = await window.API.apiCall(`/vm/${currentVmSettings.name}/settings`, 'PUT', settings);
    if (result && result.status === 'success') {
        window.UI.showStatus('VM settings updated successfully', 'success');
        hideVmSettings();
        fetchVms();
    }
}

// Export VM Manager functions
window.VMManager = {
    performVmAction,
    renderVms,
    fetchVms,
    filterVms,
    showVmSettings,
    hideVmSettings,
    toggleAdvancedSettings,
    updateRamDisplay,
    updateRamFromInput,
    updateVcpuDisplay,
    updateVcpuFromInput,
    updateDiskDisplay,
    updateDiskFromInput,
    updateVramDisplay,
    updateVramFromInput,
    fetchVmDiskSize,
    saveVmSettings
};

// Expose functions globally for onclick handlers
window.performVmAction = performVmAction;
window.fetchVms = fetchVms;
window.filterVms = filterVms;
window.showVmSettings = showVmSettings;
window.hideVmSettings = hideVmSettings;
window.toggleAdvancedSettings = toggleAdvancedSettings;
window.updateRamDisplay = updateRamDisplay;
window.updateRamFromInput = updateRamFromInput;
window.updateVcpuDisplay = updateVcpuDisplay;
window.updateVcpuFromInput = updateVcpuFromInput;
window.updateDiskDisplay = updateDiskDisplay;
window.updateDiskFromInput = updateDiskFromInput;
window.updateVramDisplay = updateVramDisplay;
window.updateVramFromInput = updateVramFromInput;
window.fetchVmDiskSize = fetchVmDiskSize;
window.saveVmSettings = saveVmSettings;
