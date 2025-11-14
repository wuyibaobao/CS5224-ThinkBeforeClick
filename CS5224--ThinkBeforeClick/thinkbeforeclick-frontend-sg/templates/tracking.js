// Phishing Simulation Tracking Script
// This script tracks email opens and scam clicks for ThinkBeforeClick platform

(function() {
    // API Configuration - Replace with your actual API Gateway URL
    const API_ENDPOINT = 'https://3ofmk3jge7.execute-api.ap-southeast-1.amazonaws.com/prod';
    
    // Get tracking ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const trackingId = urlParams.get('tid');

    // Track email open on page load
    if (trackingId) {
        // Call backend API to track email open
        trackEmailOpenAPI(trackingId);
        
        // Also update localStorage for demo mode compatibility
        updateLocalStorageOpen(trackingId);
    }

    // Function to call API for tracking email open
    async function trackEmailOpenAPI(trackingId) {
        try {
            const response = await fetch(`${API_ENDPOINT}/track-open/${trackingId}`, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ Email open tracked:', result);
            } else {
                console.warn('⚠️ Failed to track email open via API, using localStorage fallback');
            }
        } catch (error) {
            console.error('❌ Error tracking email open:', error);
            console.log('Falling back to localStorage tracking');
        }
    }

    // Function to update localStorage (fallback for demo mode)
    function updateLocalStorageOpen(trackingId) {
        try {
            const emailTracking = JSON.parse(localStorage.getItem('emailTracking') || '[]');
            const tracking = emailTracking.find(t => t.trackingId === trackingId);
            if (tracking && !tracking.opened) {
                tracking.opened = true;
                tracking.openedAt = new Date().toISOString();
                
                const employees = JSON.parse(localStorage.getItem('employees') || '[]');
                const employee = employees.find(emp => emp.id === tracking.employeeId);
                if (employee) {
                    employee.openedEmails++;
                    localStorage.setItem('employees', JSON.stringify(employees));
                }
                
                localStorage.setItem('emailTracking', JSON.stringify(emailTracking));
            }
        } catch (e) {
            console.error('LocalStorage tracking error:', e);
        }
    }

    // Function to update localStorage for scam clicks (fallback)
    function updateLocalStorageClick(trackingId, scamType) {
        try {
            const emailTracking = JSON.parse(localStorage.getItem('emailTracking') || '[]');
            const tracking = emailTracking.find(t => t.trackingId === trackingId);
            if (tracking) {
                if (!tracking.scamClicks) tracking.scamClicks = [];
                tracking.scamClicks.push({
                    scamType: scamType,
                    clickedAt: new Date().toISOString()
                });
                
                const employees = JSON.parse(localStorage.getItem('employees') || '[]');
                const employee = employees.find(emp => emp.id === tracking.employeeId);
                if (employee) {
                    employee.clickedScams++;
                    localStorage.setItem('employees', JSON.stringify(employees));
                }
                
                localStorage.setItem('emailTracking', JSON.stringify(emailTracking));
            }
        } catch (e) {
            console.error('LocalStorage click tracking error:', e);
        }
    }

    // Global function to handle scam clicks
    window.handleScamClick = async function(scamType, callback) {
        // Track scam click via API
        if (trackingId) {
            try {
                const response = await fetch(`${API_ENDPOINT}/track-click`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        trackingId: trackingId,
                        scamType: scamType
                    })
                });
                
                if (response.ok) {
                    const result = await response.json();
                    console.log('✅ Scam click tracked:', result);
                } else {
                    console.warn('⚠️ Failed to track scam click via API, using localStorage fallback');
                }
            } catch (error) {
                console.error('❌ Error tracking scam click:', error);
                console.log('Falling back to localStorage tracking');
            }
            
            // Also update localStorage for demo mode compatibility
            updateLocalStorageClick(trackingId, scamType);
        }
        
        // Execute callback if provided (e.g., show warning modal)
        if (callback && typeof callback === 'function') {
            callback();
        }
    };

    console.log('ThinkBeforeClick tracking initialized. Tracking ID:', trackingId || 'Not provided');
    console.log('API Endpoint:', API_ENDPOINT);
})();

