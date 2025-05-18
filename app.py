import nest_asyncio
nest_asyncio.apply()

"""Main application module."""
import os
from flask import Flask
from dotenv import load_dotenv
import structlog
from config import config
from extensions import init_extensions, init_gemini
from errors import init_error_handlers
import atexit
from utils.gemini_thread import GeminiThreadManager
from flask_wtf.csrf import generate_csrf

# Configure logging
logger = structlog.get_logger()

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

# Initialize the thread manager as a global instance
# This ensures it's created only once and shared across the application
gemini_thread_manager = GeminiThreadManager(
    max_workers=int(os.getenv('GEMINI_MAX_WORKERS', '5')),
    queue_size=int(os.getenv('GEMINI_QUEUE_SIZE', '100')),
    default_timeout=float(os.getenv('GEMINI_DEFAULT_TIMEOUT', '30.0'))
)

def create_app(config_name='default'):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Load environment variables
    load_dotenv()
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Add diagnostic logging for CSRF configuration
    logger.info(f"CSRF Enabled Status: {app.config.get('WTF_CSRF_ENABLED')}")
    logger.info(f"SECRET_KEY Set: {'Yes' if app.config.get('SECRET_KEY') else 'No'}")
    
    # Initialize extensions
    init_extensions(app)
    
    # Initialize Gemini API configuration and attach thread manager to app
    app.gemini_config_ok = init_gemini(app)
    app.gemini_thread_manager = gemini_thread_manager
    
    if not app.gemini_config_ok:
        logger.error("Failed to initialize Gemini API configuration")
        # We continue app initialization but some features will be disabled
    
    # Initialize error handlers
    init_error_handlers(app)
    
    # Register blueprints
    from routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from routes.api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')
    
    # Add CSRF token context processor
    @app.context_processor
    def inject_csrf_token_value():
        return dict(csrf_token_value=generate_csrf())
    
    # Register cleanup function
    atexit.register(lambda: gemini_thread_manager.shutdown())
    
    # Add metrics endpoint if in debug mode
    if app.debug:
        @app.route('/debug/metrics')
        def metrics():
            return gemini_thread_manager.get_metrics()
    
    logger.info(f"Flask app created with config: {config_name}")
    return app

# This is the WSGI application instance that Hypercorn can serve
# Or, if Hypercorn is given the factory string, it will call create_app()
application = create_app(os.getenv('FLASK_CONFIG') or 'default')

if __name__ == '__main__':
    # This block is for running with `python app.py` (Werkzeug dev server)
    logger.info(f"Starting Flask development server (Werkzeug) on http://127.0.0.1:5000/")
    # Force development mode when running with python app.py
    dev_app = create_app('development')
    dev_app.run(
        host='127.0.0.1',
        port=int(os.getenv('FLASK_PORT', '5000')),
        debug=True,  # Force debug mode
        threaded=True  # Enable threading for the development server
    )