# backend/middleware/waf_middleware.py
from functools import wraps
from flask import request, jsonify, current_app
import logging
from typing import Dict, Any, List, Optional

from services.waf_engine import WAFEngine, is_request_safe
from services.waf_blocklist import is_ip_blocked, get_offense_count, block_ip, record_offense

logger = logging.getLogger(__name__)

def get_client_ip() -> str:
    """Get client IP address from request headers"""
    # Check for forwarded IP
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded.split(',')[0].strip()
    
    # Check for real IP
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    
    # Fallback to remote addr
    return request.remote_addr or '0.0.0.0'

def waf_protect(f):
    """Decorator to protect endpoints with WAF"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Get client IP
            ip_address = get_client_ip()
            
            # Get endpoint info
            endpoint = request.path
            method = request.method
            
            # Check if IP is blocked
            if is_ip_blocked(ip_address):
                logger.warning(f"🚫 Blocked request from {ip_address} to {endpoint}")
                return jsonify({
                    'error': 'Access denied',
                    'message': 'Your IP has been blocked due to suspicious activity'
                }), 403
            
            # Get request data
            request_data = None
            if request.is_json:
                try:
                    request_data = request.get_json(silent=True)
                except Exception as e:
                    logger.error(f"Failed to parse JSON: {e}")
            
            if not request_data and request.form:
                request_data = dict(request.form)
            
            # Scan request
            is_safe, threats = is_request_safe(
                request_data=request_data,
                ip=ip_address,
                endpoint=endpoint,
                user_agent=request.headers.get('User-Agent'),
                method=method
            )
            
            if not is_safe:
                # Find critical threats
                critical_threats = [
                    t for t in threats 
                    if t.get('severity') in ['critical', 'high']
                ]
                
                # Check if IP should be blocked
                if critical_threats:
                    offense_count = get_offense_count(ip_address)
                    if offense_count >= 3:
                        block_ip(
                            ip_address, 
                            f"Blocked after {offense_count} offenses: {critical_threats[0].get('type')}",
                            offense_count
                        )
                    
                    # Log the incident
                    logger.warning(
                        f"⚠️ Security violation from {ip_address} at {endpoint}: "
                        f"{critical_threats[0].get('type')}"
                    )
                    
                    # Record offense
                    record_offense(
                        ip_address,
                        'security_violation',
                        f"{critical_threats[0].get('type')} at {endpoint}"
                    )
                
                return jsonify({
                    'error': 'Security policy violation',
                    'reason': f'Threat detected: {critical_threats[0].get("type") if critical_threats else "security violation"}',
                    'message': 'This incident has been logged.',
                    'reference': f'WAF-{hash(ip_address + endpoint) % 10000:04d}'
                }), 403
            
            # Request is safe, proceed
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"WAF protection error: {e}")
            # On error, allow the request but log it
            current_app.logger.error(f"WAF error: {e}")
            return f(*args, **kwargs)
    
    return decorated_function

def waf_protected(f):
    """Alias for waf_protect for backward compatibility"""
    return waf_protect(f)

# ========== MIDDLEWARE FOR FLASK APP ==========

class WAFMiddleware:
    """Flask middleware for WAF protection"""
    
    def __init__(self, app):
        self.app = app
        self.setup_waf()
    
    def setup_waf(self):
        """Setup WAF middleware"""
        # Log WAF initialization
        logger.info("🛡️ WAF Middleware initialized")
    
    def __call__(self, environ, start_response):
        """Process request through WAF"""
        # This is a WSGI middleware implementation
        # It can be used to intercept all requests at WSGI level
        
        # Get client IP
        ip_address = environ.get('HTTP_X_FORWARDED_FOR', environ.get('REMOTE_ADDR', '0.0.0.0'))
        if ip_address and ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        
        # Check if IP is blocked
        if is_ip_blocked(ip_address):
            start_response('403 Forbidden', [('Content-Type', 'application/json')])
            return [b'{"error":"Access denied","message":"Your IP has been blocked"}']
        
        # Continue with normal request processing
        return self.app(environ, start_response)