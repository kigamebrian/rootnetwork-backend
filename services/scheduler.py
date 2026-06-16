# backend/services/scheduler.py
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = BackgroundScheduler()

def publish_scheduled_posts(app):
    """Check and publish scheduled posts - runs within app context"""
    def _publish():
        with app.app_context():
            try:
                now = datetime.now(timezone.utc)
                print(f"🔍 Checking for scheduled posts at {now}")
                
                from models import Post
                from exts import db
                from services import send_admin_new_post_background, send_post_author_post_created_background
                
                # Find posts that should be published
                scheduled_posts = Post.query.filter(
                    Post.status == 'scheduled',
                    Post.scheduled_for <= now
                ).all()
                
                if scheduled_posts:
                    print(f"📅 Found {len(scheduled_posts)} posts to publish")
                
                for post in scheduled_posts:
                    print(f"   Publishing: {post.title}")
                    print(f"      Scheduled for: {post.scheduled_for}")
                    
                    # Update post status
                    post.status = 'published'
                    post.timestamp = now
                    post.published_at = now
                    post.scheduled_for = None
                    db.session.commit()
                    
                    # Send notifications
                    send_admin_new_post_background(post)
                    send_post_author_post_created_background(post)
                    
                    print(f"   ✅ Published: {post.title}")
                    
            except Exception as e:
                print(f"❌ Scheduler error: {e}")
                import traceback
                traceback.print_exc()
    
    return _publish

def start_scheduler(app):
    """Start the scheduler with app context"""
    # Get the publish function with app context
    publish_func = publish_scheduled_posts(app)
    
    # Add job to run every minute
    scheduler.add_job(
        func=publish_func,
        trigger=IntervalTrigger(minutes=1),
        id="publish_scheduled_posts",
        replace_existing=True
    )
    
    scheduler.start()
    print("✅ APScheduler started - will check for scheduled posts every minute")
    
    # Run once immediately
    with app.app_context():
        publish_func()