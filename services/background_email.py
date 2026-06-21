# services/background_email.py
import threading
from flask import current_app
from exts import db

def send_email_background(email_func, *args, **kwargs):
    """
    Send an email in a background thread with a fresh SQLAlchemy session.
    """
    app = current_app._get_current_object()

    def _send():
        with app.app_context():
            try:
                email_func(*args, **kwargs)
            except Exception as e:
                print(f"❌ Background email failed: {e}")
                # Use remove() instead of rollback() to clean up the session
                db.session.remove()
            finally:
                # Ensure the session is removed
                db.session.remove()

    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()

def run_in_background(func, *args, **kwargs):
    """
    Run any function in a background thread with a fresh SQLAlchemy session.
    """
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"❌ Background task failed: {e}")
                db.session.remove()
            finally:
                db.session.remove()

    thread = threading.Thread(target=_run)
    thread.daemon = True
    thread.start()
