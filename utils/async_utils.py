"""Async utilities for the Flask application."""
import asyncio
from functools import wraps
import structlog
from typing import Callable, Any, Coroutine

logger = structlog.get_logger()

def get_or_create_eventloop():
    """Get the current event loop or create a new one."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError as ex:
        if "There is no current event loop in thread" in str(ex):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop
        raise

async def run_async_safely(coro: Coroutine) -> Any:
    """
    Safely run an async coroutine, handling event loop issues.
    
    Args:
        coro: The coroutine to run
        
    Returns:
        The result of the coroutine
        
    Raises:
        Exception: If the coroutine execution fails
    """
    try:
        loop = get_or_create_eventloop()
        if loop.is_running():
            return await coro
        else:
            return loop.run_until_complete(coro)
    except Exception as e:
        logger.error("Error in async execution",
                    coroutine=coro.__name__ if hasattr(coro, '__name__') else str(coro),
                    error=str(e),
                    exc_info=True)
        raise

def async_to_sync(f: Callable) -> Callable:
    """
    Decorator to convert an async function to sync function.
    
    Args:
        f: The async function to convert
        
    Returns:
        A synchronous version of the function
    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

def background_task(f: Callable) -> Callable:
    """
    Decorator to run a function as a background task.
    
    Args:
        f: The function to run in the background
        
    Returns:
        A wrapper function that runs the original function in the background
    """
    @wraps(f)
    async def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            return await loop.create_task(f(*args, **kwargs))
        except Exception as e:
            logger.error(f"Error in background task {f.__name__}",
                        error=str(e),
                        exc_info=True)
            raise
    return wrapper 