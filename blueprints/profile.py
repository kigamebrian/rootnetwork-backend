from flask import jsonify, request, session
from models import User, Post
from exts import db, csrf
from funcs import login_required, validate_username, validate_password_strength
from . import profile_bp

@profile_bp.route('/profile', methods=['GET', 'OPTIONS'])
@csrf.exempt
@login_required
def get_user_profile():
    if request.method == 'OPTIONS':
        return '', 200
    
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
    if request.method == 'OPTIONS':
        return '', 200
    
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    try:
        data = request.json
        
        if 'email' in data and data['email'] != user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email'][:254]
        
        if 'username' in data and data['username'] != user.username:
            username_valid, username_msg = validate_username(data['username'])
            if not username_valid:
                return jsonify({'error': username_msg}), 400
            if User.query.filter_by(username=data['username']).first():
                return jsonify({'error': 'Username already exists'}), 400
            user.username = data['username'][:80]
        
        if 'full_name' in data:
            user.full_name = data['full_name'][:120]
        
        if 'blog_title' in data:
            user.blog_title = data['blog_title'][:120]
        
        if 'blog_subtitle' in data:
            user.blog_subtitle = data['blog_subtitle'][:200]
        
        if 'about' in data:
            user.about = data['about'][:500]
        
        if 'password' in data and data['password']:
            password_valid, password_msg = validate_password_strength(data['password'])
            if not password_valid:
                return jsonify({'error': password_msg}), 400
            user.set_password(data['password'])
        
        db.session.commit()
        
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
        return jsonify({'error': str(e)}), 500