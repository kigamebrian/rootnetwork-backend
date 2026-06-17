# blueprints/profile.py
from flask import jsonify, request, session, make_response
from models import User, Post
from exts import db, csrf
from funcs import login_required, validate_username, validate_password_strength
from . import profile_bp
from services.logging_service import logger   # <-- ADDED for security logging

# ========== HELPER FOR CORS ==========
def get_allowed_origin():
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork1.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    return origin if origin in allowed_origins else 'https://rootnetwork1.netlify.app'

@profile_bp.route('/profile', methods=['GET', 'OPTIONS'])
@csrf.exempt
@login_required
def get_user_profile():
    # Handle preflight OPTIONS
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    user_posts = Post.query.filter_by(author_id=user.id).order_by(Post.timestamp.desc()).all()

    return jsonify({
        'id': user.id,
        'email': user.email,
        'username': user.username,
        'full_name': user.full_name,
        'profile_image': user.profile_image,
        'is_super_admin': user.is_super_admin,
        'is_active': user.is_active,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'blog_title': user.blog_title,
        'blog_subtitle': user.blog_subtitle,
        'about': user.about,
        'post_count': len(user_posts),
        'posts': [{
            'id': post.id,
            'title': post.title,
            'slug': post.slug,
            'image': post.image,
            'timestamp': post.timestamp.isoformat(),
            'comment_count': post.comments.count(),
            'content_preview': post.content[:150] + '...' if len(post.content) > 150 else post.content
        } for post in user_posts]
    }), 200

@profile_bp.route('/profile', methods=['PUT', 'OPTIONS'])
@csrf.exempt
@login_required
def update_user_profile():
    # Handle preflight OPTIONS
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'PUT, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    try:
        data = request.json
        changes = []   # collect changes for logging

        # Email
        if 'email' in data and data['email'] != user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email already exists'}), 400
            changes.append(f"email: {user.email} -> {data['email']}")
            user.email = data['email'][:254]

        # Username
        if 'username' in data and data['username'] != user.username:
            username_valid, username_msg = validate_username(data['username'])
            if not username_valid:
                return jsonify({'error': username_msg}), 400
            if User.query.filter_by(username=data['username']).first():
                return jsonify({'error': 'Username already exists'}), 400
            changes.append(f"username: {user.username} -> {data['username']}")
            user.username = data['username'][:80]

        # Full name
        if 'full_name' in data:
            if data['full_name'] != user.full_name:
                changes.append(f"full_name: {user.full_name} -> {data['full_name']}")
                user.full_name = data['full_name'][:120]

        # Blog title
        if 'blog_title' in data:
            if data['blog_title'] != user.blog_title:
                changes.append(f"blog_title: {user.blog_title} -> {data['blog_title']}")
                user.blog_title = data['blog_title'][:120]

        # Blog subtitle
        if 'blog_subtitle' in data:
            if data['blog_subtitle'] != user.blog_subtitle:
                changes.append(f"blog_subtitle: {user.blog_subtitle} -> {data['blog_subtitle']}")
                user.blog_subtitle = data['blog_subtitle'][:200]

        # About
        if 'about' in data:
            if data['about'] != user.about:
                changes.append("about updated")
                user.about = data['about'][:500]

        # Password
        if 'password' in data and data['password']:
            password_valid, password_msg = validate_password_strength(data['password'])
            if not password_valid:
                return jsonify({'error': password_msg}), 400
            changes.append("password changed")
            user.set_password(data['password'])

        # Only commit if there were changes
        if changes:
            db.session.commit()

            # --- SECURITY LOGGING: log profile update ---
            logger.log_activity(
                user_id=user.id,
                username=user.username,
                action='update_profile',
                action_details=f"Updated profile: {', '.join(changes)}",
                endpoint='/api/profile',
                method='PUT',
                status=200
            )
        else:
            # No changes made
            return jsonify({'message': 'No changes to update'}), 200

        return jsonify({
            'message': 'Profile updated successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'full_name': user.full_name,
                'profile_image': user.profile_image,
                'is_super_admin': user.is_super_admin,
                'blog_title': user.blog_title,
                'blog_subtitle': user.blog_subtitle,
                'about': user.about
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error updating profile: {e}")
        return jsonify({'error': str(e)}), 500
