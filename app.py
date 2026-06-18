# app.py - UNIFIED (works locally and on Render)
from dotenv import load_dotenv
from flask import send_from_directory, jsonify, make_response, request, session
from flask_cors import CORS
from flask_session import Session
from blueprints import (
    admin_posts_bp, ai_bp, analytics_bp, auth_bp, blog_bp, 
    category_bp, comment_bp, profile_bp, security_bp, 
    tracking_bp, trending_bp, upload_bp, user_mgmt_bp
)
from exts import db, csrf, migrate, sess   # <-- import sess for db sessions
import secrets
import os
from funcs import create_app, init_limiter
from blueprints.waf_admin import waf_admin_bp
from init_waf import init_waf
from config import CORS_ORIGINS
import cloudinary
from blueprints.subscription import subscription_bp
from blueprints.admin_subscribers import admin_subscribers_bp
from blueprints.settings_bp import settings_bp

load_dotenv()

# Cloudinary – only if credentials exist
cloudinary.config(secure=True)

app = create_app()
migrate.init_app(app, db)

# ========== SECRET KEY ==========
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))

# ========== SESSION CONFIGURATION (database-backed) ==========
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY'] = db
app.config['SESSION_SQLALCHEMY_TABLE'] = 'sessions'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

# Initialize the session with the app
sess.init_app(app)

# Initialize rate limiter
init_limiter(app)

# ========== SESSION KEEP-ALIVE ==========
@app.before_request
def refresh_session():
    if 'user_id' in session:
        session.modified = True

# ========== WAF ==========
with app.app_context():
    waf_initialized = init_waf()
    app.config['WAF_ENABLED'] = waf_initialized
    print(f"🛡️ WAF initialized: {waf_initialized}")

# ========== CORS (using config) ==========
CORS(
    app,
    supports_credentials=True,
    origins=CORS_ORIGINS,   # from config.py – includes localhost + Netlify
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-CSRFToken",
        "X-Requested-With",
        "Accept"
    ],
    methods=[
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS",
        "PATCH"
    ],
    expose_headers=["Content-Type", "X-CSRFToken"]
)

# ========== REGISTER BLUEPRINTS ==========
from blueprints import rate_limit_bp, tts_bp

app.register_blueprint(waf_admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(tracking_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(security_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(user_mgmt_bp)
app.register_blueprint(blog_bp)
app.register_blueprint(admin_posts_bp)
app.register_blueprint(comment_bp)
app.register_blueprint(category_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(ai_bp)
app.register_blueprint(trending_bp)
app.register_blueprint(rate_limit_bp)
app.register_blueprint(tts_bp)

# ---- NEW SUBSCRIBER BLUEPRINTS ----
app.register_blueprint(subscription_bp)
app.register_blueprint(admin_subscribers_bp)
app.register_blueprint(settings_bp)

# ========== STATIC FILES ==========
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/audio_cache/<path:filename>')
def serve_audio_cache(filename):
    return send_from_directory('audio_cache', filename, mimetype='audio/mpeg')

# ========== WAF STATUS ==========
@app.route('/api/waf/status', methods=['GET'])
def waf_status():
    return jsonify({'enabled': app.config.get('WAF_ENABLED', False)})

# ========== ERROR HANDLERS ==========
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded'}), 429

@app.errorhandler(400)
def bad_request_handler(e):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error_handler(e):
    print(f"Internal error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# ========== DATABASE & SCHEDULER ==========
with app.app_context():
    db.create_all()
    print("✅ Database tables created/verified")

    # Seed default settings if table is empty
    try:
        from models import AppSetting
        if not AppSetting.query.first():
            AppSetting.set('daily_digest_hour', '8', 'Hour for daily digest')
            AppSetting.set('daily_digest_minute', '0', 'Minute for daily digest')
            AppSetting.set('weekly_digest_day', 'mon', 'Day for weekly digest')
            AppSetting.set('weekly_digest_hour', '9', 'Hour for weekly digest')
            AppSetting.set('weekly_digest_minute', '0', 'Minute for weekly digest')
            AppSetting.set('publish_interval_minutes', '1', 'Minutes between scheduled post checks')
            print("✅ Default scheduler settings seeded.")
    except Exception as e:
        print(f"⚠️ Could not seed settings: {e}")

    # Start scheduler inside app context
    from services.scheduler import start_scheduler
    start_scheduler(app)

# ========== RUN ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
