# test_scheduler.py
from app import app
from models import Post, User
from datetime import datetime, timezone, timedelta
from exts import db

with app.app_context():
    print("=" * 50)
    print("Testing Scheduler")
    print("=" * 50)
    
    # Check existing scheduled posts
    scheduled = Post.query.filter_by(status='scheduled').all()
    print(f"\n📊 Existing scheduled posts: {len(scheduled)}")
    
    for post in scheduled:
        print(f"  - {post.title}: scheduled for {post.scheduled_for}")
    
    # Create a test scheduled post for 1 minute from now
    user = User.query.first()
    if user:
        scheduled_time = datetime.now(timezone.utc) + timedelta(minutes=1)
        print(f"\n📅 Creating test post scheduled for: {scheduled_time}")
        
        test_post = Post(
            title=f"TEST SCHEDULED - {datetime.now().strftime('%H:%M:%S')}",
            slug=f"test-scheduled-{datetime.now().timestamp()}",
            content="This is a test of the scheduler.",
            author_id=user.id,
            status='scheduled',
            scheduled_for=scheduled_time
        )
        db.session.add(test_post)
        db.session.commit()
        print(f"✅ Test post created with ID: {test_post.id}")
    else:
        print("❌ No user found!")
    
    print("\n⏰ Waiting 70 seconds for scheduler to run...")
    import time
    time.sleep(70)
    
    # Check if it published
    from services.scheduler import publish_scheduled_posts
    publish_scheduled_posts()
    
    # Verify
    test_post = Post.query.get(test_post.id)
    print(f"\n📊 Test post status: {test_post.status}")
    print(f"   Published at: {test_post.published_at}")
    
    if test_post.status == 'published':
        print("\n✅ SCHEDULER IS WORKING!")
    else:
        print("\n❌ SCHEDULER IS NOT WORKING")