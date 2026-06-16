# services/redis_client.py
import os
import redis
import logging
from functools import wraps
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Import constants
from services.waf_constants import (
    BLOCK_PREFIX, RATE_PREFIX, REPUTATION_PREFIX, 
    OFFENSE_PREFIX, ALERT_PREFIX, LOGIN_ATTEMPTS_PREFIX
)

class RedisClient:
    """Redis client wrapper with connection pooling and error handling"""
    
    _instance = None
    _pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize Redis connection pool"""
        try:
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self._pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=10,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            self.client = redis.Redis(connection_pool=self._pool)
            # Test connection
            self.client.ping()
            logger.info("✅ Redis connection established successfully")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self._pool = None
            self.client = None
    
    def get_client(self) -> Optional[redis.Redis]:
        """Get Redis client instance"""
        if self.client is None:
            self._initialize()
        return self.client
    
    def is_available(self) -> bool:
        """Check if Redis is available"""
        try:
            if self.client:
                self.client.ping()
                return True
        except:
            pass
        return False

# Singleton instance
_redis_client = RedisClient()

def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client instance"""
    return _redis_client.get_client()

def redis_available() -> bool:
    """Check if Redis is available"""
    return _redis_client.is_available()

# Export constants for backward compatibility
__all__ = [
    'get_redis_client', 'redis_available', 
    'BLOCK_PREFIX', 'RATE_PREFIX', 'REPUTATION_PREFIX',
    'OFFENSE_PREFIX', 'ALERT_PREFIX', 'LOGIN_ATTEMPTS_PREFIX'
]

# For backward compatibility with existing imports
redis_client = get_redis_client()