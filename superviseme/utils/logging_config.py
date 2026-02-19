"""
Comprehensive logging configuration for SuperviseMe application
"""
import logging
import logging.handlers
import os
import json
from datetime import datetime
from flask import request, session
from flask_login import current_user

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging
    """
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                             'filename', 'module', 'lineno', 'funcName', 'created', 
                             'msecs', 'relativeCreated', 'thread', 'threadName', 
                             'processName', 'process', 'message', 'exc_info', 'exc_text', 'stack_info']:
                    log_entry[key] = value
        
        return json.dumps(log_entry)

class RequestContextFilter(logging.Filter):
    """
    Add request context information to log records
    """
    def filter(self, record):
        try:
            # Add request information if available
            if request:
                record.url = request.url
                record.method = request.method
                record.ip_address = request.remote_addr
                record.user_agent = request.headers.get('User-Agent', '')[:200]  # Truncate long user agents
                record.referer = request.headers.get('Referer', '')
            
            # Add user information if available
            if current_user and current_user.is_authenticated:
                record.user_id = current_user.id
                record.username = current_user.username
                record.user_type = current_user.user_type
            else:
                record.user_id = None
                record.username = 'anonymous'
                record.user_type = None
            
            # Add session information if available
            if session:
                record.session_id = session.get('_id', '')
            
        except RuntimeError:
            # Outside request context, add default values
            record.url = None
            record.method = None
            record.ip_address = None
            record.user_agent = None
            record.referer = None
            record.user_id = None
            record.username = None
            record.user_type = None
            record.session_id = None
        
        return True

def setup_logging(app):
    """
    Set up comprehensive logging for the Flask application
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(app.instance_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(level=logging.INFO)
    
    # Create formatters
    json_formatter = JSONFormatter()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and configure file handlers
    
    # General application log
    app_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(json_formatter)
    app_handler.addFilter(RequestContextFilter())
    
    # Error log (warnings and above)
    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'error.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(json_formatter)
    error_handler.addFilter(RequestContextFilter())
    
    # Access log for HTTP requests
    access_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'access.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    access_handler.setLevel(logging.INFO)
    access_handler.setFormatter(json_formatter)
    access_handler.addFilter(RequestContextFilter())
    
    # Security log for authentication events
    security_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'security.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10
    )
    security_handler.setLevel(logging.INFO)
    security_handler.setFormatter(json_formatter)
    security_handler.addFilter(RequestContextFilter())
    
    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if app.debug else logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)
    
    # Create specialized loggers
    access_logger = logging.getLogger('superviseme.access')
    access_logger.addHandler(access_handler)
    access_logger.propagate = False
    
    security_logger = logging.getLogger('superviseme.security')
    security_logger.addHandler(security_handler)
    security_logger.propagate = False
    
    # Configure Flask's logger
    app.logger.addHandler(app_handler)
    app.logger.addHandler(error_handler)
    app.logger.setLevel(logging.INFO)
    
    # Configure Werkzeug logger (for HTTP requests)
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addHandler(access_handler)
    werkzeug_logger.setLevel(logging.INFO)
    
    # Log application startup
    app.logger.info(f"SuperviseMe application started", extra={
        'event_type': 'app_startup',
        'debug_mode': app.debug,
        'environment': os.getenv('FLASK_ENV', 'production')
    })
    
    return {
        'app_logger': app.logger,
        'access_logger': access_logger,
        'security_logger': security_logger,
        'error_logger': logging.getLogger('superviseme.errors')
    }

def log_request_response(app, loggers):
    """
    Set up request/response logging middleware
    """
    @app.before_request
    def log_request_info():
        loggers['access_logger'].info("Request started", extra={
            'event_type': 'request_start',
            'endpoint': request.endpoint,
            'url_rule': str(request.url_rule) if request.url_rule else None,
            'content_length': request.content_length,
            'content_type': request.content_type
        })
    
    @app.after_request
    def log_response_info(response):
        loggers['access_logger'].info("Request completed", extra={
            'event_type': 'request_end',
            'status_code': response.status_code,
            'content_length': response.content_length,
            'content_type': response.content_type
        })
        return response

def log_security_event(event_type, details=None, user_id=None):
    """
    Log security-related events
    """
    security_logger = logging.getLogger('superviseme.security')
    security_logger.info(f"Security event: {event_type}", extra={
        'event_type': event_type,
        'details': details or {},
        'user_id': user_id or (current_user.id if current_user.is_authenticated else None)
    })

# Example usage of security logging
def log_login_attempt(username, success, ip_address=None, details=None):
    """Log login attempts"""
    payload = {
        'username': username,
        'success': success,
        'ip_address': ip_address or (request.remote_addr if request else None)
    }
    if details:
        payload['details'] = details

    log_security_event('login_attempt', payload)

def log_logout(username, user_id=None):
    """Log logout events"""
    log_security_event('logout', {
        'username': username
    }, user_id)

def log_privilege_escalation_attempt(username, attempted_action):
    """Log attempts to access unauthorized resources"""
    log_security_event('privilege_escalation_attempt', {
        'username': username,
        'attempted_action': attempted_action
    })

def log_data_access(resource_type, resource_id, action):
    """Log data access events"""
    log_security_event('data_access', {
        'resource_type': resource_type,
        'resource_id': resource_id,
        'action': action
    })