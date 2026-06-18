# services/notification_service.py
from models import Subscriber, PostNotification, db, Post
from services.email_service import send_post_notification_email, send_digest_email
from datetime import datetime, timezone
import threading
from flask import current_app

def notify_subscribers_async(post_id, force_instant=False):
    """
    Send notifications to subscribers in a background thread.
    If force_instant=True, send to all active subscribers (immediate publish).
    Otherwise, respects each subscriber's frequency.
    """
    # Capture the app instance before starting the thread
    app = current_app._get_current_object()

    def _send():
        with app.app_context():   # use the captured app
            post = Post.query.get(post_id)
            if not post:
                return

            # Get active subscribers
            subscribers = Subscriber.query.filter(
                Subscriber.verified == True,
                Subscriber.unsubscribed_at.is_(None)
            ).all()

            for sub in subscribers:
                # Check category preference
                pref_categories = sub.preferences.get('categories', [])
                if pref_categories and post.category_id not in pref_categories:
                    continue  # not interested in this category

                # Avoid duplicates
                existing = PostNotification.query.filter_by(
                    post_id=post.id,
                    subscriber_id=sub.id
                ).first()
                if existing:
                    continue

                frequency = sub.preferences.get('frequency', 'daily')

                # Instant delivery
                if frequency == 'instant' or force_instant:
                    success = send_post_notification_email(sub, post)
                    status = 'sent' if success else 'failed'

                    notification = PostNotification(
                        post_id=post.id,
                        subscriber_id=sub.id,
                        status=status,
                        sent_at=datetime.now(timezone.utc)
                    )
                    db.session.add(notification)
                    sub.last_sent_at = datetime.now(timezone.utc)

                # Digest (daily/weekly) – mark as pending
                else:
                    notification = PostNotification(
                        post_id=post.id,
                        subscriber_id=sub.id,
                        status='pending'
                    )
                    db.session.add(notification)

            db.session.commit()

    thread = threading.Thread(target=_send)
    thread.daemon = True
    thread.start()


def send_digest_for_subscriber(subscriber_id, frequency='daily'):
    """
    Send a digest email to a single subscriber (called by scheduler).
    """
    sub = Subscriber.query.get(subscriber_id)
    if not sub or not sub.is_active():
        return

    pending = PostNotification.query.filter_by(
        subscriber_id=sub.id,
        status='pending'
    ).all()

    if not pending:
        return

    post_ids = [n.post_id for n in pending]
    posts = Post.query.filter(Post.id.in_(post_ids)).all()

    if posts:
        send_digest_email(sub, posts, frequency)
        # Mark notifications as sent
        for n in pending:
            n.status = 'sent'
            n.sent_at = datetime.now(timezone.utc)
        db.session.commit()
