import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import structlog

logger = structlog.get_logger()

class GeminiClient:
    def __init__(self, model_name: str = 'gemini-1.5-flash'):
        """Initialize a GeminiClient instance.
        
        Args:
            model_name: The name of the model to use. Defaults to 'gemini-1.5-flash'.
            
        Note:
            This class assumes genai.configure() has been called globally (e.g., in app.py)
            before instantiating this class.
        """
        self.model_name = model_name
        try:
            self.model = genai.GenerativeModel(self.model_name)
            logger.info("gemini.client.initialized", model=self.model_name)
            
            # Test the connection
            test_response = self.model.generate_content("Test connection. Respond with 'OK'.")
            if test_response and test_response.text:
                logger.info("gemini.client.test_successful", response=test_response.text)
            else:
                raise Exception("Received empty response from model during test")
                
        except Exception as e:
            logger.error("gemini.client.initialization_failed", error=str(e))
            logger.error("Make sure genai.configure() was called before instantiating GeminiClient")
            self.model = None
            raise
    
    def get_safety_settings(self):
        """Get the default safety settings for content generation."""
        return {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
    
    def get_generation_config(self):
        """Get the default generation configuration."""
        return {
            "temperature": 0.7,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 2048,
        }
    
    async def generate_content_async(self, prompt: str, **kwargs):
        """
        Generate content asynchronously with error handling and logging.
        
        Args:
            prompt: The prompt to send to the model
            **kwargs: Additional arguments to pass to generate_content
        
        Returns:
            The model's response
        
        Raises:
            Exception: If content generation fails or if model is not initialized
        """
        if not self.model:
            error_msg = "GeminiClient model not initialized. Make sure genai.configure() was called."
            logger.error("gemini.client.model_not_initialized")
            raise RuntimeError(error_msg)

        try:
            # Merge default configs with any provided kwargs
            generation_config = {**self.get_generation_config(), **kwargs.get('generation_config', {})}
            safety_settings = {**self.get_safety_settings(), **kwargs.get('safety_settings', {})}
            
            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            # Check for blocked content
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                block_reason = getattr(response.prompt_feedback.block_reason, 'name', 
                                    str(response.prompt_feedback.block_reason))
                logger.warning("gemini.client.content_blocked", 
                             block_reason=block_reason,
                             safety_ratings=response.prompt_feedback.safety_ratings)
                raise Exception(f"Content blocked: {block_reason}")
            
            return response
            
        except Exception as e:
            logger.error("gemini.client.generation_failed", error=str(e))
            raise 