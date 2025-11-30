/**
 * Starlight First-Run Wizard JavaScript
 * Handles step navigation, form validation, and API calls
 */

const wizard = {
    currentStep: 1,
    totalSteps: 6,
    adminUsername: '',

    /**
     * Initialize the wizard
     */
    async init() {
        // Load system information
        await this.loadSystemInfo();
        
        // Set up storage option toggle
        document.querySelectorAll('input[name="storage-config"]').forEach(radio => {
            radio.addEventListener('change', () => {
                const customPath = document.getElementById('custom-storage-path');
                customPath.style.display = radio.value === 'custom' ? 'block' : 'none';
            });
        });

        // Check if first-run is still needed
        await this.checkFirstRunStatus();
    },

    /**
     * Check if first-run wizard is still needed
     */
    async checkFirstRunStatus() {
        try {
            const response = await fetch('/api/firstrun/status');
            const data = await response.json();
            
            if (!data.needs_firstrun) {
                // Redirect to main interface
                window.location.href = '/';
            }
        } catch (error) {
            console.log('First-run status check failed, continuing with wizard');
        }
    },

    /**
     * Load system information for display
     */
    async loadSystemInfo() {
        try {
            const response = await fetch('/api/firstrun/system-info');
            const data = await response.json();
            
            if (data.status === 'success') {
                document.getElementById('system-hostname').textContent = data.hostname || 'starlight';
                document.getElementById('system-ip').textContent = data.ip_address || 'Unknown';
                document.getElementById('current-ip').textContent = data.ip_address || 'Unknown';
                document.getElementById('current-interface').textContent = data.interface || 'Unknown';
                document.getElementById('available-space').textContent = data.available_space || 'Unknown';
                document.getElementById('network-hostname').value = data.hostname || 'starlight';
            }
        } catch (error) {
            console.error('Failed to load system info:', error);
            document.getElementById('system-hostname').textContent = 'starlight';
            document.getElementById('system-ip').textContent = 'Unknown';
        }
    },

    /**
     * Navigate to next step
     */
    nextStep() {
        if (this.currentStep < this.totalSteps) {
            this.goToStep(this.currentStep + 1);
        }
    },

    /**
     * Navigate to previous step
     */
    prevStep() {
        if (this.currentStep > 1) {
            this.goToStep(this.currentStep - 1);
        }
    },

    /**
     * Go to a specific step
     */
    goToStep(step) {
        // Hide current step
        document.querySelector(`.step-content[data-step="${this.currentStep}"]`).classList.remove('active');
        
        // Update progress bar
        for (let i = 1; i <= this.totalSteps; i++) {
            const circle = document.querySelector(`.step-circle[data-step="${i}"]`);
            const label = circle.parentElement.querySelector('.step-label');
            
            circle.classList.remove('active', 'completed');
            label.classList.remove('active');
            
            if (i < step) {
                circle.classList.add('completed');
                circle.innerHTML = '✓';
            } else if (i === step) {
                circle.classList.add('active');
                label.classList.add('active');
                if (i < this.totalSteps) {
                    circle.innerHTML = i;
                }
            } else {
                circle.innerHTML = i === this.totalSteps ? '✓' : i;
            }
        }
        
        // Show new step
        this.currentStep = step;
        document.querySelector(`.step-content[data-step="${step}"]`).classList.add('active');
    },

    /**
     * Check password strength
     */
    checkPasswordStrength(prefix) {
        const password = document.getElementById(`${prefix}-password`).value;
        const strengthFill = document.getElementById(`${prefix}-strength-fill`);
        const strengthText = document.getElementById(`${prefix}-strength-text`);
        
        let strength = 0;
        let label = '';
        
        if (password.length >= 8) strength++;
        if (password.length >= 12) strength++;
        if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
        if (/\d/.test(password)) strength++;
        if (/[^a-zA-Z0-9]/.test(password)) strength++;
        
        strengthFill.className = 'strength-fill';
        strengthText.className = 'strength-text';
        
        if (strength <= 1) {
            strengthFill.classList.add('weak');
            strengthText.classList.add('weak');
            label = 'Weak';
        } else if (strength === 2) {
            strengthFill.classList.add('fair');
            strengthText.classList.add('fair');
            label = 'Fair';
        } else if (strength === 3) {
            strengthFill.classList.add('good');
            strengthText.classList.add('good');
            label = 'Good';
        } else {
            strengthFill.classList.add('strong');
            strengthText.classList.add('strong');
            label = 'Strong';
        }
        
        strengthText.textContent = label;
        
        // Also validate match if confirm field has value
        this.validatePasswordMatch(prefix);
        
        return strength >= 3;
    },

    /**
     * Validate password match
     */
    validatePasswordMatch(prefix) {
        const password = document.getElementById(`${prefix}-password`).value;
        const confirm = document.getElementById(`${prefix}-password-confirm`).value;
        const error = document.getElementById(`${prefix}-match-error`);
        const nextBtn = document.getElementById(`${prefix}-next-btn`);
        
        const matches = password === confirm && password.length > 0;
        const strongEnough = this.isPasswordStrong(password);
        
        error.style.display = (confirm.length > 0 && !matches) ? 'block' : 'none';
        
        if (nextBtn) {
            nextBtn.disabled = !(matches && strongEnough);
        }
        
        return matches;
    },

    /**
     * Check if password meets minimum strength requirements
     */
    isPasswordStrong(password) {
        if (password.length < 8) return false;
        
        let score = 0;
        if (/[a-z]/.test(password)) score++;
        if (/[A-Z]/.test(password)) score++;
        if (/\d/.test(password)) score++;
        if (/[^a-zA-Z0-9]/.test(password)) score++;
        
        return score >= 2;
    },

    /**
     * Validate username format
     */
    validateUsername() {
        const username = document.getElementById('admin-username').value;
        const error = document.getElementById('username-error');
        const pattern = /^[a-z_][a-z0-9_-]*$/;
        
        if (username.length === 0) {
            error.style.display = 'none';
            return false;
        }
        
        if (!pattern.test(username)) {
            error.textContent = 'Username must start with a letter and contain only lowercase letters, numbers, underscores, and hyphens';
            error.style.display = 'block';
            return false;
        }
        
        if (username.length < 2) {
            error.textContent = 'Username must be at least 2 characters';
            error.style.display = 'block';
            return false;
        }
        
        if (username === 'root') {
            error.textContent = 'Cannot use "root" as username';
            error.style.display = 'block';
            return false;
        }
        
        error.style.display = 'none';
        this.updateAdminButton();
        return true;
    },

    /**
     * Update admin button state
     */
    updateAdminButton() {
        const username = document.getElementById('admin-username').value;
        const password = document.getElementById('admin-password').value;
        const confirm = document.getElementById('admin-password-confirm').value;
        const nextBtn = document.getElementById('admin-next-btn');
        
        const usernameValid = this.validateUsernameFormat(username);
        const passwordStrong = this.isPasswordStrong(password);
        const passwordsMatch = password === confirm && password.length > 0;
        
        nextBtn.disabled = !(usernameValid && passwordStrong && passwordsMatch);
    },

    /**
     * Check username format without displaying errors
     */
    validateUsernameFormat(username) {
        const pattern = /^[a-z_][a-z0-9_-]*$/;
        return pattern.test(username) && username.length >= 2 && username !== 'root';
    },

    /**
     * Set root password via API
     */
    async setRootPassword() {
        const password = document.getElementById('root-password').value;
        const btn = document.getElementById('root-next-btn');
        
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Setting password...';
        
        try {
            const response = await fetch('/api/firstrun/set-root-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.nextStep();
            } else {
                this.showError(data.message || 'Failed to set root password');
            }
        } catch (error) {
            this.showError('Failed to set root password. Please try again.');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Continue';
        }
    },

    /**
     * Create admin user via API
     */
    async createAdmin() {
        const username = document.getElementById('admin-username').value;
        const password = document.getElementById('admin-password').value;
        const btn = document.getElementById('admin-next-btn');
        
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Creating user...';
        
        try {
            const response = await fetch('/api/firstrun/create-admin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.adminUsername = username;
                this.nextStep();
            } else {
                this.showError(data.message || 'Failed to create admin user');
            }
        } catch (error) {
            this.showError('Failed to create admin user. Please try again.');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Continue';
        }
    },

    /**
     * Set network configuration
     */
    async setNetwork() {
        const hostname = document.getElementById('network-hostname').value;
        const configType = document.querySelector('input[name="network-config"]:checked').value;
        
        if (configType === 'skip') {
            this.nextStep();
            return;
        }
        
        try {
            const response = await fetch('/api/firstrun/set-hostname', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hostname })
            });
            
            const data = await response.json();
            
            if (data.status === 'success' || data.status === 'skipped') {
                this.nextStep();
            } else {
                this.showError(data.message || 'Failed to set hostname');
            }
        } catch (error) {
            // Continue anyway - network config is optional
            console.error('Network config failed:', error);
            this.nextStep();
        }
    },

    /**
     * Set storage configuration
     */
    async setStorage() {
        const configType = document.querySelector('input[name="storage-config"]:checked').value;
        let path = '/var/lib/libvirt/images';
        
        if (configType === 'custom') {
            path = document.getElementById('storage-path').value;
            if (!path) {
                this.showError('Please enter a storage path');
                return;
            }
        }
        
        try {
            const response = await fetch('/api/firstrun/set-storage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ storage_path: path })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.showComplete();
            } else {
                this.showError(data.message || 'Failed to set storage location');
            }
        } catch (error) {
            // Continue anyway - storage config is optional
            console.error('Storage config failed:', error);
            this.showComplete();
        }
    },

    /**
     * Show completion step with countdown
     */
    showComplete() {
        // Update completion info
        const ip = document.getElementById('system-ip').textContent;
        document.getElementById('access-url').textContent = `https://${ip}/`;
        document.getElementById('created-admin').textContent = this.adminUsername || '-';
        
        this.goToStep(6);
        
        // Start countdown
        let seconds = 10;
        const countdownEl = document.getElementById('countdown-seconds');
        
        const countdown = setInterval(() => {
            seconds--;
            countdownEl.textContent = seconds;
            
            if (seconds <= 0) {
                clearInterval(countdown);
                this.finish();
            }
        }, 1000);
    },

    /**
     * Complete the wizard and redirect
     */
    async finish() {
        try {
            const response = await fetch('/api/firstrun/complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            if (data && data.status === 'success') {
                // Give nginx a moment to reload with new config
                setTimeout(() => {
                    // Force a full page reload with cache bust to ensure new nginx config is active
                    window.location.href = '/?t=' + Date.now();
                }, 1000);
            } else {
                console.error('Failed to complete firstrun:', data);
                this.showError('Failed to complete setup. Please refresh the page.');
            }
        } catch (error) {
            console.error('Failed to mark firstrun complete:', error);
            // Try to redirect anyway in case the server completed but response failed
            setTimeout(() => {
                window.location.href = '/?t=' + Date.now();
            }, 1000);
        }
    },

    /**
     * Show error message
     */
    showError(message) {
        const toast = document.getElementById('error-toast');
        const messageEl = document.getElementById('error-message');
        
        messageEl.textContent = message;
        toast.style.display = 'block';
        
        setTimeout(() => {
            toast.style.display = 'none';
        }, 5000);
    }
};

// Initialize wizard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    wizard.init();
    
    // Add input listeners for admin form
    const adminPassword = document.getElementById('admin-password');
    const adminConfirm = document.getElementById('admin-password-confirm');
    
    if (adminPassword) {
        adminPassword.addEventListener('input', () => wizard.updateAdminButton());
    }
    if (adminConfirm) {
        adminConfirm.addEventListener('input', () => {
            wizard.validatePasswordMatch('admin');
            wizard.updateAdminButton();
        });
    }
});
