"""Thread-based utilities for Gemini API calls."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import structlog
from functools import partial
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from queue import Full
import time
from typing import Optional, Dict, Any

logger = structlog.get_logger()

DEFAULT_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

DEFAULT_GENERATION_CONFIG = {
    "temperature": 0.7,
    "max_output_tokens": 2048,
}

class GeminiThreadManagerError(Exception):
    """Base exception for GeminiThreadManager errors."""
    pass

class GeminiQueueFullError(GeminiThreadManagerError):
    """Raised when the thread pool queue is full."""
    pass

class GeminiTimeoutError(GeminiThreadManagerError):
    """Raised when a request times out."""
    pass

class GeminiThreadManager:
    def __init__(self, max_workers: int = 5, queue_size: int = 100, default_timeout: float = 30.0):
        """Initialize the thread manager with a fixed thread pool.
        
        Args:
            max_workers: Maximum number of worker threads
            queue_size: Maximum number of pending tasks
            default_timeout: Default timeout for requests in seconds
        """
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers, 
            thread_name_prefix="gemini_worker"
        )
        self.max_queue_size = queue_size
        self.default_timeout = default_timeout
        self.metrics = {
            'total_requests': 0,
            'failed_requests': 0,
            'timeouts': 0,
            'queue_full': 0,
            'total_processing_time': 0,
        }
        
        logger.info(f"Initialized GeminiThreadManager with {max_workers} workers, queue_size={queue_size}")
        
    def create_model(self, model_name: str = "gemini-1.5-flash", 
                    safety_settings: Optional[Dict] = None, 
                    generation_config: Optional[Dict] = None):
        """Create a new Gemini model instance with specified settings."""
        effective_safety_settings = safety_settings or DEFAULT_SAFETY_SETTINGS.copy()
        
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                safety_settings=effective_safety_settings
            )
            # Store settings on model for reference
            model._custom_safety_settings = effective_safety_settings
            model._custom_generation_config = generation_config or DEFAULT_GENERATION_CONFIG.copy()
            
            logger.debug(f"Created Gemini model: {model_name} with custom settings")
            return model
        except Exception as e:
            logger.error(f"Error creating Gemini model: {str(e)}", exc_info=True)
            raise
    
    def _run_async_in_thread(self, async_func):
        """Run an async function in a new event loop within the thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func)
        except Exception as e:
            logger.error(f"Error in thread's event loop: {str(e)}", exc_info=True)
            raise
        finally:
            loop.close()
    
    async def generate_content(self, model: Any, prompt: str, 
                             generation_config: Optional[Dict] = None, 
                             safety_settings: Optional[Dict] = None,
                             timeout: Optional[float] = None) -> Any:
        """Generate content using a model in a separate thread.
        
        Args:
            model: The Gemini model instance to use
            prompt: The prompt to send to the model
            generation_config: Override default generation settings
            safety_settings: Override default safety settings
            timeout: Request timeout in seconds (overrides default_timeout)
            
        Returns:
            Response from the Gemini model
            
        Raises:
            GeminiQueueFullError: If the thread pool queue is full
            GeminiTimeoutError: If the request times out
            Exception: For other failures
        """
        start_time = time.time()
        self.metrics['total_requests'] += 1
        
        effective_timeout = timeout or self.default_timeout
        effective_generation_config = generation_config or getattr(
            model, '_custom_generation_config', DEFAULT_GENERATION_CONFIG.copy()
        )
        effective_safety_settings = safety_settings or getattr(
            model, '_custom_safety_settings', DEFAULT_SAFETY_SETTINGS.copy()
        )
        
        def _blocking_call():
            try:
                return asyncio.run(model.generate_content_async(
                    prompt,
                    generation_config=effective_generation_config,
                    safety_settings=effective_safety_settings
                ))
            except Exception as e:
                logger.error(f"Error in blocking Gemini call: {str(e)}", exc_info=True)
                self.metrics['failed_requests'] += 1
                raise
        
        loop = asyncio.get_running_loop()
        logger.debug("Submitting Gemini call to thread executor")
        
        try:
            # Check queue size
            if hasattr(self.executor, '_work_queue') and \
               self.executor._work_queue.qsize() >= self.max_queue_size:
                self.metrics['queue_full'] += 1
                raise GeminiQueueFullError("Thread pool queue is full")
            
            # Submit with timeout
            future = loop.run_in_executor(self.executor, _blocking_call)
            response = await asyncio.wait_for(future, timeout=effective_timeout)
            
            processing_time = time.time() - start_time
            self.metrics['total_processing_time'] += processing_time
            logger.debug(f"Received response from thread executor in {processing_time:.2f}s")
            
            return response
            
        except asyncio.TimeoutError:
            self.metrics['timeouts'] += 1
            self.metrics['failed_requests'] += 1
            raise GeminiTimeoutError(f"Request timed out after {effective_timeout}s")
        except Exception as e:
            self.metrics['failed_requests'] += 1
            logger.error(f"Error executing Gemini call in thread: {str(e)}", exc_info=True)
            raise
    
    def get_metrics(self) -> Dict[str, float]:
        """Get current metrics."""
        metrics = self.metrics.copy()
        if metrics['total_requests'] > 0:
            metrics['success_rate'] = (metrics['total_requests'] - metrics['failed_requests']) / metrics['total_requests']
            metrics['avg_processing_time'] = metrics['total_processing_time'] / metrics['total_requests']
        return metrics
    
    def shutdown(self):
        """Shutdown the thread executor gracefully."""
        logger.info("Shutting down GeminiThreadManager executor...")
        try:
            self.executor.shutdown(wait=True)
            logger.info("GeminiThreadManager shutdown complete")
        except Exception as e:
            logger.error(f"Error during GeminiThreadManager shutdown: {str(e)}", exc_info=True) 