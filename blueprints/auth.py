# blueprints/auth.py - FINAL (SYNTAX FIXED)
from flask import jsonify, request, session, make_response
from models import User
from exts import db, csrf
from funcs import validate_username, validate_password_strength, limiter
from services.ids_service import ids
from services.logging_service import logger
from . import auth_bp
from datetime import datetime

# ========== HELPER FUNCTION FOR CORS ==========
def get_allowed_origin():
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    return origin if origin in allowed_origins else 'https://rootnetwork.netlify.app'

# ---------- REGISTER ----------
@auth_bp.route('/register', methods=['POST', 'OPTIONS'])
@csrf.exempt
@limiter.limit("5 per hour")
def register():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    data = request.json
    user_count = User.query.count()

    email = data.get('email', '')[:120]
    username = data.get('username', '')[:50]
    full_name = data.get('full_name', '')[:100]
    blog_title = data.get('blog_title', 'My Blog')[:120]
    blog_subtitle = data.get('blog_subtitle', 'Welcome to my blog')[:200]
    about = data.get('about', '')[:500]

    username_valid, username_msg = validate_username(username)
    if not username_valid:
        return jsonify({'error': username_msg}), 400

    password_valid, password_msg = validate_password_strength(data.get('password', ''))
    if not password_valid:
        return jsonify({'error': password_msg}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already registered'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 400

    user = User(
        email=email, username=username, full_name=full_name,
        is_super_admin=(user_count == 0), is_active=True,
        blog_title=blog_title, blog_subtitle=blog_subtitle, about=about
    )
    user.set_password(data['password'])

    db.session.add(user)
    db.session.commit()

    # Set session
    session.clear()
    session.permanent = True
    session['user_id'] = user.id
    session['username'] = user.username
    session['email'] = user.email
    session['is_super_admin'] = user.is_super_admin
    session.modified = True   # force save

    return jsonify({
        'message': 'Registration successful',
        'is_super_admin': user.is_super_admin,
        'user': {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'full_name': user.full_name,
            'profile_image': user.profile_image,
            'is_super_admin': user.is_super_admin
        }
    }), 201

# ---------- CHECK-AUTH ----------
@auth_bp.route('/check-auth', methods=['GET', 'OPTIONS'])
@csrf.exempt
def check_auth():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            session.modified = True
            return jsonify({
                'authenticated': True,
                'username': user.username,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'full_name': user.full_name,
                    'profile_image': user.profile_image,
                    'is_super_admin': user.is_super_admin
                }
            })
    return jsonify({'authenticated': False}), 401

# ---------- LOGIN ----------
@auth_bp.route('/login', methods=['POST', 'OPTIONS'])
@csrf.exempt
@limiter.limit("10 per minute")
def login():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    data = request.json
    identifier = data.get('identifier', '')
    password = data.get('password', '')
    user = User.query.filter_by(email=identifier).first() or User.query.filter_by(username=identifier).first()

    if not user:
        ids.log_failed_attempt(identifier, request.headers.get('X-Forwarded-For', request.remote_addr), request.headers.get('User-Agent', ''))
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account is disabled'}), 401

    if user.validate_password(password):
        user.last_login = datetime.now()
        db.session.commit()

        # SESSION: only these lines – NO manual cookie
        session.clear()
        session.permanent = True
        session['user_id'] = user.id
        session['username'] = user.username
        session['email'] = user.email
        session['is_super_admin'] = user.is_super_admin
        session.modified = True

        logger.log_login(user, success=True)

        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'full_name': user.full_name,
                'profile_image': user.profile_image,
                'is_super_admin': user.is_super_admin,
                'blog_title': user.blog_title,
                'blog_subtitle': user.blog_subtitle
            }
        })

    ids.log_failed_attempt(identifier, request.headers.get('X-Forwarded-For', request.remote_addr), request.headers.get('User-Agent', ''))
    return jsonify({'error': 'Invalid credentials'}), 401

# ---------- CHECK REGISTRATION STATUS ----------
@auth_bp.route('/check-registration-status', methods=['GET', 'OPTIONS'])
@csrf.exempt
def check_registration_status():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200
    user_count = User.query.count()
    return jsonify({'registration_open': user_count == 0, 'has_users': user_count > 0})

# ---------- LOGOUT ----------
@auth_bp.route('/logout', methods=['POST', 'OPTIONS'])
@csrf.exempt
def logout():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            logger.log_logout(user)

    session.clear()
    return jsonify({'success': True})

# ---------- ADMIN INFO ----------
@auth_bp.route('/admin-info', methods=['GET', 'OPTIONS'])
@csrf.exempt
def admin_info():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        return response, 200

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            return jsonify({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'profile_image': user.profile_image,
                'blog_title': user.blog_title or 'My Blog',
                'blog_subtitle': user.blog_subtitle or '',
                'about': user.about or '',
                'is_super_admin': user.is_super_admin
            })
    return jsonify({
        'username': 'Admin',
        'blog_title': 'My Blog',
        'blog_subtitle': '',
        'name': 'Admin',
        'about': '',
        'is_super_admin': False
    })

# ---------- DEBUG SESSION ----------
@auth_bp.route('/debug/session', methods=['GET'])
@csrf.exempt
def debug_session():
    return jsonify({
        'session_keys': list(session.keys()),
        'session_data': {k: str(v) for k, v in session.items()},
        'has_user_id': 'user_id' in session,
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'cookie_header': request.headers.get('Cookie', 'None')
    })
