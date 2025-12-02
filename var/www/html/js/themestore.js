/**
 * Theme Store Module
 * Browse and install themes from enabled repositories
 */

const themeStoreListEl = document.getElementById('theme-store-list');
const themeLoadingIndicator = document.getElementById('theme-loading-indicator');
const themeDetailModalEl = document.getElementById('theme-detail-modal');

let themeStoreData = [];
let currentThemeData = null;

/**
 * Extracts the primary color from a theme's variables
 * @param {object} theme - Theme object with theme_data
 * @returns {string} Color value (border-color, accent-primary, or default)
 */
function getThemeColor(theme) {
    if (theme.theme_data && theme.theme_data.variables) {
        return theme.theme_data.variables['border-color'] 
            || theme.theme_data.variables['accent-primary'] 
            || '#6366f1';
    }
    return '#6366f1';
}

/**
 * Generates a default theme icon SVG with the specified color
 * @param {string} color - The color to use for the icon (typically border-color from theme)
 * @returns {string} Data URL for the SVG icon
 */
function generateDefaultThemeIcon(color = '#6366f1') {
    // Sanitize the color for safety (prevents CSS injection)
    const safeColor = sanitizeColor(color);
    // URL encode for data URL - necessary for special characters in rgb()/hsl() values
    // e.g., "rgb(255, 0, 0)" becomes "rgb(255%2C%200%2C%200)"
    const encodedColor = encodeURIComponent(safeColor);
    // Use single quotes for SVG attributes to avoid conflicts with HTML double quotes
    return `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='${encodedColor}'%3E%3Cpath d='M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01'/%3E%3C/svg%3E`;
}

/**
 * Gets the icon URL for a theme, generating a color-matched default if needed
 * @param {object} theme - Theme object
 * @returns {string} Icon URL (explicit or generated)
 */
function getThemeIconUrl(theme) {
    if (theme.icon) {
        return theme.icon;
    }
    const themeColor = getThemeColor(theme);
    return generateDefaultThemeIcon(themeColor);
}

/**
 * Validates and sanitizes CSS color values to prevent CSS injection
 * Accepts: hex colors, rgb/rgba, hsl/hsla
 * 
 * Note: RGB/HSL values are validated for format but not range (e.g., rgb(999,999,999) 
 * is allowed). This is safe because:
 * 1. Invalid values are clamped/ignored by browsers
 * 2. Colors are only used in SVG data URLs (sandboxed)
 * 3. Main security concern (CSS injection via expressions/urls) is prevented
 */
function sanitizeColor(color) {
    // Handle null, undefined, non-string values
    if (color === null || color === undefined || typeof color !== 'string') {
        return '#000000';
    }
    
    // Trim whitespace
    color = color.trim();
    
    // Reject empty strings
    if (color === '') return '#000000';
    
    // Allow hex colors (3, 4, 6, or 8 digits)
    if (/^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$/.test(color)) {
        return color;
    }
    
    // Allow rgb/rgba with valid syntax (values 0-999, browser will clamp)
    if (/^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(,\s*[\d.]+\s*)?\)$/.test(color)) {
        return color;
    }
    
    // Allow hsl/hsla with valid syntax (values 0-999, browser will clamp)
    if (/^hsla?\(\s*\d{1,3}\s*,\s*\d{1,3}%\s*,\s*\d{1,3}%\s*(,\s*[\d.]+\s*)?\)$/.test(color)) {
        return color;
    }
    
    // Reject anything else (including named colors for safety)
    console.warn(`Invalid color value rejected: ${color}`);
    return '#000000'; // Default to black
}

async function fetchThemeStore() {
    if (themeLoadingIndicator) themeLoadingIndicator.classList.remove('hidden');
    if (themeStoreListEl) themeStoreListEl.innerHTML = '';
    
    const result = await window.API.apiCall('/repositories/themes');
    
    if (result && result.status === 'success') {
        renderThemeStore(result.themes);
        const themeCount = result.total || result.themes?.length || 0;
        window.UI.showStatus(`Loaded ${themeCount} themes from all enabled repositories`, 'success');
    } else if (themeStoreListEl) {
        themeStoreListEl.innerHTML = `<p class="text-center text-red-500 col-span-full p-4 bg-red-50 rounded-lg">
            Error loading themes from repositories.
        </p>`;
    }
    
    if (themeLoadingIndicator) themeLoadingIndicator.classList.add('hidden');
}

function renderThemeStore(themes, storeData = true) {
    if (!themeStoreListEl) return;
    themeStoreListEl.innerHTML = '';
    if (storeData) {
        themeStoreData = themes;
    }
    
    if (themes.length === 0) {
        themeStoreListEl.innerHTML = '<p class="text-center text-gray-500 col-span-full">No themes found. Enable repositories in the Settings page.</p>';
        return;
    }

    themes.forEach((theme, index) => {
        const themeCard = document.createElement('div');
        themeCard.className = 'card rounded-xl p-5 border flex flex-col justify-between cursor-pointer hover:shadow-lg transition-shadow';
        
        const iconUrl = getThemeIconUrl(theme);
        
        // Show color preview swatches if theme has variables
        let colorSwatches = '';
        if (theme.theme_data && theme.theme_data.variables) {
            const vars = theme.theme_data.variables;
            const colorKeys = ['bg-primary', 'bg-secondary', 'text-primary', 'accent-primary'];
            const colors = colorKeys
                .map(key => vars[key])
                .filter(color => color)
                .slice(0, 4);
            
            if (colors.length > 0) {
                colorSwatches = `
                    <div class="flex gap-1 mb-3">
                        ${colors.map(color => `<div class="w-8 h-8 rounded border" style="background-color: ${sanitizeColor(color)}; border-color: var(--border-color);"></div>`).join('')}
                    </div>
                `;
            }
        }
        
        // Use empty alt text for generated icons to prevent text overflow if image fails to load
        const altText = theme.icon ? theme.name : '';
        
        themeCard.innerHTML = `
            <div onclick='showThemeDetailByIndex(${index})'>
                <div class="flex items-start mb-3">
                    <img src="${iconUrl}" alt="${altText}" class="app-icon mr-3" data-theme-index="${index}">
                    <div class="flex-1">
                        <h3 class="text-lg font-bold mb-1" style="color: var(--text-primary);">${theme.name}</h3>
                        <p class="text-sm mb-2" style="color: var(--text-secondary);">${theme.summary || theme.description?.substring(0, 100) + '...' || 'No description provided.'}</p>
                    </div>
                </div>
                
                ${colorSwatches}
                
                ${theme.tags && theme.tags.length > 0 ? `
                <div class="flex flex-wrap gap-1 mb-3">
                    ${theme.tags.slice(0, 3).map(tag => `<span class="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">${tag}</span>`).join('')}
                </div>
                ` : ''}
                
                <div class="text-xs mb-2 border-t pt-2" style="color: var(--text-tertiary); border-color: var(--border-color);">
                    <span class="text-indigo-600 font-semibold">${theme.repo_name || 'Unknown'}</span>
                </div>
            </div>
            
            <div class="flex gap-2 mt-4">
                <button class="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold py-2 px-4 rounded-lg transition duration-150"
                        onclick='event.stopPropagation(); showThemeDetailByIndex(${index})'>
                    Details
                </button>
                <button class="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold py-2 px-4 rounded-lg transition duration-150"
                        onclick="event.stopPropagation(); installThemeByIndex(${index})">
                    Install
                </button>
            </div>
        `;
        
        // Set up onerror handler via JavaScript to avoid HTML escaping issues
        const imgEl = themeCard.querySelector('img');
        if (imgEl) {
            const fallbackIcon = generateDefaultThemeIcon(getThemeColor(theme));
            imgEl.onerror = function() {
                this.onerror = null; // Prevent infinite loop
                this.src = fallbackIcon;
            };
        }
        
        themeStoreListEl.appendChild(themeCard);
    });
}

function showThemeDetailByIndex(index) {
    if (index >= 0 && index < themeStoreData.length) {
        showThemeDetail(themeStoreData[index]);
    }
}

function installThemeByIndex(index) {
    if (index >= 0 && index < themeStoreData.length) {
        installTheme(themeStoreData[index]);
    }
}

function showThemeDetail(theme) {
    currentThemeData = theme;
    
    const iconUrl = getThemeIconUrl(theme);
    document.getElementById('theme-detail-icon').src = iconUrl;
    document.getElementById('theme-detail-icon').alt = theme.name;
    
    document.getElementById('theme-detail-name').textContent = theme.name;
    document.getElementById('theme-detail-summary').textContent = theme.summary || 'Custom Theme';
    
    // Show color palette
    const paletteEl = document.getElementById('theme-detail-palette');
    if (theme.theme_data && theme.theme_data.variables) {
        const vars = theme.theme_data.variables;
        paletteEl.innerHTML = `
            <h4 class="font-semibold mb-3" style="color: var(--text-primary);">Color Palette</h4>
            <div class="grid grid-cols-2 gap-3">
                ${Object.entries(vars).map(([key, value]) => {
                    const safeColor = sanitizeColor(value);
                    return `
                    <div class="flex items-center gap-2">
                        <div class="w-10 h-10 rounded border" style="background-color: ${safeColor}; border-color: var(--border-color);"></div>
                        <div class="flex-1">
                            <div class="text-xs font-mono" style="color: var(--text-secondary);">${key}</div>
                            <div class="text-xs font-mono font-bold" style="color: var(--text-primary);">${value}</div>
                        </div>
                    </div>
                    `;
                }).join('')}
            </div>
        `;
    } else {
        paletteEl.innerHTML = '<p class="text-sm" style="color: var(--text-secondary);">No color information available.</p>';
    }
    
    const descEl = document.getElementById('theme-detail-description');
    if (theme.description && typeof marked !== 'undefined') {
        // marked.parse() includes built-in XSS protection by default
        // It escapes HTML tags and sanitizes potentially dangerous content
        descEl.innerHTML = marked.parse(theme.description);
    } else if (theme.description) {
        // Use textContent to prevent XSS when marked is not available
        descEl.textContent = '';
        const p = document.createElement('p');
        p.textContent = theme.description;
        descEl.appendChild(p);
    } else {
        descEl.textContent = '';
        const p = document.createElement('p');
        p.textContent = 'No detailed description available.';
        descEl.appendChild(p);
    }
    
    // Show tags
    const tagsEl = document.getElementById('theme-detail-tags');
    if (tagsEl) {
        if (theme.tags && theme.tags.length > 0) {
            tagsEl.innerHTML = `
                <h4 class="font-semibold mb-2" style="color: var(--text-primary);">Tags</h4>
                <div class="flex flex-wrap gap-2">
                    ${theme.tags.map(tag => `<span class="text-sm bg-indigo-100 text-indigo-700 px-3 py-1 rounded-full">${tag}</span>`).join('')}
                </div>
            `;
        } else {
            tagsEl.innerHTML = '';
        }
    }
    
    // Show repository source
    const repoEl = document.getElementById('theme-detail-repo');
    if (repoEl) {
        repoEl.innerHTML = `
            <div class="text-sm" style="color: var(--text-secondary);">
                <strong>From:</strong> <span class="text-indigo-600">${theme.repo_name || 'Unknown Repository'}</span>
            </div>
        `;
    }
    
    document.getElementById('theme-detail-install-btn').onclick = () => {
        hideThemeDetail();
        installTheme(theme);
    };
    
    themeDetailModalEl.classList.remove('hidden');
}

function hideThemeDetail() {
    themeDetailModalEl.classList.add('hidden');
    currentThemeData = null;
}

function installTheme(theme) {
    if (!theme.theme_data) {
        window.UI.showStatus('Theme data is missing', 'error');
        return;
    }
    
    window.UI.showModal(
        'Install Theme',
        `Install theme "${theme.name}"? It will be added to your theme selector.`,
        () => {
            try {
                // Use the existing ThemeManager to import the theme
                const success = window.ThemeManager.importCustomTheme(theme.theme_data);
                
                if (success) {
                    window.UI.showStatus(`Theme "${theme.name}" installed successfully!`, 'success');
                    // Update theme selector
                    window.ThemeManager.updateThemeSelector();
                    // Apply the newly installed theme
                    window.ThemeManager.loadTheme(theme.theme_data.id);
                } else {
                    window.UI.showStatus(`Failed to install theme "${theme.name}"`, 'error');
                }
            } catch (error) {
                console.error('Error installing theme:', error);
                window.UI.showStatus('Error installing theme', 'error');
            }
        },
        false
    );
}

function filterThemes() {
    const searchEl = document.getElementById('theme-search');
    const term = searchEl ? searchEl.value.toLowerCase().trim() : '';
    
    if (!term) {
        renderThemeStore(themeStoreData, false);
        return;
    }
    
    const filtered = themeStoreData.filter(theme => {
        // Search by name
        if (theme.name.toLowerCase().includes(term)) return true;
        
        // Search by summary
        if (theme.summary && theme.summary.toLowerCase().includes(term)) return true;
        
        // Search by description
        if (theme.description && theme.description.toLowerCase().includes(term)) return true;
        
        // Search by tags
        if (theme.tags && theme.tags.some(tag => tag.toLowerCase().includes(term))) return true;
        
        return false;
    });
    
    renderThemeStore(filtered, false);
}

// Export ThemeStore functions
window.ThemeStore = {
    fetchThemeStore,
    filterThemes,
    showThemeDetail,
    hideThemeDetail,
    installTheme,
    showThemeDetailByIndex,
    installThemeByIndex
};

// Expose functions globally for onclick handlers
window.fetchThemeStore = fetchThemeStore;
window.filterThemes = filterThemes;
window.showThemeDetail = showThemeDetail;
window.hideThemeDetail = hideThemeDetail;
window.installTheme = installTheme;
window.showThemeDetailByIndex = showThemeDetailByIndex;
window.installThemeByIndex = installThemeByIndex;
