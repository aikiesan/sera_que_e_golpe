import nest_asyncio
nest_asyncio.apply()  # Apply this first, before any other imports

"""Flask extensions and third-party service configurations."""
import os
import logging
import structlog
import google.generativeai as genai
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_caching import Cache
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Initialize extensions
csrf = CSRFProtect()
cache = Cache()
talisman = Talisman()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=["200 per day", "50 per hour"]
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True
)
logger = structlog.get_logger()

def init_gemini(app):
    """Initialize Gemini API configuration and test it."""
    try:
        gemini_api_key = app.config.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("Gemini API key not found in app config")
        
        genai.configure(api_key=gemini_api_key)
        logger.info("Gemini API configured globally")
        
        # Test the API with a temporary model instance
        temp_model = genai.GenerativeModel(
            app.config.get("GEMINI_MODEL", "gemini-1.5-flash"),
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        
        # Test the model
        test_response = temp_model.generate_content("Test connection. Respond with 'OK'.")
        if test_response and test_response.text and "OK" in test_response.text:
            logger.info(f"Gemini API test successful: {test_response.text.strip()}")
            return True
        else:
            raise Exception(f"Invalid Gemini test response: {test_response.text if test_response else 'No response'}")
            
    except Exception as e:
        logger.error(f"Critical error initializing Gemini: {str(e)}", exc_info=True)
        return False

def init_extensions(app):
    """Initialize all Flask extensions."""
    csrf.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    
    # Configure Content Security Policy
    csp = {
        'default-src': ["'self'"],
        'img-src': ["'self'", "data:", "https:"],
        'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
        'style-src': ["'self'", "https://fonts.googleapis.com", "'unsafe-inline'"],
        'style-src-elem': ["'self'", "https://fonts.googleapis.com", "'unsafe-inline'"],
        'style-src-attr': ["'unsafe-inline'"],
        'font-src': ["'self'", "https://fonts.gstatic.com"],
        'connect-src': ["'self'"],
        'frame-src': ["'self'", "https://www.youtube.com", "https://www.youtube-nocookie.com"],
    }
    
    talisman.init_app(
        app,
        content_security_policy=csp,
        force_https=False,
        frame_options='SAMEORIGIN',
        x_content_type_options='nosniff'
    ) 