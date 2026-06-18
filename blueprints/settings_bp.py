# blueprints/settings_bp.py
from flask import Blueprint, request, jsonify, current_app, make_response
from models import AppSetting, db
from funcs import super_admin_required
from exts import csrf

settings_bp = Blueprint('settings', __name__, url_prefix='/api/admin/settings')

# ========== HELPER FOR CORS ==========
def get_allowed_origin():
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork1.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    return origin if origin in allowed_origins else 'https://rootnetwork1.netlify.app'

@settings_bp.route('/scheduler', methods=['GET', 'OPTIONS'])
@super_admin_required
def get_scheduler_settings():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'GET, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    keys = ['daily_digest_hour', 'daily_digest_minute', 
            'weekly_digest_day', 'weekly_digest_hour', 'weekly_digest_minute',
            'publish_interval_minutes']
    settings = {}
    for key in keys:
        setting = AppSetting.query.filter_by(key=key).first()
        settings[key] = setting.value if setting else None
    return jsonify(settings)

@settings_bp.route('/scheduler', methods=['PUT', 'OPTIONS'])
@super_admin_required
@csrf.exempt
def update_scheduler_settings():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'PUT, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    data = request.get_json()

    required = ['daily_digest_hour', 'daily_digest_minute', 
                'weekly_digest_day', 'weekly_digest_hour', 'weekly_digest_minute',
                'publish_interval_minutes']
    for key in required:
        if key not in data:
            return jsonify({'error': f'Missing field: {key}'}), 400

    try:
        hour = int(data['daily_digest_hour'])
        if not (0 <= hour <= 23):
            return jsonify({'error': 'daily_digest_hour must be 0-23'}), 400
        minute = int(data['daily_digest_minute'])
        if not (0 <= minute <= 59):
            return jsonify({'error': 'daily_digest_minute must be 0-59'}), 400
        week_day = data['weekly_digest_day']
        if week_day not in ['mon','tue','wed','thu','fri','sat','sun']:
            return jsonify({'error': 'Invalid weekly_digest_day'}), 400
        hour_w = int(data['weekly_digest_hour'])
        if not (0 <= hour_w <= 23):
            return jsonify({'error': 'weekly_digest_hour must be 0-23'}), 400
        minute_w = int(data['weekly_digest_minute'])
        if not (0 <= minute_w <= 59):
            return jsonify({'error': 'weekly_digest_minute must be 0-59'}), 400
        interval = int(data['publish_interval_minutes'])
        if interval < 1:
            return jsonify({'error': 'publish_interval_minutes must be at least 1'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid number format'}), 400

    for key, value in data.items():
        AppSetting.set(key, str(value))

    from services.scheduler import reload_scheduler
    reload_scheduler(current_app._get_current_object())

    return jsonify({'message': 'Settings updated and scheduler reloaded'})
