// Dashboard JavaScript - Enhanced Version
document.addEventListener('DOMContentLoaded', function() {
    initDashboard();
    setupEventListeners();
    updateCharts();
});

function initDashboard() {
    // Initialize components
    initSidebar();
    initSearch();
    initDatePickers();
    updateFinancialHealth();
}

function initSidebar() {
    const menuToggle = document.querySelector('.menu-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', () => {
            sidebar.classList.toggle('active');
            menuToggle.innerHTML = sidebar.classList.contains('active') ? 
                '<i class="fas fa-times"></i>' : '<i class="fas fa-bars"></i>';
        });
        
        // Close sidebar on mobile when clicking outside
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 992 && 
                !sidebar.contains(e.target) && 
                !menuToggle.contains(e.target) &&
                sidebar.classList.contains('active')) {
                sidebar.classList.remove('active');
                menuToggle.innerHTML = '<i class="fas fa-bars"></i>';
            }
        });
    }
    
    // Highlight active nav item
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar-nav a').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
}

function initSearch() {
    const searchInput = document.getElementById('search-expenses');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const term = e.target.value.toLowerCase();
            document.querySelectorAll('.expense-item').forEach(item => {
                const text = item.textContent.toLowerCase();
                item.style.display = text.includes(term) ? 'flex' : 'none';
            });
        });
    }
}

function initDatePickers() {
    // Set today's date in date inputs
    const today = new Date().toISOString().split('T')[0];
    document.querySelectorAll('input[type="date"]').forEach(input => {
        if (!input.value) input.value = today;
    });
}

function updateFinancialHealth() {
    const scoreElement = document.querySelector('.score-progress');
    if (scoreElement) {
        const score = parseInt(scoreElement.dataset.score || '0');
        const progress = document.querySelector('.score-progress');
        const value = document.querySelector('.score-value');
        
        if (progress && value) {
            // Animate circle
            const circumference = 2 * Math.PI * 80;
            const offset = circumference - (score / 100) * circumference;
            progress.style.strokeDasharray = `${circumference} ${circumference}`;
            progress.style.strokeDashoffset = offset;
            
            // Animate counter
            let current = 0;
            const increment = score / 50;
            const timer = setInterval(() => {
                current += increment;
                if (current >= score) {
                    current = score;
                    clearInterval(timer);
                }
                value.textContent = Math.round(current);
            }, 20);
        }
    }
}

function updateCharts() {
    // This function will be implemented based on available chart data
    console.log('Charts would be updated here');
}

function setupEventListeners() {
    // Add expense form
    const addExpenseForm = document.getElementById('addExpenseForm');
    if (addExpenseForm) {
        addExpenseForm.addEventListener('submit', function(e) {
            e.preventDefault();
            submitExpenseForm(this);
        });
    }
    
    // Category prediction on description input
    const descriptionInput = document.querySelector('input[name="description"]');
    if (descriptionInput) {
        descriptionInput.addEventListener('input', function(e) {
            if (e.target.value.length >= 3) {
                predictCategory(e.target.value);
            }
        });
    }
    
    // Receipt upload
    const receiptUpload = document.getElementById('receiptUpload');
    if (receiptUpload) {
        receiptUpload.addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                processReceipt(e.target.files[0]);
            }
        });
    }
}

function predictCategory(text) {
    fetch('/predict_category', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: text })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success && data.category) {
            const categorySelect = document.querySelector('select[name="category"]');
            if (categorySelect) {
                categorySelect.value = data.category;
                showNotification(`AI predicted category: ${data.category}`, 'info');
            }
        }
    });
}

async function processReceipt(file) {
    const reader = new FileReader();
    reader.onload = async function(e) {
        const imageData = e.target.result;
        
        showLoading('Processing receipt with AI...');
        
        try {
            const response = await fetch('/process_receipt', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ image_data: imageData })
            });
            
            const data = await response.json();
            hideLoading();
            
            if (data.success) {
                // Fill form with extracted data
                const amountInput = document.querySelector('input[name="amount"]');
                const categorySelect = document.querySelector('select[name="category"]');
                const descriptionInput = document.querySelector('input[name="description"]');
                
                if (amountInput && data.extracted_amount > 0) {
                    amountInput.value = data.extracted_amount;
                }
                
                if (categorySelect && data.predicted_category) {
                    categorySelect.value = data.predicted_category;
                }
                
                if (descriptionInput && data.extracted_text) {
                    descriptionInput.value = data.extracted_text.substring(0, 100);
                }
                
                showNotification('Receipt processed successfully!', 'success');
            } else {
                showNotification('Could not process receipt. Please enter manually.', 'warning');
            }
        } catch (error) {
            hideLoading();
            showNotification('Error processing receipt. Please try again.', 'error');
        }
    };
    
    reader.readAsDataURL(file);
}

function submitExpenseForm(form) {
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    // Show loading
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
    submitBtn.disabled = true;
    
    const formData = new FormData(form);
    
    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (response.redirected) {
            window.location.href = response.url;
        } else {
            return response.json();
        }
    })
    .then(data => {
        if (data && data.success) {
            showNotification('Expense added successfully!', 'success');
            setTimeout(() => {
                window.location.href = '/dashboard';
            }, 1500);
        } else if (data) {
            showNotification(data.message, 'error');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    })
    .catch(error => {
        showNotification('Error adding expense. Please try again.', 'error');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}

function deleteExpense(expenseId) {
    if (!confirm('Are you sure you want to delete this expense?')) return;
    
    fetch(`/delete_expense/${expenseId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Expense deleted successfully!', 'success');
            // Remove from UI
            const expenseItem = document.querySelector(`.expense-item[data-id="${expenseId}"]`);
            if (expenseItem) {
                expenseItem.style.opacity = '0';
                expenseItem.style.transform = 'translateX(100%)';
                setTimeout(() => expenseItem.remove(), 300);
            }
        } else {
            showNotification(data.message, 'error');
        }
    });
}

function updateIncome() {
    const form = document.getElementById('updateIncomeForm');
    if (!form) return;
    
    const submitBtn = form.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
    submitBtn.disabled = true;
    
    const formData = new FormData(form);
    
    fetch('/update_income', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Income updated successfully!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification(data.message, 'error');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        }
    })
    .catch(error => {
        showNotification('Error updating income. Please try again.', 'error');
        submitBtn.innerHTML = originalText;
        submitBtn.disabled = false;
    });
}

// Modal Functions
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
}

// Close modals when clicking outside
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.style.display = 'none';
        document.body.style.overflow = 'auto';
    }
});

// Close modals with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.style.display = 'none';
        });
        document.body.style.overflow = 'auto';
    }
});

// Notification System
function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('flash-messages-container') || createNotificationContainer();
    
    const notification = document.createElement('div');
    notification.className = `flash-message flash-${type}`;
    notification.innerHTML = `
        <div class="flash-content">
            <i class="fas ${getNotificationIcon(type)}"></i>
            <span>${message}</span>
        </div>
        <button class="flash-close" onclick="this.parentElement.remove()">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    container.appendChild(notification);
    
    // Auto-remove after duration
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => notification.remove(), 300);
        }
    }, duration);
}

function getNotificationIcon(type) {
    const icons = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    };
    return icons[type] || 'fa-info-circle';
}

function createNotificationContainer() {
    const container = document.createElement('div');
    container.id = 'flash-messages-container';
    container.className = 'flash-messages';
    document.body.appendChild(container);
    return container;
}

// Loading indicator
function showLoading(message = 'Loading...') {
    let loading = document.getElementById('loading-overlay');
    if (!loading) {
        loading = document.createElement('div');
        loading.id = 'loading-overlay';
        loading.innerHTML = `
            <div class="loading-content">
                <i class="fas fa-spinner fa-spin"></i>
                <p>${message}</p>
            </div>
        `;
        document.body.appendChild(loading);
    }
    loading.style.display = 'flex';
}

function hideLoading() {
    const loading = document.getElementById('loading-overlay');
    if (loading) {
        loading.style.display = 'none';
    }
}

// Format currency
function formatCurrency(amount) {
    return '₹' + parseFloat(amount).toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Export expenses
function exportExpenses(format = 'csv') {
    fetch('/api/expense_trends')
    .then(response => response.json())
    .then(data => {
        if (format === 'csv') {
            exportToCSV(data);
        }
    });
}

function exportToCSV(data) {
    let csv = 'Date,Category,Amount,Description\n';
    
    // This is a simplified version - in real app, you'd fetch all expenses
    document.querySelectorAll('.expense-item').forEach(item => {
        const category = item.querySelector('.expense-category').textContent;
        const description = item.querySelector('.expense-description').textContent;
        const amount = item.querySelector('.expense-amount').textContent.replace('₹', '');
        const date = item.querySelector('.expense-date').textContent;
        
        csv += `"${date}","${category}","${amount}","${description}"\n`;
    });
    
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `expenses_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
}

// Initialize tooltips
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Add CSS for loading overlay
const loadingStyles = `
    #loading-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        backdrop-filter: blur(5px);
        display: none;
        justify-content: center;
        align-items: center;
        z-index: 9999;
    }
    
    .loading-content {
        background: white;
        padding: 30px 40px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
    }
    
    .loading-content i {
        font-size: 2.5rem;
        color: #4361ee;
        margin-bottom: 15px;
    }
    
    .loading-content p {
        margin: 0;
        font-weight: 500;
        color: #333;
    }
`;

const styleSheet = document.createElement('style');
styleSheet.textContent = loadingStyles;
document.head.appendChild(styleSheet);

// Make functions available globally
window.deleteExpense = deleteExpense;
window.updateIncome = updateIncome;
window.showNotification = showNotification;
window.formatCurrency = formatCurrency;
window.showModal = showModal;
window.closeModal = closeModal;
window.exportExpenses = exportExpenses;