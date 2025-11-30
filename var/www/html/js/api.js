/**
 * API Communication Module
 * Handles all API calls and error handling
 */

async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: { 'Content-Type': 'application/json' },
        };
        
        // Add authentication header if token is available
        const authToken = window.AUTH.getAuthToken();
        if (authToken && endpoint !== '/auth/login') {
            options.headers['Authorization'] = `Bearer ${authToken}`;
        }
        
        if (data) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(`${window.CONFIG.API_BASE}${endpoint}`, options);
        
        // Handle authentication errors
        if (response.status === 401) {
            console.log('Authentication required - showing login');
            window.AUTH.showLoginModal();
            return null;
        }
        
        // Try to parse JSON response
        let result;
        try {
            const text = await response.text();
            if (text) {
                result = JSON.parse(text);
            } else {
                result = {};
            }
        } catch (parseError) {
            console.error('JSON parse error:', parseError);
            if (!response.ok) {
                // Don't show error for 404 on optional endpoints like download-progress
                if (response.status !== 404 || !endpoint.includes('download-progress')) {
                    window.UI.showStatus(`API Error: Server returned non-JSON response (${response.status})`, 'error');
                }
                return null;
            }
            result = {};
        }

        if (!response.ok) {
            // Don't show error for 404 on optional endpoints
            if (response.status !== 404 || !endpoint.includes('download-progress')) {
                window.UI.showStatus(`API Error: ${result.message || 'An unknown error occurred'}`, 'error');
            }
            return null;
        }
        return result;
    } catch (error) {
        console.error('Network or Parse Error:', error);
        window.UI.showStatus(`Network Error: Could not reach the API server. (${error.message})`, 'error');
        return null;
    }
}

// Export API functions
window.API = {
    apiCall
};
