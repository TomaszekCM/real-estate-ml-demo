/**
 * Property Valuation Form - AJAX Submission Handler with Status Polling
 * Handles form validation, submission, and response processing with real-time status updates
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('valuation-form');
    const submitBtn = document.getElementById('submit-btn');
    const loading = document.getElementById('loading');
    const ajaxErrors = document.getElementById('ajax-errors');
    const statusContainer = document.getElementById('status-container');
    
    let pollingInterval = null;  // To track polling timer
    
    // Prevent default form submission and handle via AJAX
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Clear any existing polling
        clearPolling();
        
        // Show loading state, hide previous errors
        submitBtn.style.display = 'none';
        loading.style.display = 'block';
        ajaxErrors.style.display = 'none';
        if (statusContainer) statusContainer.style.display = 'none';
        
        // Collect form data for JSON submission
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        // Submit form via AJAX with JSON payload
        fetch(form.action || window.location.href, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            // Hide initial loading state
            loading.style.display = 'none';
            
            if (data.success) {
                // SUCCESS: Start polling for status updates
                const requestId = data.request_id;
                startStatusPolling(requestId);
                
            } else {
                // ERROR: Display validation errors
                displayErrors(data.errors);
                submitBtn.style.display = 'block';
            }
        })
        .catch(error => {
            // NETWORK ERROR: Handle connection issues
            loading.style.display = 'none';
            submitBtn.style.display = 'block';
            
            ajaxErrors.innerHTML = `
                <div class="alert alert-danger">
                    <strong>Error:</strong> Something went wrong. Please try again.
                    <br><small>${error.message}</small>
                </div>
            `;
            ajaxErrors.style.display = 'block';
        });
    });
    
    /**
     * Start polling for valuation status updates
     */
    function startStatusPolling(requestId) {
        // Show status container
        if (statusContainer) {
            statusContainer.innerHTML = `
                <div class="alert alert-info">
                    <div class="d-flex align-items-center">
                        <div class="spinner-border spinner-border-sm me-3" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <div>
                            <strong>Processing your valuation request...</strong><br>
                            <small class="text-muted">Request ID: ${requestId} | Status: PENDING</small>
                        </div>
                    </div>
                </div>
            `;
            statusContainer.style.display = 'block';
        }
        
        // Start polling every 1 second
        pollingInterval = setInterval(() => {
            pollValuationStatus(requestId);
        }, 1000);
        
        // Also do initial poll immediately
        pollValuationStatus(requestId);
    }
    
    /**
     * Poll the status endpoint for updates
     */
    function pollValuationStatus(requestId) {
        fetch(`/api/valuation/${requestId}/status/`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                // Error fetching status
                clearPolling();
                displayStatusError(data.error);
                return;
            }
            
            updateStatusDisplay(data);
            
            // Stop polling when done (success or failure)
            if (data.status === 'DONE' || data.status === 'FAILED') {
                clearPolling();
                
                if (data.status === 'DONE' && data.result) {
                    displayValuationResult(data);
                } else {
                    displayStatusError('Valuation processing failed');
                }
                
                // Show submit button again for new requests
                setTimeout(() => {
                    submitBtn.style.display = 'block';
                    form.reset();
                }, 2000);
            }
        })
        .catch(error => {
            console.error('Polling error:', error);
            // Continue polling on network errors (transient issues)
        });
    }
    
    /**
     * Update the status display with current information
     */
    function updateStatusDisplay(data) {
        if (!statusContainer) return;
        
        let statusText = data.status;
        let statusClass = 'alert-info';
        let showSpinner = true;
        
        switch (data.status) {
            case 'PENDING':
                statusText = 'Waiting to start processing...';
                break;
            case 'PROCESSING':
                statusText = 'Analyzing your property details...';
                break;
            case 'DONE':
                statusText = 'Processing completed!';
                statusClass = 'alert-success';
                showSpinner = false;
                break;
            case 'FAILED':
                statusText = 'Processing failed';
                statusClass = 'alert-danger';
                showSpinner = false;
                break;
        }
        
        const spinnerHtml = showSpinner ? `
            <div class="spinner-border spinner-border-sm me-3" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        ` : '';
        
        statusContainer.innerHTML = `
            <div class="alert ${statusClass}">
                <div class="d-flex align-items-center">
                    ${spinnerHtml}
                    <div>
                        <strong>${statusText}</strong><br>
                        <small class="text-muted">Request ID: ${data.request_id} | Status: ${data.status}</small>
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * Display the final valuation result
     */
    function displayValuationResult(data) {
        if (!statusContainer) return;
        
        const result = data.result;
        const price = new Intl.NumberFormat('pl-PL', {
            style: 'currency',
            currency: 'PLN'
        }).format(result.estimated_price);
        
        const pricePerSqm = new Intl.NumberFormat('pl-PL', {
            style: 'currency', 
            currency: 'PLN'
        }).format(result.price_per_sqm);
        
        statusContainer.innerHTML = `
            <div class="alert alert-success">
                <h5 class="alert-heading">
                    <i class="bi bi-check-circle"></i> Valuation Complete!
                </h5>
                <hr>
                <div class="row">
                    <div class="col-md-6">
                        <h6>Estimated Property Value:</h6>
                        <h4 class="text-success">${price}</h4>
                    </div>
                    <div class="col-md-6">
                        <h6>Price per m²:</h6>
                        <h4 class="text-info">${pricePerSqm}</h4>
                    </div>
                </div>
                <hr>
                <small class="text-muted">
                    Model version: ${result.model_version} | 
                    Generated: ${new Date(result.created_at).toLocaleString()}
                </small>
            </div>
        `;
    }
    
    /**
     * Display status error
     */
    function displayStatusError(errorMessage) {
        if (statusContainer) {
            statusContainer.innerHTML = `
                <div class="alert alert-danger">
                    <strong>Error:</strong> ${errorMessage}
                </div>
            `;
        }
    }
    
    /**
     * Display form validation errors
     */
    function displayErrors(errors) {
        let errorHtml = '<div class="alert alert-danger"><strong>Please fix the following errors:</strong><ul>';
        
        for (const field in errors) {
            const fieldErrors = errors[field];
            if (field === '__all__') {
                fieldErrors.forEach(error => {
                    errorHtml += `<li>${error}</li>`;
                });
            } else {
                fieldErrors.forEach(error => {
                    errorHtml += `<li><strong>${field}:</strong> ${error}</li>`;
                });
            }
        }
        
        errorHtml += '</ul></div>';
        ajaxErrors.innerHTML = errorHtml;
        ajaxErrors.style.display = 'block';
    }
    
    /**
     * Clear polling interval
     */
    function clearPolling() {
        if (pollingInterval) {
            clearInterval(pollingInterval);
            pollingInterval = null;
        }
    }
    
    // Clean up polling when leaving page
    window.addEventListener('beforeunload', clearPolling);
});