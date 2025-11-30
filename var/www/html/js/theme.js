/**
 * Theme Management Module
 * Handles theme loading, switching, persistence, and CSS variable updates
 */

let currentTheme = null;
let customThemes = {};

// Initialize theme system
function initTheme() {
    // Load custom themes from localStorage first
    const customThemesData = localStorage.getItem('starlight_custom_themes');
    if (customThemesData) {
        try {
            customThemes = JSON.parse(customThemesData);
        } catch (e) {
            console.error('Error loading custom themes:', e);
        }
    }
    
    // Load saved theme or default to light
    const savedTheme = localStorage.getItem('starlight_theme') || 'default';
    const success = loadTheme(savedTheme);
    
    // If theme loading failed, fallback to default theme
    if (!success) {
        console.warn(`Failed to load theme "${savedTheme}", falling back to default`);
        localStorage.setItem('starlight_theme', 'default');
        loadTheme('default');
    }
}

function loadTheme(themeId) {
    try {
        let themeData;
        
        // Check if it's a built-in theme
        if (themeId === 'default' || themeId === 'dark') {
            // Save theme selection to localStorage for persistence
            localStorage.setItem('starlight_theme', themeId);
            
            // Load synchronously using a simple approach for built-in themes
            // We'll fetch them async in the background but apply defaults immediately
            fetch(`/themes/${themeId}.json`)
                .then(response => response.json())
                .then(data => {
                    themeData = data;
                    applyTheme(themeData);
                    currentTheme = themeData;
                })
                .catch(error => {
                    console.error('Error fetching theme:', error);
                });
            
            // Apply basic theme immediately to avoid flash
            if (themeId === 'dark') {
                document.documentElement.setAttribute('data-theme', 'dark');
            } else {
                document.documentElement.removeAttribute('data-theme');
            }
            return true;
        } else if (customThemes[themeId]) {
            // Load custom theme
            themeData = customThemes[themeId];
            applyTheme(themeData);
            currentTheme = themeData;
            localStorage.setItem('starlight_theme', themeId);
            return true;
        } else {
            console.error('Theme not found:', themeId);
            return false;
        }
    } catch (error) {
        console.error('Error loading theme:', error);
        return false;
    }
}

function applyTheme(themeData) {
    const root = document.documentElement;
    
    // Apply CSS variables
    Object.keys(themeData.variables).forEach(key => {
        root.style.setProperty(`--${key}`, themeData.variables[key]);
    });
    
    // Set data-theme attribute for dark theme compatibility
    if (themeData.id === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
}

function getCurrentTheme() {
    return currentTheme;
}

function importCustomTheme(jsonData) {
    try {
        const themeData = typeof jsonData === 'string' ? JSON.parse(jsonData) : jsonData;
        
        // Validate theme structure
        if (!themeData.id || !themeData.name || !themeData.variables) {
            throw new Error('Invalid theme structure');
        }
        
        // Don't allow overwriting built-in themes
        if (themeData.id === 'default' || themeData.id === 'dark') {
            throw new Error('Cannot import theme with reserved ID (default or dark)');
        }
        
        // Save to custom themes
        customThemes[themeData.id] = themeData;
        localStorage.setItem('starlight_custom_themes', JSON.stringify(customThemes));
        
        return true;
    } catch (error) {
        console.error('Error importing theme:', error);
        return false;
    }
}

function deleteCustomTheme(themeId) {
    // Don't allow deleting built-in themes
    if (themeId === 'default' || themeId === 'dark') {
        window.UI.showStatus('Cannot delete built-in themes', 'error');
        return false;
    }
    
    if (!customThemes[themeId]) {
        window.UI.showStatus('Theme not found', 'error');
        return false;
    }
    
    // If the theme being deleted is currently active, switch to default
    const currentThemeId = localStorage.getItem('starlight_theme');
    if (currentThemeId === themeId) {
        loadTheme('default');
    }
    
    // Remove the theme
    delete customThemes[themeId];
    localStorage.setItem('starlight_custom_themes', JSON.stringify(customThemes));
    
    // Update the theme selector
    updateThemeSelector();
    
    window.UI.showStatus(`Theme "${themeId}" deleted`, 'success');
    return true;
}

function getCustomThemes() {
    return Object.keys(customThemes).map(id => ({
        id,
        name: customThemes[id].name
    }));
}

function exportCurrentTheme() {
    if (!currentTheme) {
        console.error('No theme currently loaded');
        return null;
    }
    
    return JSON.stringify(currentTheme, null, 2);
}

function getAvailableThemes() {
    const themes = [
        { id: 'default', name: 'Light' },
        { id: 'dark', name: 'Dark' }
    ];
    
    // Add custom themes
    Object.keys(customThemes).forEach(id => {
        themes.push({ id, name: customThemes[id].name });
    });
    
    return themes;
}

// Legacy dark mode toggle for backwards compatibility
function toggleDarkMode() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    loadTheme(isDark ? 'default' : 'dark');
}

function initDarkMode() {
    // This is called by old code - just initialize theme system
    initTheme();
}

function updateThemeSelector() {
    const selector = document.getElementById('theme-selector');
    if (!selector) return;
    
    // Clear existing options
    selector.innerHTML = '';
    
    // Add built-in themes
    const option1 = document.createElement('option');
    option1.value = 'default';
    option1.textContent = 'Light';
    selector.appendChild(option1);
    
    const option2 = document.createElement('option');
    option2.value = 'dark';
    option2.textContent = 'Dark';
    selector.appendChild(option2);
    
    // Add custom themes
    Object.keys(customThemes).forEach(id => {
        const option = document.createElement('option');
        option.value = id;
        option.textContent = customThemes[id].name;
        selector.appendChild(option);
    });
    
    // Set current selection
    const savedTheme = localStorage.getItem('starlight_theme') || 'default';
    selector.value = savedTheme;
    
    // Also update the custom themes list
    renderCustomThemesList();
}

function renderCustomThemesList() {
    const listContainer = document.getElementById('custom-themes-list');
    if (!listContainer) return;
    
    const themes = getCustomThemes();
    
    if (themes.length === 0) {
        listContainer.innerHTML = '<p class="text-sm" style="color: var(--text-tertiary);">No custom themes installed</p>';
        return;
    }
    
    listContainer.innerHTML = '';
    themes.forEach(theme => {
        const themeItem = document.createElement('div');
        themeItem.className = 'flex items-center justify-between p-2 rounded border';
        themeItem.style.borderColor = 'var(--border-color)';
        themeItem.innerHTML = `
            <span style="color: var(--text-primary);">${theme.name}</span>
            <button onclick="window.ThemeManager.deleteCustomTheme('${theme.id}')" 
                    class="px-2 py-1 text-xs bg-red-500 hover:bg-red-600 text-white rounded transition">
                Delete
            </button>
        `;
        listContainer.appendChild(themeItem);
    });
}

// Theme import/export handlers for Settings page
function handleThemeImport(inputElement) {
    const file = inputElement.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const themeData = JSON.parse(e.target.result);
            if (importCustomTheme(themeData)) {
                window.UI.showStatus(`Theme "${themeData.name}" imported successfully!`, 'success');
                // Update theme selector with new theme
                updateThemeSelector();
                // Apply the newly imported theme
                loadTheme(themeData.id);
            } else {
                window.UI.showStatus('Failed to import theme. Please check the file format.', 'error');
            }
        } catch (error) {
            console.error('Theme import error:', error);
            window.UI.showStatus('Invalid theme file format', 'error');
        }
    };
    reader.readAsText(file);
    // Reset input for re-importing
    inputElement.value = '';
}

function handleThemeExport() {
    const themeJson = exportCurrentTheme();
    if (!themeJson) {
        window.UI.showStatus('No theme to export', 'error');
        return;
    }
    
    const blob = new Blob([themeJson], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentTheme.id}-theme.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    window.UI.showStatus('Theme exported successfully', 'success');
}

// Export theme functions
window.ThemeManager = {
    initTheme,
    loadTheme,
    applyTheme,
    getCurrentTheme,
    importCustomTheme,
    exportCurrentTheme,
    deleteCustomTheme,
    getCustomThemes,
    getAvailableThemes,
    toggleDarkMode,
    initDarkMode,
    updateThemeSelector
};

// Expose individual functions to global scope for onclick handlers
window.toggleDarkMode = toggleDarkMode;
window.initDarkMode = initDarkMode;
window.handleThemeImport = handleThemeImport;
window.handleThemeExport = handleThemeExport;
