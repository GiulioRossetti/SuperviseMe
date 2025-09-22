/**
 * SuperviseMe Notifications System
 * Handles real-time notifications display and interaction
 */

// Notification management
let notificationsPoll = null;
let notificationsLoaded = false;

// Initialize notifications when page loads
$(document).ready(function() {
    initNotifications();
});

function initNotifications() {
    // Load initial notifications
    loadNotifications();
    
    // Poll for new notifications every 30 seconds
    startNotificationPolling();
    
    // Handle dropdown show event
    $('#alertsDropdown').on('shown.bs.dropdown', function() {
        if (!notificationsLoaded) {
            loadNotifications();
        }
    });
}

function loadNotifications() {
    $.ajax({
        url: '/api/notifications?limit=10',
        method: 'GET',
        success: function(data) {
            displayNotifications(data.notifications);
            updateNotificationCounter(data.unread_count);
            notificationsLoaded = true;
        },
        error: function(xhr, status, error) {
            console.error('Error loading notifications:', error);
            displayNotificationError();
        }
    });
}

function displayNotifications(notifications) {
    const notificationsList = $('#notifications-list');
    
    if (notifications.length === 0) {
        notificationsList.html(`
            <div class="text-center py-4 text-muted">
                <i class="fas fa-bell-slash fa-2x mb-2"></i>
                <div>No notifications</div>
            </div>
        `);
        return;
    }
    
    let html = '';
    notifications.forEach(function(notification) {
        const timeAgo = getTimeAgo(notification.created_at);
        const iconClass = getNotificationIcon(notification.type);
        const iconColor = getNotificationColor(notification.type);
        const readClass = notification.is_read ? 'text-muted' : '';
        const bgClass = notification.is_read ? '' : 'bg-light';
        
        html += `
            <a class="dropdown-item d-flex align-items-center ${bgClass} notification-item" 
               href="#" 
               onclick="handleNotificationClick(${notification.id}, '${notification.action_url || '#'}')"
               data-notification-id="${notification.id}">
                <div class="mr-3">
                    <div class="icon-circle ${iconColor}">
                        <i class="${iconClass} text-white"></i>
                    </div>
                </div>
                <div class="flex-grow-1">
                    <div class="small text-gray-500 ${readClass}">${timeAgo}</div>
                    <div class="font-weight-bold ${readClass}">${notification.title}</div>
                    ${notification.message.length > 80 ? 
                        `<div class="small ${readClass}">${notification.message.substring(0, 80)}...</div>` :
                        `<div class="small ${readClass}">${notification.message}</div>`
                    }
                </div>
                ${!notification.is_read ? '<div class="ml-2"><span class="badge badge-primary badge-pill">New</span></div>' : ''}
            </a>
        `;
    });
    
    notificationsList.html(html);
}

function displayNotificationError() {
    $('#notifications-list').html(`
        <div class="text-center py-4 text-danger">
            <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
            <div>Error loading notifications</div>
            <button class="btn btn-sm btn-outline-primary mt-2" onclick="loadNotifications()">
                <i class="fas fa-sync"></i> Retry
            </button>
        </div>
    `);
}

function updateNotificationCounter(unreadCount) {
    const counter = $('#notification-counter');
    if (unreadCount > 0) {
        counter.text(unreadCount > 99 ? '99+' : unreadCount).show();
    } else {
        counter.hide();
    }
}

function getNotificationIcon(type) {
    const icons = {
        'new_update': 'fas fa-edit',
        'new_feedback': 'fas fa-comment',
        'todo_assigned': 'fas fa-tasks',
        'status_change': 'fas fa-info-circle',
        'default': 'fas fa-bell'
    };
    return icons[type] || icons['default'];
}

function getNotificationColor(type) {
    const colors = {
        'new_update': 'bg-success',
        'new_feedback': 'bg-primary',
        'todo_assigned': 'bg-warning',
        'status_change': 'bg-info',
        'default': 'bg-secondary'
    };
    return colors[type] || colors['default'];
}

function getTimeAgo(timestamp) {
    const now = Math.floor(Date.now() / 1000);
    const diff = now - timestamp;
    
    if (diff < 60) return 'Just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 2592000) return Math.floor(diff / 86400) + 'd ago';
    
    return new Date(timestamp * 1000).toLocaleDateString();
}

function handleNotificationClick(notificationId, actionUrl) {
    // Mark notification as read
    markNotificationAsRead(notificationId);
    
    // Navigate to action URL if provided
    if (actionUrl && actionUrl !== '#') {
        window.location.href = actionUrl;
    }
}

function markNotificationAsRead(notificationId) {
    $.ajax({
        url: `/api/notifications/${notificationId}/read`,
        method: 'POST',
        success: function() {
            // Update the notification item visually
            const notificationItem = $(`.notification-item[data-notification-id="${notificationId}"]`);
            notificationItem.removeClass('bg-light');
            notificationItem.find('.badge-primary').remove();
            notificationItem.find('div').addClass('text-muted');
            
            // Update counter
            updateNotificationCounterAfterRead();
        },
        error: function(xhr, status, error) {
            console.error('Error marking notification as read:', error);
        }
    });
}

function markAllAsRead() {
    $.ajax({
        url: '/api/notifications/mark_all_read',
        method: 'POST',
        success: function() {
            // Refresh notifications display
            loadNotifications();
        },
        error: function(xhr, status, error) {
            console.error('Error marking all notifications as read:', error);
        }
    });
}

function updateNotificationCounterAfterRead() {
    const counter = $('#notification-counter');
    const currentCount = parseInt(counter.text()) || 0;
    const newCount = Math.max(0, currentCount - 1);
    
    if (newCount > 0) {
        counter.text(newCount > 99 ? '99+' : newCount);
    } else {
        counter.hide();
    }
}

function loadMoreNotifications() {
    // Could implement pagination or navigate to a full notifications page
    loadNotifications();
}

function startNotificationPolling() {
    // Poll for notification count updates every 30 seconds
    notificationsPoll = setInterval(function() {
        $.ajax({
            url: '/api/notifications/unread_count',
            method: 'GET',
            success: function(data) {
                updateNotificationCounter(data.unread_count);
            },
            error: function(xhr, status, error) {
                console.error('Error polling notification count:', error);
            }
        });
    }, 30000); // 30 seconds
}

function stopNotificationPolling() {
    if (notificationsPoll) {
        clearInterval(notificationsPoll);
        notificationsPoll = null;
    }
}

// Clean up polling when page unloads
$(window).on('beforeunload', function() {
    stopNotificationPolling();
});

// Export functions for global access
window.markAllAsRead = markAllAsRead;
window.loadMoreNotifications = loadMoreNotifications;
window.handleNotificationClick = handleNotificationClick;