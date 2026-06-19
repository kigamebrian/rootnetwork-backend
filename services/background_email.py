# backend/services/background_email.py
import threading
from flask import current_app
from exts import db

def send_email_background(email_func, *args, **kwargs):
    """
    Send an email in a background thread with the Flask application context.
    Uses a fresh SQLAlchemy session to avoid conflicts with the main request.
    """
    app = current_app._get_current_object()

    def _send():
        with app.app_context():
            try:
                email_func(*args, **kwargs)
            except Exception as e:
                print(f"❌ Background email failed: {e}")
                db.session.rollback()
            finally:
                # Remove the session for this thread
                db.session.remove()

    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()


def run_in_background(func, *args, **kwargs):
    """
    Run any function in a background thread with app context.
    Uses a fresh SQLAlchemy session.
    """
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"❌ Background task failed: {e}")
                db.session.rollback()
            finally:
                db.session.remove()

    thread = threading.Thread(target=_run)
    thread.daemon = True
    thread.start()
