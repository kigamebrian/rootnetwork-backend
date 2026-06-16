# backend/services/background_email.py
import threading
from functools import wraps

def run_in_background(func):
    """Decorator to run a function in background thread"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
    return wrapper

@run_in_background
def send_email_background(email_func, *args, **kwargs):
    """Send email in background thread"""
    try:
        email_func(*args, **kwargs)
    except Exception as e:
        print(f"❌ Background email failed: {e}")