/**
 * Property Valuation Form - AJAX Submission Handler
 * Handles form validation, submission, and response processing
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('valuation-form');
    const submitBtn = document.getElementById('submit-btn');
    const loading = document.getElementById('loading');
    const ajaxErrors = document.getElementById('ajax-errors');
    
    // Prevent default form submission and handle via AJAX
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Show loading state, hide previous errors
        submitBtn.style.display = 'none';
        loading.style.display = 'block';
        ajaxErrors.style.display = 'none';
        
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
            // Hide loading state
            loading.style.display = 'none';
            
            if (data.success) {
                // SUCCESS: Display success message and reset form
                ajaxErrors.innerHTML = `
                    <div class="alert alert-success">
                        <strong>Success!</strong> ${data.message}
                        <br><small>Request ID: ${data.request_id} | Status: ${data.status}</small>
                    </div>
                `;
                ajaxErrors.style.display = 'block';
                form.reset();
                
                // Auto-hide success message after 5 seconds
                setTimeout(() => {
                    ajaxErrors.style.display = 'none';
                }, 5000);
                
            } else {
                // ERROR: Display validation errors
                let errorHtml = '<div class="alert alert-danger"><strong>Please fix the following errors:</strong><ul>';
                
                // Process field-specific and general errors
                for (const field in data.errors) {
                    const fieldErrors = data.errors[field];
                    if (field === '__all__') {
                        // General form errors
                        fieldErrors.forEach(error => {
                            errorHtml += `<li>${error}</li>`;
                        });
                    } else {
                        // Field-specific errors
                        fieldErrors.forEach(error => {
                            errorHtml += `<li><strong>${field}:</strong> ${error}</li>`;
                        });
                    }
                }
                
                errorHtml += '</ul></div>';
                ajaxErrors.innerHTML = errorHtml;
                ajaxErrors.style.display = 'block';
            }
            
            // Restore submit button
            submitBtn.style.display = 'block';
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
});