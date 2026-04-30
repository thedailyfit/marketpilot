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

    async def get_response(self, user_query: str, market_context: dict) -> str:
        """Process user query against the live algorithmic market context."""
        if not self.is_ready or not self.model:
            return "Gemini AI is offline. Please configure GEMINI_API_KEY in your environment variables."

        try:
            # Construct a prompt blending the user query with the live math context
            system_prompt = (
                "You are the Singularity Meta AI for MarketPilot, an advanced institutional trading system. "
                "You have direct access to quantitative algorithmic engines. "
                f"LIVE ALGO DATA: {str(market_context)}\n\n"
                "Respond concisely and professionally as a quantitative trading assistant. "
                "If the user asks to execute, confirm the exact contract and wait for their explicit execute command."
            )
            
            full_prompt = f"{system_prompt}\n\nUSER COMMAND: {user_query}"
            
            response = self.model.generate_content(full_prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
            return f"Error communicating with Gemini AI: {str(e)}"

# Singleton instance
meta_agent = MetaAIAgent()
