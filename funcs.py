# funcs.py
from dotenv import load_dotenv
from functools import wraps
from flask import session, jsonify, g, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import User, generate_slug
from config import (
    ALLOWED_TAGS, ALLOWED_ATTRIBUTES, MIN_PASSWORD_LENGTH, 
    MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH, ALLOWED_EXTENSIONS,
    MAX_IMAGE_SIZE_MB, MAX_IMAGE_DIMENSION
)
import bleach
import re
import os
from PIL import Image
from datetime import datetime
import json
import logging
import secrets

logger = logging.getLogger(__name__)

load_dotenv()

# ================= EXISTING FUNCTIONS =================

def create_app():
    """App factory function - your existing implementation"""
    from flask import Flask
    from exts import db, csrf, mail, ckeditor, loginmanager
    import os
    
    app = Flask(__name__)
    
    # Load config
    app.config.from_pyfile('config.py', silent=True)
    
    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    ckeditor.init_app(app)
    loginmanager.init_app(app)
    
    return app

# Create limiter instance (will be initialized with app later)
limiter = Limiter(
    get_remote_address,
    default_limits=["1000 per day", "200 per hour", "30 per minute"],  # Increased
    storage_uri="memory://"
)

def init_limiter(app):
    """Initialize limiter with app instance"""
    limiter.init_app(app)

def sanitize_html(content):
    """Sanitize HTML content to prevent XSS attacks"""
    if not content:
        return content
    return bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )

def validate_username(username):
    """Validate username format"""
    if not username or len(username) < MIN_USERNAME_LENGTH or len(username) > MAX_USERNAME_LENGTH:
        return False, f"Username must be between {MIN_USERNAME_LENGTH} and {MAX_USERNAME_LENGTH} characters"
    if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
        return False, "Username can only contain letters, numbers, dots, hyphens, and underscores"
    return True, "Valid"

def validate_password_strength(password):
    """Validate password strength"""
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Password must contain at least one special character"
    return True, "Strong password"

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_and_sanitize_image(file_path):
    """Validate and sanitize image file for security"""
    try:
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        if file_size > MAX_IMAGE_SIZE_MB:
            return False, f"Image too large. Max {MAX_IMAGE_SIZE_MB}MB", 0, 0
        
        img = Image.open(file_path)
        img.verify()
        img = Image.open(file_path)
        
        allowed_formats = ['PNG', 'JPEG', 'JPG', 'GIF', 'WEBP']
        if img.format not in allowed_formats:
            return False, f"Invalid format. Allowed: {', '.join(allowed_formats)}", 0, 0
        
        width, height = img.size
        if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
            return False, f"Image dimensions too large. Max {MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION} pixels", width, height
        
        # Sanitize image
        img = Image.open(file_path)
        if img.mode in ('RGBA', 'LA', 'P'):
            clean_img = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                clean_img.paste(img, mask=img.split()[-1])
            else:
                clean_img.paste(img)
        else:
            clean_img = img.convert('RGB')
        
        clean_img.save(file_path, format=img.format, optimize=True, quality=85)
        return True, "Valid and sanitized", width, height
        
    except Exception as e:
        return False, f"Invalid image: {str(e)}", 0, 0

# ================= IMPROVED DECORATORS =================

def login_required(f):
    """Decorator to require login for routes - sets g.current_user"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        
        # Set current user in Flask's g object
        user = User.query.get(session['user_id'])
        if not user or not user.is_active:
            session.clear()
            return jsonify({'error': 'Invalid session'}), 401
        
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    """Decorator to require super admin access - sets g.current_user"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Login required'}), 401
        
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            return jsonify({'error': 'Invalid session'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account disabled'}), 403
        
        if not user.is_super_admin:
            return jsonify({'error': 'Super admin access required'}), 403
        
        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function

def get_session_id():
    """Get or create session ID for tracking"""
    import uuid
    session_id = session.get('tracking_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        session['tracking_session_id'] = session_id
    return session_id

# ================= NEW HELPER FUNCTIONS =================

def validate_email_address(email):
    """Validate email using proper library (fallback if email-validator not installed)"""
    # Basic validation - consider installing email-validator
    if '@' not in email or '.' not in email.split('@')[-1]:
        return None, "Invalid email format"
    return email, None

def validate_boolean(value, field_name):
    """Strict boolean validation accepting various formats"""
    if isinstance(value, bool):
        return value, None
    if isinstance(value, str):
        if value.lower() in ('true', '1', 'yes'):
            return True, None
        if value.lower() in ('false', '0', 'no'):
            return False, None
    if isinstance(value, (int, float)):
        return bool(value), None
    return None, f"{field_name} must be a boolean"

def safe_get_json(allowed_fields=None, required_fields=None):
    """Safely get JSON from request with field validation"""
    data = request.get_json(silent=True)
    if data is None:
        return None, "Invalid JSON"
    
    if not isinstance(data, dict):
        return None, "JSON body must be an object"
    
    if allowed_fields:
        unknown = set(data.keys()) - allowed_fields
        if unknown:
            return None, f"Unknown fields: {', '.join(unknown)}"
    
    if required_fields:
        missing = [f for f in required_fields if f not in data]
        if missing:
            return None, f"Missing required fields: {', '.join(missing)}"
    
    return data, None

def handle_db_error():
    """Consistent database error handler"""
    from exts import db
    db.session.rollback()
    logger.exception("Database error occurred")
    return jsonify({'error': 'Internal server error'}), 500

def validate_pagination(page, per_page, default_per_page=20):
    """Validate pagination parameters"""
    page = max(1, page if page else 1)
    per_page = min(max(1, per_page if per_page else default_per_page), 100)
    return page, per_page

def format_datetime(dt):
    """Format datetime safely with timezone"""
    if not dt:
        return None
    if dt.tzinfo:
        return dt.astimezone(datetime.now().astimezone().tzinfo).isoformat()
    return dt.isoformat()

def log_audit(action, actor_id, target_id=None, details=None, request_info=None):
    """Structured audit logging with JSON format"""
    log_entry = {
        "event": "audit",
        "action": action,
        "actor": actor_id,
        "target": target_id,
        "timestamp": datetime.now().isoformat(),
    }
    if request_info:
        log_entry["ip"] = request_info.remote_addr
        log_entry["user_agent"] = request_info.user_agent
    if details:
        log_entry["details"] = details
    logger.info(json.dumps(log_entry))

# ================= CLI COMMANDS =================

def register_commands(app):
    """Register CLI commands"""
    @app.cli.command("create-admin")
    def create_admin():
        """Create admin user"""
        from models import User
        import getpass
        from exts import db
        
        print("Creating admin user...")
        email = input("Email: ")
        username = input("Username: ")
        password = getpass.getpass("Password: ")
        
        if User.query.filter_by(email=email).first():
            print("❌ Email already exists")
            return
        
        admin = User(
            email=email,
            username=username,
            full_name="Admin",
            is_super_admin=True,
            is_active=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Admin user {username} created successfully")

def register_tFilter(app):
    """Register template filters"""
    @app.template_filter('datetimeformat')
    def datetimeformat(value, format='%Y-%m-%d %H:%M'):
        if value:
            return value.strftime(format)
        return ''