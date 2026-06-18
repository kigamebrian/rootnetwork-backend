# blueprints/admin_subscribers.py
from flask import Blueprint, request, jsonify, make_response
from models import Subscriber, db
from services.email_service import send_verification_email
from funcs import super_admin_required
from exts import csrf
from datetime import datetime, timezone
import logging

admin_subscribers_bp = Blueprint('admin_subscribers', __name__, url_prefix='/api/admin/subscribers')
logger = logging.getLogger(__name__)

# ========== HELPER FOR CORS ==========
def get_allowed_origin():
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork1.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    return origin if origin in allowed_origins else 'https://rootnetwork1.netlify.app'

# ---------- LIST SUBSCRIBERS ----------
@admin_subscribers_bp.route('', methods=['GET', 'OPTIONS'])
@super_admin_required
def list_subscribers():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '').strip()

    query = Subscriber.query
    if search:
        query = query.filter(Subscriber.email.ilike(f'%{search}%'))

    paginated = query.order_by(Subscriber.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    result = {
        'subscribers': [{
            'id': s.id,
            'email': s.email,
            'verified': s.verified,
            'is_active': s.is_active(),
            'preferences': s.preferences,
            'subscribed_at': s.subscribed_at.isoformat() if s.subscribed_at else None,
            'unsubscribed_at': s.unsubscribed_at.isoformat() if s.unsubscribed_at else None,
            'last_sent_at': s.last_sent_at.isoformat() if s.last_sent_at else None,
        } for s in paginated.items],
        'total': paginated.total,
        'page': paginated.page,
        'per_page': paginated.per_page,
        'pages': paginated.pages,
    }
    return jsonify(result), 200

# ---------- GET SINGLE SUBSCRIBER ----------
@admin_subscribers_bp.route('/<int:subscriber_id>', methods=['GET', 'OPTIONS'])
@super_admin_required
def get_subscriber(subscriber_id):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    subscriber = Subscriber.query.get_or_404(subscriber_id)
    return jsonify({
        'id': subscriber.id,
        'email': subscriber.email,
        'verified': subscriber.verified,
        'is_active': subscriber.is_active(),
        'preferences': subscriber.preferences,
        'subscribed_at': subscriber.subscribed_at.isoformat() if subscriber.subscribed_at else None,
        'unsubscribed_at': subscriber.unsubscribed_at.isoformat() if subscriber.unsubscribed_at else None,
        'last_sent_at': subscriber.last_sent_at.isoformat() if subscriber.last_sent_at else None,
        'created_at': subscriber.created_at.isoformat() if subscriber.created_at else None,
    }), 200

# ---------- ADMIN UNSUBSCRIBE ----------
@admin_subscribers_bp.route('/<int:subscriber_id>/unsubscribe', methods=['POST', 'OPTIONS'])
@csrf.exempt
@super_admin_required
def admin_unsubscribe(subscriber_id):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    subscriber = Subscriber.query.get_or_404(subscriber_id)
    if subscriber.unsubscribed_at:
        return jsonify({'message': 'Already unsubscribed'}), 400

    subscriber.unsubscribed_at = datetime.now(timezone.utc)
    db.session.commit()
    logger.info(f"Admin unsubscribed subscriber {subscriber.email} (ID: {subscriber.id})")
    return jsonify({'message': f'Unsubscribed {subscriber.email}'}), 200

# ---------- RESEND VERIFICATION ----------
@admin_subscribers_bp.route('/<int:subscriber_id>/resend-verification', methods=['POST', 'OPTIONS'])
@csrf.exempt
@super_admin_required
def resend_verification(subscriber_id):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    subscriber = Subscriber.query.get_or_404(subscriber_id)
    if subscriber.verified:
        return jsonify({'message': 'Already verified'}), 400

    import secrets
    token = secrets.token_urlsafe(32)
    subscriber.verification_token = token
    db.session.commit()

    send_verification_email(subscriber.email, token)
    logger.info(f"Resent verification email to {subscriber.email}")
    return jsonify({'message': f'Verification email resent to {subscriber.email}'}), 200

# ---------- DELETE SUBSCRIBER ----------
@admin_subscribers_bp.route('/<int:subscriber_id>', methods=['DELETE', 'OPTIONS'])
@csrf.exempt
@super_admin_required
def delete_subscriber(subscriber_id):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    subscriber = Subscriber.query.get_or_404(subscriber_id)
    email = subscriber.email
    db.session.delete(subscriber)
    db.session.commit()
    logger.info(f"Admin deleted subscriber {email} (ID: {subscriber_id})")
    return jsonify({'message': f'Deleted subscriber {email}'}), 200
