"""Error handling module for the Flask application."""
from flask import jsonify, render_template, request, flash, redirect, url_for
import structlog
from werkzeug.exceptions import HTTPException
from flask_wtf.csrf import CSRFError
from functools import wraps

logger = structlog.get_logger()

class APIError(Exception):
    """Base exception for API errors."""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or {})
        rv['error'] = self.message
        rv['status_code'] = self.status_code
        return rv

def handle_api_error(error):
    """Handle API errors."""
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

def handle_404_error(error):
    """Handle 404 Not Found errors."""
    logger.warning("404 - Page not found", 
                  path=request.path,
                  method=request.method)
    
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'Resource not found',
            'status_code': 404
        }), 404
    return render_template('errors/404.html'), 404

def handle_csrf_error(error):
    """Handle CSRF validation errors."""
    logger.warning("CSRF validation failed",
                  path=request.path,
                  method=request.method,
                  error=str(error))
    
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'CSRF validation failed',
            'message': str(error),
            'status_code': 400
        }), 400
    
    flash('Erro de segurança: token CSRF inválido. Por favor, tente novamente.', 'error')
    return redirect(url_for('main.index'))

def handle_500_error(error):
    """Handle 500 Internal Server errors."""
    logger.error("500 - Internal server error", 
                error_info=str(error),
                path=request.path,
                method=request.method,
                exc_info=True)
    
    if request.path.startswith('/api/'):
        return jsonify({
            'error': 'Internal server error',
            'status_code': 500
        }), 500
    return render_template('errors/500.html'), 500

def handle_413_error(error):
    """Handle 413 Request Entity Too Large errors."""
    from flask import current_app
    logger.warning("413 - File too large", 
                  path=request.path,
                  content_length=request.content_length)
    
    response = {
        'error': 'File too large',
        'message': 'The uploaded file exceeds the maximum allowed size.',
        'max_size_mb': current_app.config.get('MAX_CONTENT_LENGTH', 0) / (1024 * 1024)
    }
    
    if request.path.startswith('/api/'):
        return jsonify(response), 413
    return render_template('errors/413.html', **response), 413

def init_error_handlers(app):
    """Initialize error handlers for the application."""
    app.register_error_handler(APIError, handle_api_error)
    app.register_error_handler(404, handle_404_error)
    app.register_error_handler(500, handle_500_error)
    app.register_error_handler(413, handle_413_error)
    app.register_error_handler(CSRFError, handle_csrf_error)
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        """Handle any unhandled exceptions."""
        logger.error("Unhandled exception",
                    error_type=type(error).__name__,
                    error_str=str(error),
                    path=request.path,
                    method=request.method,
                    exc_info=True)
        
        if request.path.startswith('/api/'):
            return jsonify({
                'error': 'An unexpected error occurred',
                'status_code': 500
            }), 500
        return render_template('errors/500.html'), 500

def api_error_handler(f):
    """Decorator to handle API endpoint errors consistently."""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except APIError as e:
            return handle_api_error(e)
        except Exception as e:
            logger.error(f"API endpoint error in {f.__name__}",
                        error_type=type(e).__name__,
                        error_str=str(e),
                        exc_info=True)
            return jsonify({
                'error': 'An unexpected error occurred',
                'status_code': 500
            }), 500
    return decorated_function 