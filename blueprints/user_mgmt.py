# blueprints/user_mgmt.py - FINAL (with 500 error fix)
from flask import jsonify, request, session, make_response
from models import User
from exts import db, csrf
from funcs import super_admin_required, validate_username, validate_password_strength, get_session_id
from middleware.security_middleware import security_middleware
from . import user_mgmt_bp
from datetime import datetime
from services import send_welcome_email_background

# ========== HELPER FUNCTION FOR CORS ==========
def get_allowed_origin():
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    return origin if origin in allowed_origins else 'https://rootnetwork.netlify.app'

def track_action(action_type, action_details, target_id, target_type):
    try:
        from models import UserAction
        session_id = get_session_id()
        user_id = session.get('user_id')
        action = UserAction(
            user_id=user_id,
            session_id=session_id,
            action_type=action_type[:50],
            action_details=action_details[:500],
            target_id=target_id,
            target_type=target_type[:50],
            timestamp=datetime.now()
        )
        db.session.add(action)
        db.session.commit()
    except Exception as e:
        print(f"Failed to track action: {e}")

# ========== GET USERS (FIXED 500 ERROR) ==========
@user_mgmt_bp.route('/users', methods=['GET'])
@csrf.exempt
@super_admin_required
def get_users():
    try:
        users = User.query.all()
        result = []
        for u in users:
            # Safely get post count – check if relationship exists
            if hasattr(u, 'posts'):
                post_count = u.posts.count()
            else:
                post_count = 0
            result.append({
                'id': u.id,
                'email': u.email,
                'username': u.username,
                'full_name': u.full_name,
                'profile_image': u.profile_image,
                'is_super_admin': u.is_super_admin,
                'is_active': u.is_active,
                'created_at': u.created_at.isoformat() if u.created_at else None,
                'last_login': u.last_login.isoformat() if u.last_login else None,
                'post_count': post_count
            })
        return jsonify(result), 200
    except Exception as e:
        print(f"Error in get_users: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ========== CREATE USER ==========
@user_mgmt_bp.route('/users', methods=['POST'])
@csrf.exempt
@super_admin_required
@security_middleware
def create_user():
    try:
        data = request.json
        if not data.get('email'):
            return jsonify({'error': 'Email is required'}), 400
        if not data.get('username'):
            return jsonify({'error': 'Username is required'}), 400
        if not data.get('password'):
            return jsonify({'error': 'Password is required'}), 400

        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400

        username_valid, username_msg = validate_username(data['username'])
        if not username_valid:
            return jsonify({'error': username_msg}), 400

        password_valid, password_msg = validate_password_strength(data['password'])
        if not password_valid:
            return jsonify({'error': password_msg}), 400

        user = User(
            email=data['email'][:254],
            username=data['username'][:80],
            full_name=data.get('full_name', '')[:120],
            is_super_admin=data.get('is_super_admin', False),
            is_active=data.get('is_active', True),
            blog_title=data.get('blog_title', 'My Blog')[:120],
            blog_subtitle=data.get('blog_subtitle', 'Welcome to my blog')[:200],
            about=data.get('about', '')[:500]
        )
        user.set_password(data['password'])

        db.session.add(user)
        db.session.commit()

        send_welcome_email_background(
            email=user.email,
            name=user.full_name,
            username=user.username,
            password=data['password']
        )

        track_action(
            action_type='create_user',
            action_details=f'Created user: {user.username} (Role: {"Admin" if user.is_super_admin else "User"})',
            target_id=user.id,
            target_type='user'
        )

        return jsonify({'message': 'User created successfully. Welcome email sent.', 'id': user.id}), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error creating user: {e}")
        return jsonify({'error': str(e)}), 500

# ========== UPDATE USER ==========
@user_mgmt_bp.route('/users/<int:user_id>', methods=['PUT'])
@csrf.exempt
@super_admin_required
@security_middleware
def update_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        data = request.json
        changes = []

        if 'email' in data and data['email'] != user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email already exists'}), 400
            changes.append(f"email: {user.email} -> {data['email']}")
            user.email = data['email'][:254]

        if 'username' in data and data['username'] != user.username:
            username_valid, username_msg = validate_username(data['username'])
            if not username_valid:
                return jsonify({'error': username_msg}), 400
            if User.query.filter_by(username=data['username']).first():
                return jsonify({'error': 'Username already exists'}), 400
            changes.append(f"username: {user.username} -> {data['username']}")
            user.username = data['username'][:80]

        if 'full_name' in data and data['full_name'] != user.full_name:
            changes.append(f"full_name: {user.full_name} -> {data['full_name']}")
            user.full_name = data['full_name'][:120]

        if 'is_active' in data and data['is_active'] != user.is_active:
            changes.append(f"active status: {user.is_active} -> {data['is_active']}")
            user.is_active = data['is_active']

        if 'is_super_admin' in data and data['is_super_admin'] != user.is_super_admin:
            if user.id == session.get('user_id'):
                return jsonify({'error': 'Cannot change your own super admin status'}), 400
            changes.append(f"admin role: {user.is_super_admin} -> {data['is_super_admin']}")
            user.is_super_admin = data['is_super_admin']

        if 'password' in data and data['password']:
            password_valid, password_msg = validate_password_strength(data['password'])
            if not password_valid:
                return jsonify({'error': password_msg}), 400
            changes.append("password changed")
            user.set_password(data['password'])

        db.session.commit()

        if changes:
            track_action(
                action_type='update_user',
                action_details=f'Updated user {user.username}: {", ".join(changes)}',
                target_id=user_id,
                target_type='user'
            )

        return jsonify({'message': 'User updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ========== DELETE USER ==========
@user_mgmt_bp.route('/users/<int:user_id>', methods=['DELETE'])
@csrf.exempt
@super_admin_required
@security_middleware
def delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        username = user.username

        if user.id == session.get('user_id'):
            return jsonify({'error': 'Cannot delete your own account'}), 400

        db.session.delete(user)
        db.session.commit()

        track_action(
            action_type='delete_user',
            action_details=f'Deleted user: {username}',
            target_id=user_id,
            target_type='user'
        )

        return jsonify({'message': 'User deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
