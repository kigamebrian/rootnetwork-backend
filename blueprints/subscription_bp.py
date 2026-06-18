# blueprints/subscription_bp.py
from flask import Blueprint, request, jsonify, session, make_response
from models import Subscriber, Category, db
from services.email_service import send_verification_email
from exts import csrf
from datetime import datetime, timedelta, timezone  # <-- added timezone
import secrets
import re

subscription_bp = Blueprint('subscription', __name__, url_prefix='/api/subscribe')

# ========== HELPER FOR CORS ==========
def get_allowed_origin():
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork1.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    return origin if origin in allowed_origins else 'https://rootnetwork1.netlify.app'

def _cors_response(response, status=200):
    response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS, PATCH')
    return response, status

# ================== SUBSCRIBE ==================
@subscription_bp.route('', methods=['POST', 'OPTIONS'])
@csrf.exempt
def subscribe():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    data = request.get_json()
    email = data.get('email', '').strip().lower()
    categories = data.get('categories', [])
    frequency = data.get('frequency', 'daily')

    if not email or not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({'error': 'Valid email is required'}), 400

    if categories:
        existing = Category.query.filter(Category.id.in_(categories)).count()
        if existing != len(categories):
            return jsonify({'error': 'One or more categories are invalid'}), 400

    if frequency not in ('instant', 'daily', 'weekly'):
        frequency = 'daily'

    subscriber = Subscriber.query.filter_by(email=email).first()
    if subscriber:
        if subscriber.is_active():
            if (subscriber.preferences.get('categories') != categories or
                subscriber.preferences.get('frequency') != frequency):
                subscriber.preferences = {'categories': categories, 'frequency': frequency}
                db.session.commit()
                return jsonify({'message': 'Preferences updated successfully'}), 200
            return jsonify({'message': 'Already subscribed'}), 200
        else:
            # Re-subscribe
            subscriber.verified = False
            subscriber.unsubscribed_at = None
            subscriber.preferences = {'categories': categories, 'frequency': frequency}
            subscriber.verification_token = secrets.token_urlsafe(32)
            subscriber.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
            db.session.commit()
            send_verification_email(email, subscriber.verification_token)
            return jsonify({'message': 'Re-subscribed. Please verify your email.'}), 200

    # New subscriber
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    new_sub = Subscriber(
        email=email,
        verification_token=token,
        expires_at=expires_at,
        preferences={'categories': categories, 'frequency': frequency}
    )
    db.session.add(new_sub)
    db.session.commit()

    send_verification_email(email, token)
    return jsonify({'message': 'Please check your email to verify your subscription.'}), 201

# ================== VERIFY ==================
@subscription_bp.route('/verify/<token>', methods=['GET', 'OPTIONS'])
@csrf.exempt
def verify(token):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    try:
        subscriber = Subscriber.query.filter_by(verification_token=token).first()
        if not subscriber:
            return _cors_response(jsonify({'error': 'Invalid or expired verification token'}), 400)

        if subscriber.expires_at and subscriber.expires_at < datetime.now(timezone.utc):
            return _cors_response(jsonify({'error': 'Invalid or expired verification token'}), 400)

        if subscriber.verified:
            return _cors_response(jsonify({'message': 'You are already verified.'}), 200)

        subscriber.verified = True
        db.session.commit()
        return _cors_response(jsonify({'message': 'Email verified. You are now subscribed!'}), 200)
    except Exception as e:
        print(f"❌ Verification error: {e}")
        import traceback
        traceback.print_exc()
        return _cors_response(jsonify({'error': 'Verification failed. Please try again.'}), 500)

# ================== UNSUBSCRIBE ==================
@subscription_bp.route('/unsubscribe', methods=['POST', 'OPTIONS'])
@csrf.exempt
def unsubscribe():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    data = request.get_json()
    email = data.get('email', '').strip().lower()
    token = data.get('token')

    subscriber = None
    if token:
        subscriber = Subscriber.query.filter_by(verification_token=token).first()
    if not subscriber and email:
        subscriber = Subscriber.query.filter_by(email=email).first()

    if not subscriber:
        return jsonify({'error': 'Subscriber not found'}), 404

    subscriber.unsubscribed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'message': 'You have been unsubscribed.'}), 200

# ================== PREFERENCES ==================
@subscription_bp.route('/preferences', methods=['PUT', 'OPTIONS'])
@csrf.exempt
def update_preferences():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'PUT, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    data = request.get_json()
    email = data.get('email', '').strip().lower()
    token = data.get('token')
    categories = data.get('categories')
    frequency = data.get('frequency')

    subscriber = None
    if token:
        subscriber = Subscriber.query.filter_by(verification_token=token).first()
    if not subscriber and email:
        subscriber = Subscriber.query.filter_by(email=email).first()

    if not subscriber or not subscriber.is_active():
        return jsonify({'error': 'Subscriber not found or inactive'}), 404

    if categories is not None:
        if categories:
            existing = Category.query.filter(Category.id.in_(categories)).count()
            if existing != len(categories):
                return jsonify({'error': 'Invalid categories'}), 400
        subscriber.preferences['categories'] = categories

    if frequency is not None:
        if frequency not in ('instant', 'daily', 'weekly'):
            return jsonify({'error': 'Invalid frequency'}), 400
        subscriber.preferences['frequency'] = frequency

    db.session.commit()
    return jsonify({'message': 'Preferences updated successfully'}), 200

# ================== CATEGORIES ==================
@subscription_bp.route('/categories', methods=['GET', 'OPTIONS'])
def get_subscription_categories():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    categories = Category.query.all()
    return jsonify([{'id': c.id, 'name': c.name} for c in categories])
