# create_admin.py
from app import app
from models import User
from exts import db

with app.app_context():
    # Check if admin already exists
    existing_admin = User.query.filter_by(is_super_admin=True).first()
    if existing_admin:
        print(f"Admin already exists: {existing_admin.username}")
        print(f"Email: {existing_admin.email}")
    else:
        # Create new admin user
        admin = User(
            email="briankigame7@gmail.com",
            username="admin",
            full_name="Administrator",
            is_super_admin=True,
            is_active=True,
            blog_title="My Blog",
            blog_subtitle="Welcome to my blog"
        )
        admin.set_password("Admin123!")
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created successfully!")
        print("   Username: admin")
        print("   Password: Admin123!")
        print("   Email: briankigame7@gmail.com")