# services/email_service.py - BREVO API VERSION (No SMTP, No Background Threads)
import os
from datetime import datetime
from dotenv import load_dotenv
from brevo_python import Configuration, ApiClient, TransactionalEmailsApi
from brevo_python.models import SendSmtpEmail, SendSmtpEmailTo, SendSmtpEmailSender
from brevo_python.rest import ApiException

load_dotenv()

# ========== CONFIGURATION ==========
BREVO_API_KEY = os.getenv('BREVO_API_KEY')
BREVO_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL', 'hello@rootnetwork.com')
BLOG_NAME = os.getenv('BLOG_NAME', 'RootNetwork')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://rootnetwork1.netlify.app')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')

# ========== BREVO CLIENT ==========
def get_brevo_client():
    """Get Brevo API client"""
    configuration = Configuration()
    configuration.api_key['api-key'] = BREVO_API_KEY
    return ApiClient(configuration)

def send_email(to_email, subject, html_content, text_content=None, from_name=BLOG_NAME):
    """
    Send an email using Brevo API.
    Returns True on success, False on failure.
    """
    if not BREVO_API_KEY:
        print("⚠️ BREVO_API_KEY not configured. Email not sent.")
        print(f"Would have sent to: {to_email} | Subject: {subject}")
        return False

    try:
        with get_brevo_client() as api_client:
            api_instance = TransactionalEmailsApi(api_client)
            
            sender = SendSmtpEmailSender(
                name=from_name,
                email=BREVO_SENDER_EMAIL
            )
            to = [SendSmtpEmailTo(email=to_email)]
            
            email = SendSmtpEmail(
                sender=sender,
                to=to,
                subject=subject,
                html_content=html_content,
                text_content=text_content
            )
            
            result = api_instance.send_transac_email(email)
            print(f"✅ Email sent to {to_email}: {result.message_id}")
            return True
            
    except ApiException as e:
        print(f"❌ Brevo API error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


# ========== POST NOTIFICATIONS ==========

def notify_admin_new_post(post_id, admin_email=None):
    """Send email to admin when a new post is published."""
    from models import Post, User
    post = Post.query.get(post_id)
    if not post:
        print(f"❌ Post {post_id} not found")
        return False

    admin_email = admin_email or ADMIN_EMAIL
    if not admin_email:
        return False

    subject = f"📝 New Post Published: {post.title} - {BLOG_NAME}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #27ae60; color: white; padding: 15px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>📝 New Post Published</h2></div>
            <p><strong>Title:</strong> {post.title}</p>
            <p><strong>Author:</strong> {post.author.username if post.author else 'Unknown'}</p>
            <p><strong>Category:</strong> {post.category.name if post.category else 'Uncategorized'}</p>
            <p><a href="{FRONTEND_URL}/admin/posts">📋 View in Admin</a></p>
            <p><a href="{FRONTEND_URL}/blog/post/{post.slug}">🔗 View on Site</a></p>
        </div>
    </body>
    </html>
    """

    # Get all super admins
    super_admins = User.query.filter_by(is_super_admin=True).all()
    emails = list({admin_email} | {u.email for u in super_admins if u.email})

    for email in emails:
        send_email(email, subject, html_content)
    return True


def notify_post_author_post_created(post_id):
    """Send email to post author confirming their post was published."""
    from models import Post
    post = Post.query.get(post_id)
    if not post or not post.author or not post.author.email:
        return False

    subject = f"✅ Your Post '{post.title}' has been Published - {BLOG_NAME}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #27ae60; color: white; padding: 15px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>✅ Post Published Successfully</h2></div>
            <p>Hello {post.author.full_name or post.author.username},</p>
            <p>Your post <strong>"{post.title}"</strong> has been successfully published.</p>
            <p><strong>Category:</strong> {post.category.name if post.category else 'Uncategorized'}</p>
            <p><a href="{FRONTEND_URL}/blog/post/{post.slug}">🔗 View Your Post</a></p>
            <p><a href="{FRONTEND_URL}/admin/create">✍️ Write Another Post</a></p>
        </div>
    </body>
    </html>
    """

    return send_email(post.author.email, subject, html_content)


# ========== COMMENT NOTIFICATIONS ==========

def notify_admin_new_comment(comment_id, post_id, admin_email=None):
    """Send email to all super admins when a new comment is posted."""
    from models import Comment, Post, User
    comment = Comment.query.get(comment_id)
    post = Post.query.get(post_id)
    if not comment or not post:
        print(f"❌ Comment or post not found")
        return False

    admin_email = admin_email or ADMIN_EMAIL
    if not admin_email:
        return False

    super_admins = User.query.filter_by(is_super_admin=True).all()
    emails = list({admin_email} | {u.email for u in super_admins if u.email})

    subject = f"🔔 New Comment on '{post.title}' - {BLOG_NAME}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #e74c3c; color: white; padding: 15px; text-align: center; }}
            .comment-box {{ background: #f9f9f9; padding: 15px; margin: 15px 0; border-left: 4px solid #e74c3c; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>🔔 New Comment Alert</h2></div>
            <p><strong>📝 Post:</strong> {post.title}</p>
            <p><strong>👤 From:</strong> {comment.author} ({comment.email})</p>
            <div class="comment-box">
                <strong>💬 Comment:</strong><br>
                {comment.comment}
            </div>
            <p><a href="{FRONTEND_URL}/admin/comments">📋 Moderate Comment</a></p>
            <p><a href="{FRONTEND_URL}/blog/post/{post.slug}">🔗 View Post</a></p>
        </div>
    </body>
    </html>
    """

    for email in emails:
        send_email(email, subject, html_content)
    return True


def notify_author_new_comment(comment_id, post_id):
    """Send email to post author when someone comments on their post."""
    from models import Comment, Post
    comment = Comment.query.get(comment_id)
    post = Post.query.get(post_id)
    if not comment or not post:
        return False

    if not post.author or not post.author.email:
        return False

    if post.author.is_super_admin:
        return False

    subject = f"💬 New Comment on Your Post '{post.title}' - {BLOG_NAME}"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #3498db; color: white; padding: 15px; text-align: center; }}
            .comment-box {{ background: #f9f9f9; padding: 15px; margin: 15px 0; border-left: 4px solid #3498db; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>💬 New Comment on Your Post</h2></div>
            <p><strong>📝 Post:</strong> {post.title}</p>
            <p><strong>👤 From:</strong> {comment.author}</p>
            <div class="comment-box">
                <strong>💬 Comment:</strong><br>
                {comment.comment}
            </div>
            <p><a href="{FRONTEND_URL}/blog/post/{post.slug}">🔗 View Comment</a></p>
            <p><a href="{FRONTEND_URL}/admin/comments">📋 Manage Comments</a></p>
        </div>
    </body>
    </html>
    """

    return send_email(post.author.email, subject, html_content)


# ========== USER & SUBSCRIPTION EMAILS ==========

def send_welcome_email(email, name, username, password):
    """Send welcome email to newly created user."""
    subject = f"Welcome to {BLOG_NAME} - Your Writer Account"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4a5568; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .credentials-box {{ background: #f7fafc; border-left: 4px solid #48bb78; padding: 15px; margin: 20px 0; }}
            .password {{ font-family: monospace; font-size: 18px; font-weight: bold; color: #2f855a; }}
            .button {{ background: #48bb78; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block; }}
            .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #718096; }}
            .warning {{ background: #fef5e7; border-left: 4px solid #f39c12; padding: 15px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>Welcome to {BLOG_NAME}!</h2></div>
            <div class="content">
                <p>Hello {name or username},</p>
                <p>You have been added as a writer to <strong>{BLOG_NAME}</strong>.</p>
                <div class="credentials-box">
                    <p><strong>Your Account Details:</strong></p>
                    <p>📧 <strong>Email:</strong> {email}<br>
                    👤 <strong>Username:</strong> {username}</p>
                    <p>🔑 <strong>Your Password:</strong><br>
                    <span class="password">{password}</span></p>
                </div>
                <div class="warning">
                    <p><strong>⚠️ Important Security Notice:</strong></p>
                    <ul>
                        <li>Store this password in a secure place</li>
                        <li>Do not share your password with anyone</li>
                        <li>We recommend changing your password after first login</li>
                    </ul>
                </div>
                <p style="text-align: center;">
                    <a href="{FRONTEND_URL}/login" class="button">Click Here to Login</a>
                </p>
                <p>After logging in, you can:</p>
                <ul>
                    <li>Create and publish posts</li>
                    <li>Edit your profile</li>
                    <li>Change your password in Profile Settings</li>
                </ul>
                <p>If you didn't expect this email, please contact the site administrator.</p>
            </div>
            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>&copy; 2024 {BLOG_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_content = f"Welcome to {BLOG_NAME}!\n\nHello {name or username},\n\nYou have been added as a writer.\n\nAccount Details:\nEmail: {email}\nUsername: {username}\nPassword: {password}\n\nLogin here: {FRONTEND_URL}/login"
    return send_email(email, subject, html_content, text_content)


def send_verification_email(email, token):
    verify_url = f"{FRONTEND_URL}/subscribe/verify/{token}"
    subject = "Confirm your subscription"
    html_content = f"""
    <h2>Welcome!</h2>
    <p>Thank you for subscribing to RootNetwork. Please click the link below to confirm your email address:</p>
    <p><a href="{verify_url}">Confirm Subscription</a></p>
    <p>If you didn't request this, please ignore this email.</p>
    """
    return send_email(email, subject, html_content)


def send_post_notification_email(subscriber, post):
    post_url = f"{FRONTEND_URL}/blog/post/{post.slug}"
    subject = f"New article: {post.title}"
    html_content = f"""
    <h2>New post on RootNetwork</h2>
    <p><strong>{post.title}</strong></p>
    <p>{post.content[:200]}...</p>
    <p><a href="{post_url}">Read full article</a></p>
    <hr>
    <p style="font-size:12px; color:#888;">You received this because you subscribed to instant notifications. 
    <a href="{FRONTEND_URL}/subscribe/preferences?email={subscriber.email}">Manage preferences</a> | 
    <a href="{FRONTEND_URL}/subscribe/unsubscribe?email={subscriber.email}">Unsubscribe</a></p>
    """
    return send_email(subscriber.email, subject, html_content)


def send_digest_email(subscriber, posts, frequency='daily'):
    subject = f"Your {frequency} digest from RootNetwork"
    post_list = ''.join([
        f'<li><a href="{FRONTEND_URL}/blog/post/{p.slug}">{p.title}</a> - {p.category.name if p.category else "Uncategorized"}</li>'
        for p in posts
    ])
    html_content = f"""
    <h2>Your {frequency.capitalize()} Digest</h2>
    <p>Here are the latest articles we thought you'd like:</p>
    <ul>{post_list}</ul>
    <p><a href="{FRONTEND_URL}">Visit RootNetwork</a></p>
    <hr>
    <p style="font-size:12px; color:#888;">
        You received this because you subscribed to {frequency} updates. 
        <a href="{FRONTEND_URL}/subscribe/preferences?email={subscriber.email}">Manage preferences</a> | 
        <a href="{FRONTEND_URL}/subscribe/unsubscribe?email={subscriber.email}">Unsubscribe</a>
    </p>
    """
    return send_email(subscriber.email, subject, html_content)


def send_unsubscribe_confirmation(email):
    subject = "You've been unsubscribed"
    html_content = f"""
    <p>You have successfully unsubscribed from RootNetwork notifications.</p>
    <p>If this was a mistake, you can <a href="{FRONTEND_URL}/subscribe">subscribe again</a>.</p>
    """
    return send_email(email, subject, html_content)


# ========== SECURITY EMAILS ==========

def notify_admin_intrusion_detected(threat, ip_address, endpoint):
    admin_email = ADMIN_EMAIL
    if not admin_email:
        return False
    subject = f"🚨 SECURITY ALERT: Intrusion Detected - {BLOG_NAME}"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #e74c3c; color: white; padding: 15px; text-align: center; }}
            .alert {{ background: #ffeeee; border-left: 4px solid #e74c3c; padding: 15px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>🚨 SECURITY ALERT</h2></div>
            <div class="alert">
                <p><strong>Threat Type:</strong> {threat.get('type', 'Unknown')}</p>
                <p><strong>Severity:</strong> {threat.get('severity', 'Unknown')}</p>
                <p><strong>Pattern:</strong> {threat.get('pattern', 'Unknown')}</p>
                <p><strong>IP Address:</strong> {ip_address}</p>
                <p><strong>Endpoint:</strong> {endpoint}</p>
                <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            <p><a href="{FRONTEND_URL}/admin/security">🔒 View Security Dashboard</a></p>
        </div>
    </body>
    </html>
    """
    return send_email(admin_email, subject, html_content)


def notify_admin_failed_login(ip_address, attempts_count, username_attempted):
    admin_email = ADMIN_EMAIL
    if not admin_email:
        return False
    subject = f"⚠️ Multiple Failed Login Attempts - {BLOG_NAME}"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #f39c12; color: white; padding: 15px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h2>⚠️ Multiple Failed Login Attempts</h2></div>
            <p><strong>IP Address:</strong> {ip_address}</p>
            <p><strong>Attempts:</strong> {attempts_count}</p>
            <p><strong>Username Attempted:</strong> {username_attempted}</p>
            <p><a href="{FRONTEND_URL}/admin/security">🔒 View Security Dashboard</a></p>
        </div>
    </body>
    </html>
    """
    return send_email(admin_email, subject, html_content)


# ========== WRAPPER FUNCTIONS (NO BACKGROUND THREADS) ==========
# These now call the functions directly (no background threads needed)
# Brevo API is fast enough to be called synchronously

def send_admin_new_post_background(post_id, admin_email=None):
    return notify_admin_new_post(post_id, admin_email)

def send_post_author_post_created_background(post_id):
    return notify_post_author_post_created(post_id)

def send_admin_new_comment_background(comment_id, post_id, admin_email=None):
    return notify_admin_new_comment(comment_id, post_id, admin_email)

def send_author_new_comment_background(comment_id, post_id):
    return notify_author_new_comment(comment_id, post_id)

def send_welcome_email_background(email, name, username, password):
    return send_welcome_email(email, name, username, password)

def send_admin_intrusion_detected_background(threat, ip_address, endpoint):
    return notify_admin_intrusion_detected(threat, ip_address, endpoint)

def send_admin_failed_login_background(ip_address, attempts_count, username_attempted):
    return notify_admin_failed_login(ip_address, attempts_count, username_attempted)
