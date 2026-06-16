# blueprints/waf_admin.py
from flask import Blueprint, jsonify, request, current_app
from functools import wraps
import json
import logging
from typing import Dict, Any

from services.waf_blocklist import (
    is_blocked, unblock_ip, get_block_info, 
    get_rate_limit_info, get_reputation, get_offense_count,
    get_blocked_ips, get_blocklist_stats
)
from services.redis_client import get_redis_client
from services.waf_constants import (
    BLOCK_PREFIX, RATE_PREFIX, REPUTATION_PREFIX, 
    OFFENSE_PREFIX, ALERT_PREFIX, STATS_CACHE_PREFIX,
    STATS_CACHE_TTL
)

logger = logging.getLogger(__name__)

waf_admin_bp = Blueprint('waf_admin', __name__, url_prefix='/api/admin/waf')

# ========== DECORATORS ==========

def handle_waf_errors(f):
    """Decorator to handle WAF-related errors"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"WAF admin error: {e}")
            return jsonify({
                'error': 'WAF operation failed',
                'message': str(e)
            }), 500
    return decorated_function

def validate_ip(f):
    """Decorator to validate IP addresses"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = kwargs.get('ip')
        if ip:
            # Basic IP validation
            parts = ip.split('.')
            if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                return jsonify({
                    'error': 'Invalid IP address format',
                    'ip': ip
                }), 400
        return f(*args, **kwargs)
    return decorated_function

# ========== ROUTES ==========

@waf_admin_bp.route('/status', methods=['GET'])
@handle_waf_errors
def get_waf_status():
    """
    Get WAF status for an IP
    Query params: ip (optional, defaults to requestor's IP)
    """
    ip = request.args.get('ip')
    if not ip:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    if not ip:
        return jsonify({'error': 'Unable to determine IP address'}), 400
    
    from services.waf_engine import WAFEngine
    
    try:
        status = WAFEngine.get_status(ip)
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"Failed to get WAF status for {ip}: {e}")
        return jsonify({
            'error': 'Failed to get WAF status',
            'ip': ip,
            'message': str(e)
        }), 500

@waf_admin_bp.route('/blocked-ips', methods=['GET'])
@handle_waf_errors
def get_blocked_ips_route():
    """
    Get all blocked IPs with pagination
    Query params: page (default 1), per_page (default 50)
    """
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 200:
            per_page = 50
        
        redis_client = get_redis_client()
        if not redis_client:
            return jsonify({'error': 'Redis unavailable'}), 500
        
        # Get all blocked keys
        keys = redis_client.keys(f"{BLOCK_PREFIX}*")
        total = len(keys)
        
        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        paginated_keys = keys[start:end]
        
        blocked = []
        for key in paginated_keys:
            ip = key.replace(BLOCK_PREFIX, '')
            data = redis_client.get(key)
            blocked.append({
                'ip': ip,
                'info': json.loads(data) if data else {},
                'ttl': redis_client.ttl(key)
            })
        
        return jsonify({
            'total': total,
            'page': page,
            'per_page': per_page,
            'pages': (total + per_page - 1) // per_page if total > 0 else 0,
            'items': blocked
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get blocked IPs: {e}")
        return jsonify({'error': 'Failed to retrieve blocked IPs'}), 500

@waf_admin_bp.route('/unblock/<ip>', methods=['POST'])
@handle_waf_errors
@validate_ip
def unblock_ip_route(ip):
    """Unblock an IP address"""
    if not ip:
        return jsonify({'error': 'IP address is required'}), 400
    
    # Check if IP is actually blocked
    if not is_blocked(ip):
        return jsonify({
            'error': f'IP {ip} is not currently blocked',
            'ip': ip
        }), 404
    
    try:
        if unblock_ip(ip):
            logger.info(f"✅ IP {ip} unblocked by admin")
            return jsonify({
                'message': f'IP {ip} unblocked successfully',
                'ip': ip,
                'unblocked': True
            }), 200
        else:
            return jsonify({
                'error': 'Failed to unblock IP',
                'ip': ip
            }), 500
    except Exception as e:
        logger.error(f"Failed to unblock {ip}: {e}")
        return jsonify({
            'error': 'Unblock operation failed',
            'message': str(e)
        }), 500

@waf_admin_bp.route('/stats', methods=['GET'])
@handle_waf_errors
def get_waf_stats():
    """
    Get WAF statistics
    Query params: force (boolean, default false) - bypass cache
    """
    try:
        force_refresh = request.args.get('force', 'false').lower() == 'true'
        cache_key = f"{STATS_CACHE_PREFIX}admin_stats"
        
        redis_client = get_redis_client()
        if not redis_client:
            return jsonify({'error': 'Redis unavailable'}), 500
        
        # Check cache
        if not force_refresh:
            cached_stats = redis_client.get(cache_key)
            if cached_stats:
                try:
                    stats = json.loads(cached_stats)
                    stats['cached'] = True
                    return jsonify(stats), 200
                except json.JSONDecodeError:
                    pass
        
        # Get fresh stats
        stats = {
            'blocked': len(redis_client.keys(f"{BLOCK_PREFIX}*")),
            'rate_limits': len(redis_client.keys(f"{RATE_PREFIX}*")),
            'reputations': len(redis_client.keys(f"{REPUTATION_PREFIX}*")),
            'offenses': len(redis_client.keys(f"{OFFENSE_PREFIX}*")),
            'alerts': len(redis_client.keys(f"{ALERT_PREFIX}*")),
            'cached': False,
            'timestamp': current_app.config.get('WAF_STATS_TIME', None)
        }
        
        # Cache stats
        try:
            redis_client.setex(cache_key, STATS_CACHE_TTL, json.dumps(stats))
        except Exception as e:
            logger.warning(f"Failed to cache WAF stats: {e}")
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Failed to get WAF stats: {e}")
        return jsonify({
            'error': 'Failed to retrieve statistics',
            'message': str(e)
        }), 500

@waf_admin_bp.route('/offenses/<ip>', methods=['GET'])
@handle_waf_errors
@validate_ip
def get_ip_offenses(ip):
    """Get detailed offense information for an IP"""
    if not ip:
        return jsonify({'error': 'IP address is required'}), 400
    
    try:
        info = {
            'ip': ip,
            'offense_count': get_offense_count(ip),
            'is_blocked': is_blocked(ip),
            'reputation': get_reputation(ip),
            'rate_limit': get_rate_limit_info(ip)
        }
        
        if is_blocked(ip):
            info['block_info'] = get_block_info(ip)
        
        return jsonify(info), 200
        
    except Exception as e:
        logger.error(f"Failed to get offense info for {ip}: {e}")
        return jsonify({
            'error': 'Failed to retrieve offense information',
            'message': str(e)
        }), 500

@waf_admin_bp.route('/blocklist/stats', methods=['GET'])
@handle_waf_errors
def get_blocklist_stats_route():
    """Get blocklist statistics"""
    try:
        stats = get_blocklist_stats()
        return jsonify(stats), 200
    except Exception as e:
        logger.error(f"Failed to get blocklist stats: {e}")
        return jsonify({
            'error': 'Failed to retrieve blocklist statistics',
            'message': str(e)
        }), 500

@waf_admin_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for WAF"""
    try:
        redis_client = get_redis_client()
        redis_available = redis_client is not None and redis_client.ping()
        
        status = {
            'status': 'healthy' if redis_available else 'degraded',
            'redis': 'connected' if redis_available else 'disconnected',
            'timestamp': datetime.now().isoformat()
        }
        
        if not redis_available:
            status['message'] = 'Redis connection failed'
            return jsonify(status), 503
        
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500