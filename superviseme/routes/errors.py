"""
Error handlers for HTTP errors (404, 500, etc.) with integrated logging
"""
import logging
import traceback
from datetime import datetime
from flask import Blueprint, render_template, request, current_app, session
from flask_login import current_user
from werkzeug.exceptions import HTTPException
import os

errors = Blueprint('errors', __name__)

# Set up error-specific logger
error_logger = logging.getLogger(__name__)

def log_error(error, status_code, user_info=None, request_info=None):
    """
    Comprehensive error logging with structured data
    """
    try:
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'status_code': status_code,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'user_id': current_user.id if current_user.is_authenticated else None,
            'username': current_user.username if current_user.is_authenticated else 'anonymous',
            'user_type': current_user.user_type if current_user.is_authenticated else None,
            'url': request.url if request else None,
            'method': request.method if request else None,
            'ip_address': request.remote_addr if request else None,
            'user_agent': request.headers.get('User-Agent') if request else None,
            'referer': request.headers.get('Referer') if request else None,
            'session_id': session.get('_id') if session else None,
        }
        
        # Add stack trace for 500 errors
        if status_code >= 500:
            log_entry['stack_trace'] = traceback.format_exc()
            error_logger.error(f"Server Error {status_code}: {error}", extra=log_entry)
        elif status_code >= 400:
            error_logger.warning(f"Client Error {status_code}: {error}", extra=log_entry)
        else:
            error_logger.info(f"HTTP {status_code}: {error}", extra=log_entry)
            
    except Exception as logging_error:
        # Fallback logging if structured logging fails
        error_logger.error(f"Error logging failed: {logging_error}. Original error: {error}")

@errors.app_errorhandler(400)
def bad_request_error(error):
    """Handle 400 Bad Request errors"""
    log_error(error, 400)
    return render_template('errors/400.html', error=error), 400

@errors.app_errorhandler(401)
def unauthorized_error(error):
    """Handle 401 Unauthorized errors"""
    log_error(error, 401)
    return render_template('errors/401.html', error=error), 401

@errors.app_errorhandler(403)
def forbidden_error(error):
    """Handle 403 Forbidden errors"""
    log_error(error, 403)
    return render_template('errors/403.html', error=error), 403

@errors.app_errorhandler(404)
def not_found_error(error):
    """Handle 404 Not Found errors"""
    log_error(error, 404)
    return render_template('errors/404.html', error=error), 404

@errors.app_errorhandler(405)
def method_not_allowed_error(error):
    """Handle 405 Method Not Allowed errors"""
    log_error(error, 405)
    return render_template('errors/405.html', error=error), 405

@errors.app_errorhandler(429)
def too_many_requests_error(error):
    """Handle 429 Too Many Requests errors"""
    log_error(error, 429)
    return render_template('errors/429.html', error=error), 429

@errors.app_errorhandler(500)
def internal_server_error(error):
    """Handle 500 Internal Server Error"""
    log_error(error, 500)
    # For 500 errors, we should rollback any pending database transactions
    try:
        from superviseme import db
        db.session.rollback()
    except Exception:
        pass  # If database is unavailable, continue without rollback
    return render_template('errors/500.html', error=error), 500

@errors.app_errorhandler(502)
def bad_gateway_error(error):
    """Handle 502 Bad Gateway errors"""
    log_error(error, 502)
    return render_template('errors/502.html', error=error), 502

@errors.app_errorhandler(503) 
def service_unavailable_error(error):
    """Handle 503 Service Unavailable errors"""
    log_error(error, 503)
    return render_template('errors/503.html', error=error), 503

@errors.app_errorhandler(Exception)
def handle_exception(error):
    """Handle all other uncaught exceptions"""
    # Pass through HTTP errors to their specific handlers
    if isinstance(error, HTTPException):
        return error
    
    # Handle non-HTTP exceptions as 500 errors
    log_error(error, 500)
    try:
        from superviseme import db
        db.session.rollback()
    except Exception:
        pass
    return render_template('errors/500.html', error=error), 500

# Utility route for testing error pages (only in development)
@errors.route('/test-error/<int:status_code>')
def test_error(status_code):
    """Test route for triggering different error types (development only)"""
    if not current_app.debug:
        return render_template('errors/404.html'), 404
    
    if status_code == 400:
        from werkzeug.exceptions import BadRequest
        raise BadRequest("Test bad request error")
    elif status_code == 401:
        from werkzeug.exceptions import Unauthorized
        raise Unauthorized("Test unauthorized error")
    elif status_code == 403:
        from werkzeug.exceptions import Forbidden
        raise Forbidden("Test forbidden error") 
    elif status_code == 404:
        from werkzeug.exceptions import NotFound
        raise NotFound("Test not found error")
    elif status_code == 405:
        from werkzeug.exceptions import MethodNotAllowed
        raise MethodNotAllowed("Test method not allowed error")
    elif status_code == 429:
        from werkzeug.exceptions import TooManyRequests
        raise TooManyRequests("Test too many requests error")
    elif status_code == 500:
        raise Exception("Test internal server error")
    elif status_code == 502:
        from werkzeug.exceptions import BadGateway
        raise BadGateway("Test bad gateway error")
    elif status_code == 503:
        from werkzeug.exceptions import ServiceUnavailable
        raise ServiceUnavailable("Test service unavailable error")
    else:
        return render_template('errors/404.html'), 404