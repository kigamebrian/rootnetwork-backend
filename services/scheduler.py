# services/scheduler.py
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from models import AppSetting, Post, db
from services.notification_service import send_digest_for_subscriber, notify_subscribers_async
from services import send_admin_new_post_background, send_post_author_post_created_background

scheduler = BackgroundScheduler()

def _get_setting(key, default):
    from models import AppSetting
    return AppSetting.get(key, default)

def _int_setting(key, default):
    try:
        return int(_get_setting(key, default))
    except (ValueError, TypeError):
        return default

def publish_scheduled_posts(app):
    def _publish():
        with app.app_context():
            try:
                # Prevent SSL errors with stale connections
                db.engine.dispose()

                now = datetime.now(timezone.utc)
                print(f"🔍 Checking for scheduled posts at {now}")

                scheduled_posts = Post.query.filter(
                    Post.status == 'scheduled',
                    Post.scheduled_for <= now
                ).all()

                if scheduled_posts:
                    print(f"📅 Found {len(scheduled_posts)} posts to publish")

                for post in scheduled_posts:
                    post.status = 'published'
                    post.timestamp = now
                    post.published_at = now
                    post.scheduled_for = None
                    db.session.commit()

                    send_admin_new_post_background(post)
                    send_post_author_post_created_background(post)
                    notify_subscribers_async(post.id, force_instant=True)
                    print(f"   ✅ Published: {post.title}")

            except Exception as e:
                print(f"❌ Scheduler error: {e}")
                import traceback
                traceback.print_exc()
    return _publish

def run_daily_digest(app):
    def _send():
        with app.app_context():
            try:
                from models import Subscriber
                subscribers = Subscriber.query.filter(
                    Subscriber.verified == True,
                    Subscriber.unsubscribed_at.is_(None)
                ).all()
                daily_subs = [s for s in subscribers if s.preferences.get('frequency') == 'daily']
                print(f"📧 Sending daily digest to {len(daily_subs)} subscribers")
                for sub in daily_subs:
                    send_digest_for_subscriber(sub.id, 'daily')
            except Exception as e:
                print(f"❌ Daily digest error: {e}")
                import traceback
                traceback.print_exc()
    return _send

def run_weekly_digest(app):
    def _send():
        with app.app_context():
            try:
                from models import Subscriber
                subscribers = Subscriber.query.filter(
                    Subscriber.verified == True,
                    Subscriber.unsubscribed_at.is_(None)
                ).all()
                weekly_subs = [s for s in subscribers if s.preferences.get('frequency') == 'weekly']
                print(f"📧 Sending weekly digest to {len(weekly_subs)} subscribers")
                for sub in weekly_subs:
                    send_digest_for_subscriber(sub.id, 'weekly')
            except Exception as e:
                print(f"❌ Weekly digest error: {e}")
                import traceback
                traceback.print_exc()
    return _send

def reload_scheduler(app):
    """Reload all jobs with current settings from the database."""
    # Remove existing jobs
    for job in scheduler.get_jobs():
        scheduler.remove_job(job.id)

    # 1. Publish scheduled posts – interval
    interval_minutes = _int_setting('publish_interval_minutes', 1)
    scheduler.add_job(
        func=publish_scheduled_posts(app),
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="publish_scheduled_posts",
        replace_existing=True
    )

    # 2. Daily digest
    hour = _int_setting('daily_digest_hour', 8)
    minute = _int_setting('daily_digest_minute', 0)
    scheduler.add_job(
        func=run_daily_digest(app),
        trigger=CronTrigger(hour=hour, minute=minute),
        id="daily_digest",
        replace_existing=True
    )

    # 3. Weekly digest
    day = _get_setting('weekly_digest_day', 'mon')
    hour = _int_setting('weekly_digest_hour', 9)
    minute = _int_setting('weekly_digest_minute', 0)
    scheduler.add_job(
        func=run_weekly_digest(app),
        trigger=CronTrigger(day_of_week=day, hour=hour, minute=minute),
        id="weekly_digest",
        replace_existing=True
    )

    print(f"✅ Scheduler reloaded with:")
    print(f"   - Publish interval: {interval_minutes} min")
    print(f"   - Daily digest: {hour:02d}:{minute:02d}")
    print(f"   - Weekly digest: {day} at {hour:02d}:{minute:02d}")

def start_scheduler(app):
    """Start the scheduler for the first time."""
    # Prevent duplicate start
    if scheduler.running:
        print("⚠️ Scheduler already running")
        return
    reload_scheduler(app)
    scheduler.start()
    print("✅ APScheduler started")
