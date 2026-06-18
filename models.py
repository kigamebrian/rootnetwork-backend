from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from exts import db
import re
from unicodedata import normalize

# slug generation functions
def generate_slug(title):
    """Generate a URL-friendly slug from a title"""
    slug = normalize('NFKD', title).encode('ASCII', 'ignore').decode('ASCII')
    slug = re.sub(r'[^\w\s-]', '', slug).strip().lower()
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug


def create_unique_slug(title, model, existing_id=None):
    """Create a unique slug with counter to avoid duplicates"""
    base_slug = generate_slug(title)
    slug = base_slug
    counter = 1
    
    while True:
        query = model.query.filter_by(slug=slug)
        if existing_id:
            query = query.filter(model.id != existing_id)
        if not query.first():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
    
    return slug


# ========== User ModelL ==========
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120))
    password_hash = db.Column(db.String(255), nullable=False)
    profile_image = db.Column(db.String(500), default='default-avatar.png')
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_login = db.Column(db.DateTime(timezone=True))
    
    # Blog fields
    blog_title = db.Column(db.String(120), default='My Blog')
    blog_subtitle = db.Column(db.String(200), default='Welcome to my blog')
    about = db.Column(db.Text)
    
        # Relationships
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
    
   # Use overlaps to prevent warning conflicts --- IGNORE ---
    comments = db.relationship('Comment', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True, overlaps="user_comments,comment_user")
    replies = db.relationship('CommentReply', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True, overlaps="user_replies,reply_user")
    
    # Analytics relationships
    page_views = db.relationship('PageView', lazy='dynamic', overlaps="page_views_list,viewer")
    actions = db.relationship('UserAction', lazy='dynamic', overlaps="user_actions,action_user")
    activity_logs = db.relationship('ActivityLog', lazy='dynamic', overlaps="activity_logs_list,log_user")
    security_audit_logs = db.relationship('SecurityAuditLog', lazy='dynamic', overlaps="security_audit_entries,audit_user")
    
    __table_args__ = (
        db.CheckConstraint('LENGTH(username) >= 3', name='check_username_length'),
        db.CheckConstraint("email LIKE '%_@_%._%'", name='check_email_format'),
    )
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def validate_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def update_last_login(self):
        self.last_login = datetime.now(timezone.utc)
    
    def normalize_email(self):
        self.email = self.email.lower().strip()
    
    @property
    def post_count(self):
        return self.posts.count()
    
    def get_id(self):
        return str(self.id)
    
    def __repr__(self):
        return f"<User id={self.id} username='{self.username}'>"


# ========== Category Model ==========
class Category(db.Model):
    __tablename__ = 'category'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False, index=True)
    posts = db.relationship('Post', backref='category', lazy='dynamic', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.CheckConstraint('LENGTH(name) >= 2', name='check_category_name_length'),
    )
    
    def __repr__(self):
        return f"<Category id={self.id} name='{self.name}'>"

# ========== Post model ==========
class Post(db.Model):
    __tablename__ = 'post'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(500))
    # Allow timestamp to be NULL for drafts
    timestamp = db.Column(db.DateTime(timezone=True), nullable=True, index=True)  # Changed to nullable=True
    author_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id', ondelete='SET NULL'), index=True)
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
    
    # Status fields
    status = db.Column(db.String(20), default='draft', nullable=False)
    scheduled_for = db.Column(db.DateTime(timezone=True), nullable=True)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        db.CheckConstraint('LENGTH(title) >= 3', name='check_post_title_length'),
        db.CheckConstraint("status IN ('draft', 'published', 'scheduled')", name='check_valid_status'),
    )
    
    def __repr__(self):
        return f"<Post id={self.id} title='{self.title[:50]}' status='{self.status}'>"

# ==========Comment model ==========
class Comment(db.Model):
    __tablename__ = 'comment'
    
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    site = db.Column(db.String(255))
    comment = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    from_admin = db.Column(db.Boolean, default=False, nullable=False)
    reviewed = db.Column(db.Boolean, default=False, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    comment_replies = db.relationship('CommentReply', backref='comment', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True)
    
  
    user = db.relationship('User', backref='user_comments', foreign_keys=[user_id], overlaps="comments")
    
    def __repr__(self):
        return f"<Comment id={self.id} author='{self.author}'>"


# ========== Comment Reply MODEL ==========
class CommentReply(db.Model):
    __tablename__ = 'commentreply'
    
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    site = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    from_admin = db.Column(db.Boolean, default=False, nullable=False)
    reviewed = db.Column(db.Boolean, default=False, nullable=False)
    comment_reply = db.Column(db.Text, nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    
  
    user = db.relationship('User', backref='user_replies', foreign_keys=[user_id], overlaps="replies")
    
    def __repr__(self):
        return f"<CommentReply id={self.id}>"


# ========== ANALYTICS MODELS ==========
class PageView(db.Model):
    __tablename__ = 'page_views'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    page_url = db.Column(db.String(500), nullable=False)
    page_type = db.Column(db.String(50))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='SET NULL'), index=True)
    referrer = db.Column(db.String(500))
    user_agent = db.Column(db.String(500))
    ip_address = db.Column(db.String(50))
    country = db.Column(db.String(100))
    city = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    user = db.relationship('User', backref='page_views_list', foreign_keys=[user_id], overlaps="page_views")
    post = db.relationship('Post', backref='post_views')


class UserAction(db.Model):
    __tablename__ = 'user_actions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    action_type = db.Column(db.String(50), nullable=False)
    action_details = db.Column(db.Text)
    target_id = db.Column(db.Integer)
    target_type = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    user = db.relationship('User', backref='user_actions', foreign_keys=[user_id], overlaps="actions")


class CommentAnalytics(db.Model):
    __tablename__ = 'comment_analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    session_id = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    comment = db.relationship('Comment', backref='analytics_list')


# ========== SECURITY MODELS ==========
class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    username = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    action_details = db.Column(db.Text)
    ip_address = db.Column(db.String(50), nullable=False)
    user_agent = db.Column(db.String(500))
    endpoint = db.Column(db.String(200))
    method = db.Column(db.String(10))
    status = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    
    user = db.relationship('User', backref='activity_logs_list', foreign_keys=[user_id], overlaps="activity_logs")

#failed login attempt model
class FailedLoginAttempt(db.Model):
    __tablename__ = 'failed_logins'
    
    id = db.Column(db.Integer, primary_key=True)
    username_attempted = db.Column(db.String(80), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    user_agent = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    attempts_count = db.Column(db.Integer, default=1, nullable=False)

#suspicious activity model
class SuspiciousActivity(db.Model):
    __tablename__ = 'suspicious_activities'
    
    id = db.Column(db.Integer, primary_key=True)
    severity = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    endpoint = db.Column(db.String(200))
    request_data = db.Column(db.Text)
    detected_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    resolved = db.Column(db.Boolean, default=False, nullable=False)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    resolved_at = db.Column(db.DateTime(timezone=True))
    notes = db.Column(db.Text)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='suspicious_activities')
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref='resolved_activities')

#security event model
class SecurityEvent(db.Model):
    __tablename__ = 'security_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, default=True, nullable=False)

#blocked IP model
class BlockedIP(db.Model):
    __tablename__ = 'blocked_ips'
    
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50), unique=True, nullable=False, index=True)
    reason = db.Column(db.String(500), nullable=False)
    blocked_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    blocked_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True))
    is_permanent = db.Column(db.Boolean, default=False, nullable=False)
    
    blocker = db.relationship('User', backref='blocked_ips', foreign_keys=[blocked_by])

#security audit log model
class SecurityAuditLog(db.Model):
    __tablename__ = 'security_audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    username = db.Column(db.String(80), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)
    user_agent = db.Column(db.String(500))
    endpoint = db.Column(db.String(200))
    request_method = db.Column(db.String(10))
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    

    user = db.relationship('User', backref='security_audit_entries', foreign_keys=[user_id], overlaps="security_audit_logs")

# ========== RATE LIMIT MODELS ==========

class RateLimitRule(db.Model):
    __tablename__ = 'rate_limit_rules'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    endpoint_pattern = db.Column(db.String(200), nullable=False)
    method = db.Column(db.String(10), default='ALL')
    limit_count = db.Column(db.Integer, nullable=False)
    time_window = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'endpoint_pattern': self.endpoint_pattern,
            'method': self.method,
            'limit_count': self.limit_count,
            'time_window': self.time_window,
            'is_active': self.is_active,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class RateLimitLog(db.Model):
    __tablename__ = 'rate_limit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    endpoint = db.Column(db.String(200), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    rule_id = db.Column(db.Integer, db.ForeignKey('rate_limit_rules.id'))
    was_blocked = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)
    
    rule = db.relationship('RateLimitRule', backref='logs')
    
    def to_dict(self):
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'endpoint': self.endpoint,
            'method': self.method,
            'was_blocked': self.was_blocked,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }



#Trending news model
class TrendingNews(db.Model):
    __tablename__ = 'trending_news'
    
    id = db.Column(db.Integer, primary_key=True)
    headline = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    
    def __repr__(self):
        return f"<TrendingNews id={self.id} headline='{self.headline[:50]}'>"

# ========== SUBSCRIBER MODELS ==========

class Subscriber(db.Model):
    __tablename__ = 'subscribers'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(100), unique=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Preferences: JSON with { "categories": [1,2,3], "frequency": "instant"|"daily"|"weekly" }
    preferences = db.Column(db.JSON, default={'categories': [], 'frequency': 'daily'})
    subscribed_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    unsubscribed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationship to notifications
    notifications = db.relationship('PostNotification', backref='subscriber', lazy='dynamic', cascade='all, delete-orphan')
    
    __table_args__ = (
        db.CheckConstraint("email LIKE '%_@_%._%'", name='check_subscriber_email_format'),
    )
    
    def is_active(self):
        return self.verified and self.unsubscribed_at is None
    
    def __repr__(self):
        return f"<Subscriber id={self.id} email='{self.email}'>"


class PostNotification(db.Model):
    __tablename__ = 'post_notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False, index=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey('subscribers.id', ondelete='CASCADE'), nullable=False, index=True)
    sent_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, sent, failed, skipped
    error_message = db.Column(db.Text, nullable=True)
    
    post = db.relationship('Post', backref='subscriber_notifications')
    
    __table_args__ = (
        db.CheckConstraint("status IN ('pending', 'sent', 'failed', 'skipped')", name='check_notification_status'),
        db.UniqueConstraint('post_id', 'subscriber_id', name='uq_post_subscriber'),
    )
    
    def __repr__(self):
        return f"<PostNotification post_id={self.post_id} subscriber_id={self.subscriber_id} status='{self.status}'>"


# ========== DIGEST LOG (OPTIONAL) ==========
class DigestLog(db.Model):
    __tablename__ = 'digest_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey('subscribers.id', ondelete='CASCADE'), nullable=False, index=True)
    frequency = db.Column(db.String(20), nullable=False)  # daily, weekly
    sent_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    post_ids = db.Column(db.JSON, nullable=False)  # list of post IDs included
    status = db.Column(db.String(20), default='sent')
    
    subscriber = db.relationship('Subscriber', backref='digest_logs')

# models.py
class AppSetting(db.Model):
    __tablename__ = 'app_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get(cls, key, default=None):
        try:
            setting = cls.query.filter_by(key=key).first()
            if setting:
                return setting.value
        except Exception:
            # Table may not exist yet (e.g., before migration)
            pass
        return default
    
    @classmethod
    def set(cls, key, value, description=None):
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.description = description
        else:
            setting = cls(key=key, value=value, description=description)
            db.session.add(setting)
        db.session.commit()
