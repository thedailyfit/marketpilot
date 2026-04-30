import google.generativeai as genai
from core.config_manager import sys_config
import logging

logger = logging.getLogger(__name__)

class MetaAIAgent:
    def __init__(self):
        self.model = None
        self.is_ready = False
        self._initialize_gemini()
        
    def _initialize_gemini(self):
        try:
            if not sys_config.GEMINI_API_KEY:
                logger.warning("No GEMINI_API_KEY found. Meta AI Agent running in offline/mock mode.")
                return
                
            genai.configure(api_key=sys_config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-1.5-pro')
            self.is_ready = True
            logger.info("Gemini 1.5 Pro initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")

    async def get_response(self, user_query: str, market_context: dict, image_bytes: bytes = None) -> str:
        """Process user query against live context, with optional image analysis."""
        if not self.is_ready or not self.model:
            return "Gemini AI is offline. Please configure GEMINI_API_KEY in your environment variables."

        try:
            import io
            from PIL import Image

            system_prompt = (
                "You are the Singularity Meta AI for MarketPilot, an advanced institutional trading system. "
                "You act as the primary brain. If the user shares an image (like a chart screenshot or news clipping), "
                "analyze it immediately, cross-reference it with the live algo data, and provide verified feedback. "
                f"LIVE ALGO DATA: {str(market_context)}\n\n"
                "Provide a concise, highly professional quantitative response."
            )
            
            full_prompt = f"{system_prompt}\n\nUSER COMMAND: {user_query}"
            
            if image_bytes:
                img = Image.open(io.BytesIO(image_bytes))
                response = self.model.generate_content([full_prompt, img])
            else:
                response = self.model.generate_content(full_prompt)
                
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return f"Error communicating with Gemini AI: {str(e)}"

# Singleton instance
meta_agent = MetaAIAgent()
