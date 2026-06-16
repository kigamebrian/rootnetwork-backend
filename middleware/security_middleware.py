# middleware/security_middleware.py
from functools import wraps
from flask import request, jsonify, session
from services.ids_service import ids

def security_middleware(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"\n{'='*60}")
        print(f"🔍 SECURITY MIDDLEWARE")
        print(f"📍 Path: {request.path}")
        print(f"📝 Method: {request.method}")
        
        # Skip for static files
        if request.path.startswith('/static/'):
            return f(*args, **kwargs)
        
        # Skip for OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        
        # PUBLIC ENDPOINTS - No authentication needed
        public_endpoints = [
            '/api/health', '/api/login', '/api/register', '/api/check-auth',
            '/api/check-registration-status', '/api/csrf-token', '/api/logout',
            '/api/admin-info', '/api/posts', '/api/categories', '/api/about',
            '/api/track/page-view', '/api/track/action'
        ]
        
        # SKIP SECURITY SCANNING FOR POST EDITING/CREATION (content can be long and contain special chars)
        content_endpoints = [
            '/api/admin/posts',           # Create/update posts
            '/api/admin/edit',            # Edit posts
            '/api/admin/create',          # Create posts
        ]
        
        if request.path in public_endpoints:
            print(f"⏭️ Public endpoint, skipping security scan")
            return f(*args, **kwargs)
        
        # Skip security scanning for post content (allow long articles)
        if request.path in content_endpoints or '/api/admin/posts/' in request.path:
            print(f"📝 Content endpoint (post editing), skipping security scan")
            # Still check authentication
            if request.path.startswith('/api/') and 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            return f(*args, **kwargs)
        
        # SKIP SECURITY SCANNING FOR FILE UPLOADS
        if '/upload' in request.path:
            print(f"📁 Upload endpoint, checking auth only")
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            return f(*args, **kwargs)
        
        # Check authentication for all other API endpoints
        if request.path.startswith('/api/'):
            if 'user_id' not in session:
                print(f"❌ Authentication required")
                return jsonify({'error': 'Authentication required'}), 401
            
            print(f"✅ User authenticated: {session.get('user_id')}")
            
            # For modifying requests (POST, PUT, DELETE), check for threats
            if request.method in ['POST', 'PUT', 'DELETE']:
                print(f"🔍 Scanning for threats...")
                
                # Only scan JSON data, skip multipart/form-data
                if request.is_json:
                    request_data = request.get_json()
                    
                    if request_data:
                        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
                        
                        # For post content, only scan title and excerpt, not full content
                        if 'content' in request_data and len(str(request_data.get('content', ''))) > 5000:
                            print(f"📄 Long content detected ({len(str(request_data.get('content')))} chars), skipping content scan")
                            # Only scan title (shorter, more likely to contain real attacks)
                            if 'title' in request_data:
                                threats = ids.scan_request({'title': request_data['title']}, ip_address, request.path)
                            else:
                                threats = []
                        else:
                            threats = ids.scan_request(request_data, ip_address, request.path)
                        
                        print(f"⚠️ Threats found: {len(threats)}")
                        
                        critical_threats = [t for t in threats if t.get('severity') == 'critical']
                        if critical_threats:
                            print(f"🔥 CRITICAL THREAT BLOCKED!")
                            return jsonify({
                                'error': 'Security policy violation',
                                'reason': f'Critical threat detected in title or excerpt: {critical_threats[0]["type"]}'
                            }), 403
                elif request.form and not request.files:
                    request_data = dict(request.form)
                    
                    if request_data:
                        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
                        
                        # Skip scanning for content field
                        if 'content' in request_data and len(str(request_data.get('content', ''))) > 5000:
                            print(f"📄 Long content in form data, skipping content scan")
                            scan_data = {k: v for k, v in request_data.items() if k != 'content'}
                        else:
                            scan_data = request_data
                        
                        threats = ids.scan_request(scan_data, ip_address, request.path)
                        
                        critical_threats = [t for t in threats if t.get('severity') == 'critical']
                        if critical_threats:
                            print(f"🔥 CRITICAL THREAT BLOCKED!")
                            return jsonify({
                                'error': 'Security policy violation',
                                'reason': f'Critical threat detected: {critical_threats[0]["type"]}'
                            }), 403
                else:
                    print(f"📦 Non-JSON, non-form request, skipping scan")
        
        print(f"✅ Request passed security check")
        return f(*args, **kwargs)
    return decorated_function