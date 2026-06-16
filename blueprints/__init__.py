from flask import Blueprint

# Create all blueprints
auth_bp = Blueprint('auth', __name__, url_prefix='/api')
tracking_bp = Blueprint('tracking', __name__, url_prefix='/api/track')
upload_bp = Blueprint('upload', __name__, url_prefix='/api')
security_bp = Blueprint('security', __name__, url_prefix='/api/admin')
analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/admin')
user_mgmt_bp = Blueprint('user_mgmt', __name__, url_prefix='/api/admin')
blog_bp = Blueprint('blog', __name__, url_prefix='/api')
admin_posts_bp = Blueprint('admin_posts', __name__, url_prefix='/api/admin')
comment_bp = Blueprint('comment', __name__, url_prefix='/api/admin')
category_bp = Blueprint('category', __name__, url_prefix='/api/admin')
profile_bp = Blueprint('profile', __name__, url_prefix='/api/user')
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')
trending_bp = Blueprint('trending', __name__, url_prefix='/api')
rate_limit_bp = Blueprint('rate_limit', __name__, url_prefix='/api')

# Import TTS blueprint
from .tts_bp import tts_bp

# Import all route modules
from . import auth, tracking, upload, security, analytics, user_mgmt, blog, admin_posts, comment, category, profile, ai, trending
from .rate_limit_bp import rate_limit_bp

# Export all blueprints
__all__ = [
    'auth_bp', 'tracking_bp', 'upload_bp', 'security_bp', 'analytics_bp',
    'user_mgmt_bp', 'blog_bp', 'admin_posts_bp', 'comment_bp', 'category_bp',
    'profile_bp', 'ai_bp', 'trending_bp', 'rate_limit_bp', 'tts_bp'
]