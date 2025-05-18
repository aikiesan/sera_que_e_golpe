#!/usr/bin/env python3
"""
ASGI server entry point for the Flask application.
This script wraps the Flask WSGI application with ASGI middleware and runs it using Uvicorn.
"""

import uvicorn
from app import application
from a2wsgi import ASGIMiddleware
import logging
import os
from typing import Optional
import sys

# Configure basic logging for this script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# This 'application' (the Flask WSGI app) is imported.
# The 'asgi_compatible_app' will be created when this module (run_asgi) is imported by Uvicorn.
try:
    asgi_compatible_app = ASGIMiddleware(application)
    logger.info("Flask application wrapped with ASGIMiddleware for ASGI server.")
except Exception as e:
    logger.error(f"Failed to wrap Flask application with ASGI middleware: {str(e)}")
    raise RuntimeError(f"ASGI middleware initialization failed: {str(e)}")

def get_config() -> dict:
    """
    Retrieves configuration from environment variables with defaults.
    
    Returns:
        dict: Configuration dictionary for Uvicorn
    """
    return {
        "host": os.getenv("HOST", "0.0.0.0"),
        "port": int(os.getenv("PORT", "5000")),
        "reload": os.getenv("FLASK_ENV", "development").lower() == "development",
        "log_level": os.getenv("LOG_LEVEL", "info").lower(),
        "workers": int(os.getenv("WORKERS", "1"))
    }

def main() -> None:
    """Main entry point for the ASGI server."""
    try:
        config = get_config()
        logger.info(f"Starting Uvicorn ASGI server on {config['host']}:{config['port']}")
        uvicorn.run(
            "run_asgi:asgi_compatible_app",  # Use import string format for proper hot reloading
            host=config["host"],
            port=config["port"],
            reload=config["reload"],
            log_level=config["log_level"],
            workers=config["workers"]
        )
    except KeyboardInterrupt:
        logger.info("Received shutdown signal. Gracefully shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start ASGI server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 