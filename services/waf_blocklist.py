# services/waf_blocklist.py
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from functools import wraps

from services.redis_client import get_redis_client, redis_available
from services.waf_constants import (
    BLOCK_PREFIX, RATE_PREFIX, REPUTATION_PREFIX, 
    OFFENSE_PREFIX, ALERT_PREFIX, LOGIN_ATTEMPTS_PREFIX,
    get_ban_duration, get_ban_label,
    OFFENSE_BLOCK_THRESHOLD, DEFAULT_REPUTATION,
    MIN_REPUTATION, MAX_REPUTATION, REPUTATION_TTL,
    DEFAULT_RATE_LIMIT, DEFAULT_RATE_WINDOW
)

logger = logging.getLogger(__name__)

# ========== DECORATORS ==========

def handle_redis_errors(default_return=None, log_error=True):
    """Decorator to handle Redis connection errors gracefully"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not redis_available():
                if log_error:
                    logger.error(f"Redis unavailable in {func.__name__}")
                return default_return
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"Redis error in {func.__name__}: {e}")
                return default_return
        return wrapper
    return decorator

# ========== CORE FUNCTIONS ==========

@handle_redis_errors(default_return=0)
def get_offense_count(ip: str) -> int:
    """Get the offense count for an IP address"""
    if not ip:
        return 0
    key = f"{OFFENSE_PREFIX}{ip}"
    redis_client = get_redis_client()
    count = redis_client.get(key)
    return int(count) if count else 0

@handle_redis_errors(default_return=None)
def get_offense_details(ip: str) -> Dict[str, Any]:
    """Get detailed offense information for an IP"""
    if not ip:
        return {'error': 'Invalid IP'}
    
    return {
        'ip': ip,
        'offense_count': get_offense_count(ip),
        'is_blocked': is_blocked(ip),
        'block_info': get_block_info(ip),
        'reputation': get_reputation(ip)
    }

@handle_redis_errors(default_return=False)
def is_blocked(ip: str) -> bool:
    """Check if IP is blocked"""
    if not ip:
        return False
    key = f"{BLOCK_PREFIX}{ip}"
    redis_client = get_redis_client()
    return redis_client.exists(key) > 0

def is_ip_blocked(ip: str) -> bool:
    """Alias for is_blocked for compatibility"""
    return is_blocked(ip)

@handle_redis_errors(default_return=None)
def get_block_info(ip: str) -> Optional[Dict[str, Any]]:
    """Get block info for an IP"""
    if not ip:
        return None
    key = f"{BLOCK_PREFIX}{ip}"
    redis_client = get_redis_client()
    data = redis_client.get(key)
    if data:
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in block info for {ip}")
            return None
    return None

@handle_redis_errors(default_return=None)
def block_ip(ip: str, reason: str, offense_count: Optional[int] = None) -> Optional[int]:
    """Block an IP with progressive banning"""
    if not ip:
        logger.error("Cannot block: Invalid IP address")
        return None
    
    if offense_count is None:
        offense_count = get_offense_count(ip)
    
    # Calculate ban duration based on offense count
    ban_minutes = get_ban_duration(offense_count)
    ban_label = get_ban_label(offense_count)
    
    key = f"{BLOCK_PREFIX}{ip}"
    redis_client = get_redis_client()
    
    block_data = {
        'reason': reason,
        'offense_count': offense_count,
        'blocked_at': datetime.now().isoformat(),
        'ban_minutes': ban_minutes,
        'ban_label': ban_label
    }
    
    try:
        redis_client.setex(
            key,
            timedelta(minutes=ban_minutes),
            json.dumps(block_data)
        )
        
        # Decrease reputation for blocking
        update_reputation(ip, -20)
        
        logger.warning(
            f"🚫 IP {ip} blocked for {ban_minutes} minutes ({ban_label}). "
            f"Reason: {reason} (Offense #{offense_count})"
        )
        return ban_minutes
    except Exception as e:
        logger.error(f"Failed to block IP {ip}: {e}")
        return None

@handle_redis_errors(default_return=False)
def unblock_ip(ip: str) -> bool:
    """Unblock an IP and clear offenses"""
    if not ip:
        return False
    
    redis_client = get_redis_client()
    
    # Remove block
    block_key = f"{BLOCK_PREFIX}{ip}"
    redis_client.delete(block_key)
    
    # Clear offenses
    offense_key = f"{OFFENSE_PREFIX}{ip}"
    redis_client.delete(offense_key)
    
    # Improve reputation
    update_reputation(ip, 30)
    
    logger.info(f"✅ IP {ip} unblocked by admin")
    return True

@handle_redis_errors(default_return=False)
def record_offense(ip: str, offense_type: str, details: Optional[str] = None) -> int:
    """Record an offense for an IP address"""
    if not ip:
        return 0
    
    redis_client = get_redis_client()
    key = f"{OFFENSE_PREFIX}{ip}"
    
    # Increment offense count
    offense_count = redis_client.incr(key)
    redis_client.expire(key, timedelta(days=30))
    
    # Log the offense
    logger.warning(
        f"⚠️ Offense recorded for {ip}: {offense_type} "
        f"(total: {offense_count}) - {details or ''}"
    )
    
    # Auto-block if offense count exceeds threshold
    if offense_count >= OFFENSE_BLOCK_THRESHOLD:
        block_ip(ip, f"Auto-blocked after {offense_count} offenses: {offense_type}", offense_count)
    
    return offense_count

@handle_redis_errors(default_return=0)
def increment_offense(ip: str) -> int:
    """Increment offense count for an IP"""
    if not ip:
        return 0
    
    redis_client = get_redis_client()
    key = f"{OFFENSE_PREFIX}{ip}"
    count = redis_client.incr(key)
    redis_client.expire(key, timedelta(days=30))
    return count

# ========== RATE LIMIT FUNCTIONS ==========

@handle_redis_errors(default_return=False)
def check_rate_limit(
    ip: str, 
    limit: int = DEFAULT_RATE_LIMIT, 
    window: int = DEFAULT_RATE_WINDOW
) -> bool:
    """Check rate limit for an IP with sliding window"""
    if not ip:
        return False
    
    redis_client = get_redis_client()
    key = f"{RATE_PREFIX}{ip}"
    now = datetime.now().timestamp()
    window_start = now - window
    
    # Use sorted set for sliding window
    pipeline = redis_client.pipeline()
    pipeline.zremrangebyscore(key, 0, window_start)
    pipeline.zadd(key, {str(now): now})
    pipeline.zcard(key)
    pipeline.expire(key, window + 10)
    
    try:
        results = pipeline.execute()
        current_count = results[2]
        
        if current_count > limit:
            record_offense(ip, 'rate_limit_exceeded', f'Requests: {current_count} in {window}s')
            return False
        
        return True
    except Exception as e:
        logger.error(f"Rate limit check failed for {ip}: {e}")
        return True  # Allow on error to avoid blocking legitimate users

@handle_redis_errors(default_return={})
def get_rate_limit_info(ip: str) -> Dict[str, Any]:
    """Get rate limit info for an IP"""
    if not ip:
        return {'error': 'Invalid IP'}
    
    redis_client = get_redis_client()
    key = f"{RATE_PREFIX}{ip}"
    
    try:
        count = redis_client.zcard(key)
        ttl = redis_client.ttl(key)
        return {
            'count': count,
            'ttl': ttl if ttl > 0 else 0,
            'limit': DEFAULT_RATE_LIMIT,
            'window': DEFAULT_RATE_WINDOW
        }
    except Exception as e:
        logger.error(f"Failed to get rate limit info for {ip}: {e}")
        return {'error': 'Failed to get rate limit info'}

# ========== REPUTATION FUNCTIONS ==========

@handle_redis_errors(default_return=DEFAULT_REPUTATION)
def get_reputation(ip: str) -> int:
    """Get IP reputation score"""
    if not ip:
        return DEFAULT_REPUTATION
    
    redis_client = get_redis_client()
    key = f"{REPUTATION_PREFIX}{ip}"
    score = redis_client.get(key)
    
    if score:
        try:
            return int(score)
        except ValueError:
            return DEFAULT_REPUTATION
    return DEFAULT_REPUTATION

@handle_redis_errors(default_return=DEFAULT_REPUTATION)
def update_reputation(ip: str, score_delta: int) -> int:
    """Update IP reputation score"""
    if not ip:
        return DEFAULT_REPUTATION
    
    redis_client = get_redis_client()
    key = f"{REPUTATION_PREFIX}{ip}"
    
    # Get current score or use default
    current = redis_client.get(key)
    score = int(current) if current else DEFAULT_REPUTATION
    
    # Calculate new score with bounds
    new_score = max(MIN_REPUTATION, min(MAX_REPUTATION, score + score_delta))
    
    # Store with TTL
    redis_client.setex(key, timedelta(seconds=REPUTATION_TTL), new_score)
    
    return new_score

# ========== LIST FUNCTIONS ==========

@handle_redis_errors(default_return=[])
def get_blocked_ips() -> List[str]:
    """Get list of all blocked IPs"""
    redis_client = get_redis_client()
    keys = redis_client.keys(f"{BLOCK_PREFIX}*")
    return [key.replace(BLOCK_PREFIX, '') for key in keys]

@handle_redis_errors(default_return={})
def get_blocklist_stats() -> Dict[str, Any]:
    """Get blocklist statistics"""
    blocked_ips = get_blocked_ips()
    total_offenses = 0
    
    for ip in blocked_ips:
        total_offenses += get_offense_count(ip)
    
    return {
        'total_blocked': len(blocked_ips),
        'total_offenses': total_offenses,
        'blocked_ips': blocked_ips
    }

@handle_redis_errors(default_return=0)
def clear_expired_blocks() -> int:
    """Remove expired blocks (Redis handles this automatically)"""
    blocked = get_blocked_ips()
    logger.info(f"🧹 Active blocks: {len(blocked)}")
    return len(blocked)

# ========== LOGIN ATTEMPT FUNCTIONS ==========

@handle_redis_errors(default_return=False)
def check_brute_force(ip: str, username: Optional[str] = None) -> bool:
    """Check for brute force patterns"""
    if not ip:
        return False
    
    redis_client = get_redis_client()
    key = f"{LOGIN_ATTEMPTS_PREFIX}{ip}"
    
    # Get or create counter
    attempts = redis_client.get(key)
    if attempts is None:
        redis_client.setex(key, 900, 1)  # 15 minutes
        return False
    
    attempts = int(attempts)
    redis_client.incr(key)
    
    # If more than threshold attempts in 15 minutes, flag as brute force
    if attempts > BRUTE_FORCE_THRESHOLD:
        record_offense(ip, 'brute_force', f'Attempts: {attempts} in 15 min')
        return True
    
    return False

# ========== INITIALIZATION ==========

logger.info("🔒 WAF Blocklist initialized with Redis")