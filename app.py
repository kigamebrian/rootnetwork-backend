# app.py
from dotenv import load_dotenv
from flask import send_from_directory, jsonify, make_response, request
from flask_cors import CORS
from flask_session import Session
from blueprints import (
    admin_posts_bp, ai_bp, analytics_bp, auth_bp, blog_bp, 
    category_bp, comment_bp, profile_bp, security_bp, 
    tracking_bp, trending_bp, upload_bp, user_mgmt_bp
)
from exts import db, csrf, migrate
import secrets
import os
from funcs import create_app, init_limiter
from blueprints.waf_admin import waf_admin_bp
from init_waf import init_waf
from config import CORS_ORIGINS

load_dotenv()

app = create_app()
migrate.init_app(app, db)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))

# Initialize limiter with app
init_limiter(app)

# Session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() == 'true'

Session(app)

# ========== WAF INITIALIZATION ==========
with app.app_context():
    waf_initialized = init_waf()
    app.config['WAF_ENABLED'] = waf_initialized
    
    if waf_initialized:
        print("🛡️ WAF system initialized and ready")
    else:
        print("⚠️ WAF system initialization failed - continuing without WAF")

# ========== SINGLE CORS CONFIGURATION (NO DUPLICATES) ==========
# REMOVED duplicate CORS and @app.before_request handlers
# Let Flask-CORS handle OPTIONS automatically

# Define allowed origins
ALLOWED_ORIGINS = [
    "https://rootnetwork.netlify.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
]

# Single CORS configuration
CORS(
    app,
    supports_credentials=True,
    origins=ALLOWED_ORIGINS,
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
# app.py - Add this after CORS configuration

# ========== GLOBAL CORS HANDLER (OVERRIDES BLUEPRINT HEADERS) ==========
@app.after_request
def add_cors_headers(response):
    """Add CORS headers to every response, overriding blueprint-level headers"""
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    
    # Allow the requesting origin if it's in our list
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
    else:
        response.headers['Access-Control-Allow-Origin'] = 'https://rootnetwork.netlify.app'
    
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-CSRFToken, X-Requested-With, Accept'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Type, X-CSRFToken'
    
    return response
# Import and register blueprints
from blueprints import (
    rate_limit_bp, tts_bp 
)

# Register WAF admin blueprint FIRST (before other admin routes)
app.register_blueprint(waf_admin_bp)

# Register other blueprints
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

# Static files
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# Route for audio cache
@app.route('/audio_cache/<path:filename>')
def serve_audio_cache(filename):
    return send_from_directory('audio_cache', filename, mimetype='audio/mpeg')

# ========== WAF STATUS ENDPOINT ==========
@app.route('/api/waf/status', methods=['GET'])
def waf_status():
    """Public WAF status endpoint (no auth required)"""
    return jsonify({
        'enabled': app.config.get('WAF_ENABLED', False),
        'redis_available': app.config.get('WAF_ENABLED', False),
        'version': '1.0.0'
    })

# ========== ERROR HANDLERS ==========
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429

@app.errorhandler(400)
def bad_request_handler(e):
    return jsonify({'error': 'Bad request. Please check your input.'}), 400

@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error_handler(e):
    print(f"Internal error: {e}")
    return jsonify({'error': 'Internal server error'}), 500

# ========== DATABASE INITIALIZATION ==========
with app.app_context():
    db.create_all()
    print("✅ Database tables created/verified")

# ========== SCHEDULER ==========
from services.scheduler import start_scheduler
start_scheduler(app)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
