# backend/add_images_column.py
import os
import sys
from sqlalchemy import text
from app import app
from exts import db

def add_images_column():
    with app.app_context():
        # Check if column exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('post')]
        if 'images' not in columns:
            print("Adding 'images' column to 'post' table...")
            db.session.execute(text("ALTER TABLE post ADD COLUMN images JSON DEFAULT '[]'"))
            db.session.commit()
            print("✅ 'images' column added.")
        else:
            print("ℹ️ 'images' column already exists. Nothing to do.")

if __name__ == "__main__":
    add_images_column()
