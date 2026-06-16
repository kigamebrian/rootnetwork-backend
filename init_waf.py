# init_waf.py - Updated for your project structure
import os
import logging
from services.waf_blocklist import clear_expired_blocks
from services.redis_client import redis_available

# Configure logging
logger = logging.getLogger(__name__)

def init_waf(force: bool = False):
    """
    Initialize WAF system
    
    Args:
        force: Force initialization even in testing environments
    
    Returns:
        bool: True if WAF initialized successfully, False otherwise
    """
    # Skip WAF in test environment unless forced
    if not force and os.getenv('FLASK_ENV') == 'testing':
        logger.info("🔧 Skipping WAF initialization in test environment")
        return True
    
    logger.info("🛡️ Initializing WAF System...")
    
    # Check Redis connection
    if not redis_available():
        logger.error("❌ Redis is not available! WAF will not function properly.")
        # Return False but don't crash the app
        return False
    
    # Clear expired blocks (optional, Redis handles TTL automatically)
    try:
        clear_expired_blocks()
        logger.info("✅ WAF initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ WAF initialization failed: {e}")
        return False

# Run if executed directly (for testing)
if __name__ == "__main__":
    result = init_waf()
    print(f"WAF initialization: {'SUCCESS' if result else 'FAILED'}")