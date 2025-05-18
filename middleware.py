"""Middleware module for request processing."""
import uuid
from functools import wraps
from flask import request, g, current_app
import structlog
from werkzeug.utils import secure_filename
import magic
import os

logger = structlog.get_logger()

def init_request_id():
    """Initialize request ID for tracking."""
    request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
    g.request_id = request_id
    logger.new(request_id=request_id)

def log_request_info():
    """Log request information."""
    logger.info("Request received",
                method=request.method,
                path=request.path,
                remote_addr=request.remote_addr)

def validate_file_type(allowed_mimetypes=None):
    """
    Decorator to validate file type using libmagic.
    
    Args:
        allowed_mimetypes: List of allowed MIME types
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'file' not in request.files and 'image' not in request.files:
                return {
                    'error': 'No file provided',
                    'status_code': 400
                }, 400
            
            file = request.files.get('file') or request.files.get('image')
            if file.filename == '':
                return {
                    'error': 'No file selected',
                    'status_code': 400
                }, 400
            
            # Read file content for MIME type detection
            file_content = file.read()
            file.seek(0)  # Reset file pointer
            
            # Detect MIME type
            mime = magic.Magic(mime=True)
            file_type = mime.from_buffer(file_content)
            
            if allowed_mimetypes and file_type not in allowed_mimetypes:
                return {
                    'error': f'Invalid file type. Allowed types: {", ".join(allowed_mimetypes)}',
                    'detected_type': file_type,
                    'status_code': 400
                }, 400
            
            # Store detected MIME type
            g.detected_mime_type = file_type
            return f(*args, **kwargs)
        return wrapper
    return decorator

def save_uploaded_file(file, upload_folder=None):
    """
    Safely save an uploaded file.
    
    Args:
        file: FileStorage object
        upload_folder: Optional custom upload folder
        
    Returns:
        Tuple of (success, filepath or error_message)
    """
    if not file:
        return False, "No file provided"
    
    try:
        filename = secure_filename(file.filename)
        if not filename:
            return False, "Invalid filename"
        
        # Use custom or default upload folder
        target_folder = upload_folder or current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        
        filepath = os.path.join(target_folder, filename)
        file.save(filepath)
        
        return True, filepath
    except Exception as e:
        logger.error("File save error",
                    error=str(e),
                    filename=file.filename if file else None,
                    exc_info=True)
        return False, f"Error saving file: {str(e)}"

def cleanup_temp_files():
    """Clean up temporary files after request."""
    temp_files = getattr(g, '_temp_files', [])
    for filepath in temp_files:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            logger.error(f"Error cleaning up temp file: {filepath}", error=str(e))

def register_middleware(app):
    """Register middleware with the Flask app."""
    @app.before_request
    def before_request():
        init_request_id()
        log_request_info()
    
    @app.after_request
    def after_request(response):
        cleanup_temp_files()
        return response 