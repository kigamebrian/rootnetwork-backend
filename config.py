# config.py
import os

basedir = os.path.abspath(os.path.dirname(__file__))

# Security
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Database - Support both SQLite (local) and PostgreSQL (production)
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
else:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'database.sqlite3')

SQLALCHEMY_TRACK_MODIFICATIONS = False

# Email
MAIL_SERVER = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('SMTP_PORT', 587))
MAIL_USE_TLS = True
MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
MAIL_DEFAULT_SENDER = (os.environ.get('BLOG_NAME', 'RootNetwork'), MAIL_USERNAME)

# AI Configuration
API_KEY = os.environ.get('API_KEY')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')
HUGGINGFACE_TOKEN = os.environ.get('HUGGINGFACE_TOKEN')
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')

# App Settings
BLOG_NAME = os.environ.get('BLOG_NAME', 'RootNetwork')
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
CORS_ORIGINS = os.environ.get(
    'CORS_ORIGINS',
    'http://localhost:3000,http://127.0.0.1:3000,https://rootnetwork1.netlify.app'  # no trailing slash
).split(',')
# Security configuration
ALLOWED_TAGS = [
    'p', 'br', 'b', 'i', 'u', 'em', 'strong', 'a', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre',
    'img', 'span', 'div', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
    'code': ['class'],
    'pre': ['class'],
    'table': ['class'],
    'td': ['colspan', 'rowspan'],
    'th': ['colspan', 'rowspan']
}

MIN_PASSWORD_LENGTH = 8
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 50

# Upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_IMAGE_SIZE_MB = 5
MAX_IMAGE_DIMENSION = 4000

# Static folder configuration
STATIC_FOLDER = os.path.join(basedir, 'static')
STATIC_URL_PATH = '/static'

# Upload folders
UPLOAD_FOLDERS = {
    'posts': os.path.join(STATIC_FOLDER, 'posts'),
    'profiles': os.path.join(STATIC_FOLDER, 'profiles')
}
