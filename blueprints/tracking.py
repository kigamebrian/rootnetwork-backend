# blueprints/tracking.py - Fixed CORS
from flask import jsonify, request, session, make_response
from models import PageView, UserAction
from exts import db, csrf
from funcs import get_session_id
from services.geo_service import get_geolocation, get_cache_stats
from . import tracking_bp
from datetime import datetime

# ========== HELPER FUNCTION FOR CORS ==========
def get_allowed_origin():
    """Return the appropriate allowed origin based on request"""
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork1.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    if origin in allowed_origins:
        return origin
    return 'https://rootnetwork1.netlify.app'  # Default

@tracking_bp.route('/page-view', methods=['POST', 'OPTIONS'])
@csrf.exempt
def track_page_view():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200
    
    try:
        data = request.json
        session_id = get_session_id()
        user_id = session.get('user_id')
        user_agent = request.headers.get('User-Agent', '')
        
        # Extract the first IP from X-Forwarded-For
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            ip_address = forwarded.split(',')[0].strip()
        else:
            ip_address = request.remote_addr
        
        country, city = get_geolocation(ip_address)
        
        page_view = PageView(
            user_id=user_id,
            session_id=session_id,
            page_url=data.get('url', ''),
            page_type=data.get('page_type', ''),
            post_id=data.get('post_id'),
            referrer=data.get('referrer', ''),
            user_agent=user_agent[:500],
            ip_address=ip_address[:50],
            country=country[:100] if country else None,
            city=city[:100] if city else None,
            timestamp=datetime.now()
        )
        db.session.add(page_view)
        db.session.commit()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Tracking error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 200

@tracking_bp.route('/action', methods=['POST', 'OPTIONS'])
@csrf.exempt
def track_user_action():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200
    
    try:
        data = request.json
        session_id = get_session_id()
        user_id = session.get('user_id')
        
        action = UserAction(
            user_id=user_id,
            session_id=session_id,
            action_type=data.get('action_type', '')[:50],
            action_details=data.get('action_details', '')[:500],
            target_id=data.get('target_id'),
            target_type=data.get('target_type', '')[:50],
            timestamp=datetime.now()
        )
        db.session.add(action)
        db.session.commit()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Track action error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 200

# ========== DEBUG ENDPOINTS ==========

@tracking_bp.route('/debug/geo', methods=['GET', 'OPTIONS'])
@csrf.exempt
def debug_geo():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200
    
    """Debug endpoint to test geolocation"""
    from services.geo_service import get_geolocation, is_private_ip, get_public_ip, get_cache_stats
    
    results = []
    
    # Test with different IPs
    test_ips = [
        request.remote_addr,
        request.headers.get('X-Forwarded-For', ''),
        '8.8.8.8',  # Google DNS
        '1.1.1.1',  # Cloudflare
        '192.168.1.1',  # Private IP
        '10.0.0.1',  # Private IP
    ]
    
    for ip in test_ips:
        if ip:
            clean_ip = get_public_ip(ip)
            is_private = is_private_ip(clean_ip)
            country, city = get_geolocation(ip)
            results.append({
                'original_ip': ip,
                'cleaned_ip': clean_ip,
                'is_private': is_private,
                'country': country,
                'city': city
            })
    
    cache_stats = get_cache_stats()
    
    return jsonify({
        'results': results,
        'cache_size': cache_stats.get('cache_size', 0),
        'cache_keys': cache_stats.get('cache_keys', [])
    }), 200

@tracking_bp.route('/debug/recent', methods=['GET', 'OPTIONS'])
@csrf.exempt
def debug_recent():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200
    
    """Debug endpoint to see recent page views"""
    recent = PageView.query.order_by(PageView.id.desc()).limit(20).all()
    
    return jsonify([{
        'id': v.id,
        'ip_address': v.ip_address,
        'country': v.country,
        'city': v.city,
        'page_type': v.page_type,
        'timestamp': v.timestamp.isoformat() if v.timestamp else None
    } for v in recent]), 200
