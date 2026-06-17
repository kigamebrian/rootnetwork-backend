# blueprints/category.py
from flask import jsonify, request, session, make_response
from models import Category, User
from exts import db, csrf
from funcs import login_required, get_session_id, super_admin_required
from middleware.security_middleware import security_middleware
from . import category_bp
from datetime import datetime
from services.logging_service import logger   # <-- ADDED for security logging

MAX_CATEGORIES = 5  # Maximum categories allowed for navigation

# ========== HELPER FOR CORS ==========
def get_allowed_origin():
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork1.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    return origin if origin in allowed_origins else 'https://rootnetwork1.netlify.app'

# ========== ANALYTICS TRACKING (optional) ==========
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

# ========== PUBLIC ENDPOINTS ==========

@category_bp.route('/nav-categories', methods=['GET'])
@csrf.exempt
def get_nav_categories():
    try:
        categories = Category.query.order_by(Category.name.asc()).limit(MAX_CATEGORIES).all()
        return jsonify([{
            'id': c.id,
            'name': c.name,
            'slug': c.name.lower().replace(' ', '-'),
            'post_count': c.posts.count()
        } for c in categories]), 200
    except Exception as e:
        print(f"Error in get_nav_categories: {e}")
        return jsonify([]), 200

# ========== ADMIN ENDPOINTS ==========

@category_bp.route('/categories', methods=['GET'])
@csrf.exempt
def get_admin_categories():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        categories = Category.query.order_by(Category.name.asc()).all()
        return jsonify([{
            'id': c.id,
            'name': c.name,
            'post_count': c.posts.count()
        } for c in categories]), 200
    except Exception as e:
        print(f"Error in get_admin_categories: {e}")
        return jsonify({'error': str(e)}), 500

@category_bp.route('/categories/limit', methods=['GET'])
@csrf.exempt
@super_admin_required
def get_category_limit():
    try:
        current_count = Category.query.count()
        return jsonify({
            'max_categories': MAX_CATEGORIES,
            'current_count': current_count,
            'can_add': current_count < MAX_CATEGORIES,
            'remaining': MAX_CATEGORIES - current_count
        }), 200
    except Exception as e:
        print(f"Error in get_category_limit: {e}")
        return jsonify({'error': str(e)}), 500

@category_bp.route('/categories', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def create_category():
    # Handle preflight OPTIONS
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        user = User.query.get(session['user_id'])
        if not user.is_super_admin:
            return jsonify({'error': 'Only super admin can create categories'}), 403

        current_count = Category.query.count()
        if current_count >= MAX_CATEGORIES:
            return jsonify({
                'error': f'Maximum {MAX_CATEGORIES} categories allowed. Delete a category before adding a new one.'
            }), 400

        data = request.json
        if not data or 'name' not in data or not data['name'].strip():
            return jsonify({'error': 'Category name is required'}), 400

        existing = Category.query.filter_by(name=data['name'].strip()).first()
        if existing:
            return jsonify({'error': 'Category already exists'}), 400

        category = Category(name=data['name'].strip())
        db.session.add(category)
        db.session.commit()

        # --- ANALYTICS tracking ---
        track_action(
            action_type='create_category',
            action_details=f'Created category: {category.name}',
            target_id=category.id,
            target_type='category'
        )

        # --- SECURITY LOGGING: record in ActivityLog ---
        logger.log_activity(
            user_id=user.id,
            username=user.username,
            action='create_category',
            action_details=f'Created category: {category.name}',
            endpoint='/api/admin/categories',
            method='POST',
            status=201
        )

        return jsonify({
            'message': 'Category created successfully',
            'id': category.id,
            'current_count': Category.query.count(),
            'remaining': MAX_CATEGORIES - Category.query.count()
        }), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_category: {e}")
        return jsonify({'error': str(e)}), 500

@category_bp.route('/categories/<int:category_id>', methods=['DELETE', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def delete_category(category_id):
    # Handle preflight OPTIONS
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        user = User.query.get(session['user_id'])
        if not user.is_super_admin:
            return jsonify({'error': 'Only super admin can delete categories'}), 403

        category = Category.query.get_or_404(category_id)
        category_name = category.name

        if category.posts.count() > 0:
            return jsonify({'error': 'Cannot delete category with existing posts. Reassign posts first.'}), 400

        db.session.delete(category)
        db.session.commit()

        # --- ANALYTICS tracking ---
        track_action(
            action_type='delete_category',
            action_details=f'Deleted category: {category_name}',
            target_id=category_id,
            target_type='category'
        )

        # --- SECURITY LOGGING: record in ActivityLog ---
        logger.log_activity(
            user_id=user.id,
            username=user.username,
            action='delete_category',
            action_details=f'Deleted category: {category_name}',
            endpoint=f'/api/admin/categories/{category_id}',
            method='DELETE',
            status=200
        )

        return jsonify({
            'message': 'Category deleted successfully',
            'current_count': Category.query.count(),
            'remaining': MAX_CATEGORIES - Category.query.count()
        }), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in delete_category: {e}")
        return jsonify({'error': str(e)}), 500
