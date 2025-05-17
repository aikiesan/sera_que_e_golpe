document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('tutorial-modal');
    const openButton = document.getElementById('open-tutorial');
    const closeButton = modal.querySelector('.close-button');

    function openModal() {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden'; // Prevent scrolling when modal is open
        
        // Set focus on close button for accessibility
        closeButton.focus();
        
        // Trap focus within modal
        modal.addEventListener('keydown', trapFocus);
    }

    function closeModal() {
        modal.style.display = 'none';
        document.body.style.overflow = ''; // Restore scrolling
        
        // Remove focus trap
        modal.removeEventListener('keydown', trapFocus);
        
        // Return focus to open button
        openButton.focus();
    }

    function trapFocus(e) {
        // Get all focusable elements in modal
        const focusableElements = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const firstFocusable = focusableElements[0];
        const lastFocusable = focusableElements[focusableElements.length - 1];

        // If shift + tab pressed and focus is on first element, move to last
        if (e.key === 'Tab' && e.shiftKey) {
            if (document.activeElement === firstFocusable) {
                e.preventDefault();
                lastFocusable.focus();
            }
        }
        // If tab pressed and focus is on last element, move to first
        else if (e.key === 'Tab' && !e.shiftKey) {
            if (document.activeElement === lastFocusable) {
                e.preventDefault();
                firstFocusable.focus();
            }
        }
        // Close modal on escape
        else if (e.key === 'Escape') {
            closeModal();
        }
    }

    // Event listeners
    openButton.addEventListener('click', openModal);
    closeButton.addEventListener('click', closeModal);
    
    // Close modal when clicking outside
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeModal();
        }
    });
}); 