# init_db.py
from app import app
from exts import db
from models import User, Post, Category, Comment, CommentReply, PageView, UserAction, ActivityLog, FailedLoginAttempt, SuspiciousActivity, SecurityEvent, BlockedIP, SecurityAuditLog

with app.app_context():
    # Drop all tables (if they exist)
    db.drop_all()
    print("Dropped all tables")
    
    # Create all tables
    db.create_all()
    print("✅ Created all tables successfully!")
    
    # Verify tables exist
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print(f"Tables created: {tables}")