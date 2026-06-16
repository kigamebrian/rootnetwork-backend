# services/rate_limit_service.py
from flask import request, jsonify, session
from functools import wraps
from datetime import datetime, timedelta
from collections import defaultdict
from models import RateLimitRule, BlockedIP, RateLimitLog
from exts import db
import re

class RateLimitService:
    def __init__(self):
        self.request_cache = defaultdict(list)  # In-memory cache for requests
    
    def is_ip_blocked(self, ip_address):
        """Check if IP is blocked"""
        blocked = BlockedIP.query.filter_by(ip_address=ip_address).first()
        if not blocked:
            return False
        
        if blocked.blocked_until and blocked.blocked_until < datetime.now():
            # Block expired
            db.session.delete(blocked)
            db.session.commit()
            return False
        
        return True
    
    def get_matching_rule(self, endpoint, method):
        """Find matching rate limit rule for the request"""
        rules = RateLimitRule.query.filter_by(is_active=True).order_by(RateLimitRule.priority.desc()).all()
        
        for rule in rules:
            # Check method match
            if rule.method != 'ALL' and rule.method != method:
                continue
            
            # Check endpoint pattern match
            pattern = rule.endpoint_pattern.replace('*', '.*')
            if re.match(pattern, endpoint):
                return rule
        
        return None
    
    def check_rate_limit(self, ip_address, endpoint, method):
        """Check if request exceeds rate limit"""
        if self.is_ip_blocked(ip_address):
            return False, "IP is blocked"
        
        rule = self.get_matching_rule(endpoint, method)
        if not rule:
            return True, None  # No rule applies, allow request
        
        # Clean old requests
        now = datetime.now()
        cutoff = now - timedelta(seconds=rule.time_window)
        key = f"{ip_address}:{rule.id}"
        
        # Filter requests within time window
        self.request_cache[key] = [
            ts for ts in self.request_cache[key] 
            if ts > cutoff
        ]
        
        # Check limit
        if len(self.request_cache[key]) >= rule.limit_count:
            # Log blocked request
            self.log_request(ip_address, endpoint, method, rule.id, True)
            return False, f"Rate limit exceeded. Limit: {rule.limit_count} requests per {rule.time_window} seconds"
        
        # Allow request
        self.request_cache[key].append(now)
        self.log_request(ip_address, endpoint, method, rule.id, False)
        return True, None
    
    def log_request(self, ip_address, endpoint, method, rule_id, was_blocked):
        """Log request for analytics"""
        try:
            log = RateLimitLog(
                ip_address=ip_address,
                endpoint=endpoint,
                method=method,
                rule_id=rule_id,
                was_blocked=was_blocked,
                timestamp=datetime.now()
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"Failed to log rate limit request: {e}")
    
    def block_ip(self, ip_address, reason, blocked_by, minutes=None):
        """Block an IP address"""
        blocked_until = None
        if minutes:
            blocked_until = datetime.now() + timedelta(minutes=minutes)
        
        existing = BlockedIP.query.filter_by(ip_address=ip_address).first()
        if existing:
            existing.reason = reason
            existing.blocked_by = blocked_by
            existing.blocked_until = blocked_until
        else:
            blocked = BlockedIP(
                ip_address=ip_address,
                reason=reason,
                blocked_by=blocked_by,
                blocked_until=blocked_until
            )
            db.session.add(blocked)
        
        db.session.commit()
        
        # Clear cache for this IP
        keys_to_delete = [k for k in self.request_cache.keys() if k.startswith(ip_address)]
        for key in keys_to_delete:
            del self.request_cache[key]
    
    def unblock_ip(self, ip_address):
        """Unblock an IP address"""
        blocked = BlockedIP.query.filter_by(ip_address=ip_address).first()
        if blocked:
            db.session.delete(blocked)
            db.session.commit()
            return True
        return False
    
    def get_rate_limit_status(self, ip_address=None):
        """Get current rate limit status for visual dashboard"""
        status = {
            'rules': [],
            'blocked_ips': [],
            'recent_requests': []
        }
        
        # Get all active rules
        rules = RateLimitRule.query.filter_by(is_active=True).all()
        for rule in rules:
            status['rules'].append(rule.to_dict())
        
        # Get blocked IPs
        blocked_ips = BlockedIP.query.all()
        for ip in blocked_ips:
            status['blocked_ips'].append(ip.to_dict())
        
        # Get recent requests (last 24 hours)
        yesterday = datetime.now() - timedelta(hours=24)
        recent_logs = RateLimitLog.query.filter(
            RateLimitLog.timestamp >= yesterday
        ).order_by(RateLimitLog.timestamp.desc()).limit(100).all()
        
        for log in recent_logs:
            status['recent_requests'].append(log.to_dict())
        
        # Add summary statistics
        status['summary'] = self.get_summary_stats()
        
        # Add current IP status if provided
        if ip_address:
            status['current_ip'] = {
                'ip': ip_address,
                'is_blocked': self.is_ip_blocked(ip_address),
                'request_count': len([
                    ts for ts in self.request_cache.keys() 
                    if ts.startswith(ip_address)
                ])
            }
        
        return status
    
    def get_summary_stats(self):
        """Get summary statistics for the dashboard"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        total_requests_today = RateLimitLog.query.filter(
            RateLimitLog.timestamp >= today
        ).count()
        
        blocked_today = RateLimitLog.query.filter(
            RateLimitLog.timestamp >= today,
            RateLimitLog.was_blocked == True
        ).count()
        
        total_blocked_ips = BlockedIP.query.count()
        
        return {
            'total_requests_today': total_requests_today,
            'blocked_requests_today': blocked_today,
            'blocked_ips_count': total_blocked_ips,
            'active_rules_count': RateLimitRule.query.filter_by(is_active=True).count()
        }

# Initialize service
rate_limit_service = RateLimitService()

# Decorator for rate limiting
def rate_limit_middleware(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        endpoint = request.path
        method = request.method
        
        allowed, message = rate_limit_service.check_rate_limit(ip_address, endpoint, method)
        
        if not allowed:
            return jsonify({
                'error': 'Rate limit exceeded',
                'message': message,
                'retry_after': 60  # Suggest retry after 60 seconds
            }), 429
        
        return f(*args, **kwargs)
    return decorated_function