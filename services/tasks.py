# services/tasks.py
import logging
import threading
from functools import wraps
from time import sleep
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def retry_on_failure(max_retries: int = 3, delay: int = 1):
    """Retry decorator for async tasks"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Task {func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    sleep(delay * (attempt + 1))
            return None
        return wrapper
    return decorator

@retry_on_failure(max_retries=3, delay=2)
def send_intrusion_alert(threat: Dict[str, Any], ip_address: str, endpoint: str) -> None:
    """Send intrusion alert email with retry logic"""
    try:
        from services.email_service import notify_admin_intrusion_detected
        notify_admin_intrusion_detected(threat, ip_address, endpoint)
        logger.info(f"📧 Intrusion alert sent for {ip_address} at {endpoint}")
    except Exception as e:
        logger.error(f"Failed to send intrusion alert for {ip_address}: {e}")
        # Re-raise for retry
        raise

@retry_on_failure(max_retries=3, delay=2)
def send_bruteforce_alert(ip_address: str, attempts_count: int, username_attempted: Optional[str] = None) -> None:
    """Send brute force alert email with retry logic"""
    try:
        from services.email_service import notify_admin_failed_login
        notify_admin_failed_login(ip_address, attempts_count, username_attempted)
        logger.info(f"📧 Brute force alert sent for {ip_address} ({attempts_count} attempts)")
    except Exception as e:
        logger.error(f"Failed to send brute force alert for {ip_address}: {e}")
        # Re-raise for retry
        raise

def send_intrusion_alert_async(threat: Dict[str, Any], ip_address: str, endpoint: str) -> None:
    """Send intrusion alert asynchronously"""
    def _send():
        try:
            send_intrusion_alert(threat, ip_address, endpoint)
        except Exception as e:
            logger.error(f"Async alert failed: {e}")
    
    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()

def send_bruteforce_alert_async(ip_address: str, attempts_count: int, username_attempted: Optional[str] = None) -> None:
    """Send brute force alert asynchronously"""
    def _send():
        try:
            send_bruteforce_alert(ip_address, attempts_count, username_attempted)
        except Exception as e:
            logger.error(f"Async alert failed: {e}")
    
    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()

# For backward compatibility with existing code
# These are the functions that were imported in other files
def send_intrusion_alert_delay(threat: Dict[str, Any], ip_address: str, endpoint: str) -> None:
    """Alias for backward compatibility"""
    send_intrusion_alert_async(threat, ip_address, endpoint)

def send_bruteforce_alert_delay(ip_address: str, attempts_count: int, username_attempted: Optional[str] = None) -> None:
    """Alias for backward compatibility"""
    send_bruteforce_alert_async(ip_address, attempts_count, username_attempted)