# backend/exts.py
from faker import Faker
from flask_ckeditor import CKEditor
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from flask_session import Session   # <-- ADD THIS

# Database - declare only once
db = SQLAlchemy()

# Email
mail = Mail()

# Fake data
faker = Faker('zh_CN')

# Login
loginmanager = LoginManager()
loginmanager.login_view = 'auth.login'
loginmanager.login_message_category = 'warning'
loginmanager.login_message = 'Please log in to access this page.'

# Rich text editor
ckeditor = CKEditor()

# CSRF protection
csrf = CSRFProtect()

# Migration
migrate = Migrate()

# Session - new
sess = Session()   
