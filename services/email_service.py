# backend/services/email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from datetime import datetime
from services.background_email import send_email_background

load_dotenv()

# Email configuration
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER)
BLOG_NAME = os.getenv('BLOG_NAME', 'RootNetwork')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

def send_welcome_email(email, name, username, password):
    """Send welcome email to newly created user with their credentials"""
    
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
            <div class="header">
                <h2>Welcome to {BLOG_NAME}!</h2>
            </div>
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
                
                <p>If you didn't expect this email or have any questions, please contact the site administrator.</p>
            </div>
            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>&copy; 2024 {BLOG_NAME}. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_content = f"""
    Welcome to {BLOG_NAME}!
    
    Hello {name or username},
    
    You have been added as a writer to {BLOG_NAME}.
    
    Your Account Details:
    Email: {email}
    Username: {username}
    Password: {password}
    
    Login here: {FRONTEND_URL}/login
    
    Important Security Notice:
    - Store this password in a secure place
    - Do not share your password with anyone
    - We recommend changing your password after first login
    
    After logging in, you can:
    - Create and publish posts
    - Edit your profile
    - Change your password in Profile Settings
    
    If you didn't expect this email, please contact the site administrator.
    """
    
    return send_email(email, subject, html_content, text_content)

def send_email(to_email, subject, html_content, text_content=None):
    """Generic email sender"""
    try:
        if not SMTP_USER or not SMTP_PASSWORD:
            print("⚠️ Email not configured. SMTP credentials missing.")
            print(f"Would have sent email to: {to_email}")
            print(f"Subject: {subject}")
            return False
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        
        # Attach plain text version
        if text_content:
            msg.attach(MIMEText(text_content, 'plain'))
        
        # Attach HTML version
        msg.attach(MIMEText(html_content, 'html'))
        
        # Send email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Email sent to {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email to {to_email}: {e}")
        return False

# Add these to your email_service.py

def email_to_admin(comment, post, admin_email=None):
    """Send email to admin when new comment is posted"""
    admin_email = admin_email or os.getenv('ADMIN_EMAIL', SMTP_USER)
    if not admin_email:
        print("⚠️ Admin email not configured")
        return False
    
    subject = f"New Comment on '{post.title}' - {BLOG_NAME}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4a5568; color: white; padding: 10px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h3>New Comment Alert</h3>
            </div>
            <p><strong>Post:</strong> {post.title}</p>
            <p><strong>From:</strong> {comment.author} ({comment.email})</p>
            <p><strong>Comment:</strong><br>{comment.comment}</p>
            <p><a href="{FRONTEND_URL}/admin/comments">Click here to moderate this comment</a></p>
        </div>
    </body>
    </html>
    """
    
    return send_email(admin_email, subject, html_content)


def email_to_author(comment, post):
    """Send email to post author when new comment is posted"""
    author_email = post.author.email if post.author else None
    if not author_email:
        return False
    
    subject = f"New Comment on Your Post '{post.title}' - {BLOG_NAME}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4a5568; color: white; padding: 10px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h3>New Comment on Your Post</h3>
            </div>
            <p><strong>Post:</strong> {post.title}</p>
            <p><strong>From:</strong> {comment.author}</p>
            <p><strong>Comment:</strong><br>{comment.comment}</p>
            <p><a href="{FRONTEND_URL}/blog/post/{post.slug}">Click here to view the comment</a></p>
        </div>
    </body>
    </html>
    """
    
    return send_email(author_email, subject, html_content)


def email_to_author_comment_approved(comment, post):
    """Send email to comment author when their comment is approved"""
    if not comment.email:
        return False
    
    subject = f"Your Comment on '{post.title}' has been Approved - {BLOG_NAME}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4a5568; color: white; padding: 10px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h3>Your Comment Has Been Approved</h3>
            </div>
            <p>Your comment on <strong>"{post.title}"</strong> has been approved and is now visible to others.</p>
            <p><strong>Your comment:</strong><br>{comment.comment}</p>
            <p><a href="{FRONTEND_URL}/blog/post/{post.slug}">Click here to view your comment</a></p>
        </div>
    </body>
    </html>
    """
    
    return send_email(comment.email, subject, html_content)


def notify_admin_new_comment(comment, post, admin_email=None):
    """Send email to admin when new comment is posted"""
    from models import User
    admin_email = admin_email or os.getenv('ADMIN_EMAIL', SMTP_USER)
    
    # Get all super admins
    super_admins = User.query.filter_by(is_super_admin=True).all()
    emails = [admin_email] + [u.email for u in super_admins if u.email]
    emails = list(set(emails))  
    
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
            <div class="header">
                <h2>🔔 New Comment Alert</h2>
            </div>
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


def notify_author_new_comment(comment, post):
    """Send email to post author when someone comments on their post"""
    if not post.author or not post.author.email:
        return False
    
    # Don't notify if author is super admin (they already get admin notification)
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
            <div class="header">
                <h2>💬 New Comment on Your Post</h2>
            </div>
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


def notify_admin_new_post(post, admin_email=None):
    """Send email to admin when a new post is published"""
    admin_email = admin_email or os.getenv('ADMIN_EMAIL', SMTP_USER)
    
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
            <div class="header">
                <h2>📝 New Post Published</h2>
            </div>
            <p><strong>Title:</strong> {post.title}</p>
            <p><strong>Author:</strong> {post.author.username if post.author else 'Unknown'}</p>
            <p><strong>Category:</strong> {post.category.name if post.category else 'Uncategorized'}</p>
            <p><a href="{FRONTEND_URL}/admin/posts">📋 View in Admin</a></p>
            <p><a href="{FRONTEND_URL}/blog/post/{post.slug}">🔗 View on Site</a></p>
        </div>
    </body>
    </html>
    """
    
    return send_email(admin_email, subject, html_content)


def notify_post_author_post_created(post):
    """Send email to post author confirming their post was published"""
    if not post.author or not post.author.email:
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
            <div class="header">
                <h2>✅ Post Published Successfully</h2>
            </div>
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


def notify_admin_intrusion_detected(threat, ip_address, endpoint):
    """Send email to admin when intrusion is detected"""
    admin_email = os.getenv('ADMIN_EMAIL', SMTP_USER)
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
            <div class="header">
                <h2>🚨 SECURITY ALERT</h2>
            </div>
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
    """Send email to admin when multiple failed login attempts detected"""
    admin_email = os.getenv('ADMIN_EMAIL', SMTP_USER)
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
            <div class="header">
                <h2>⚠️ Multiple Failed Login Attempts</h2>
            </div>
            <p><strong>IP Address:</strong> {ip_address}</p>
            <p><strong>Attempts:</strong> {attempts_count}</p>
            <p><strong>Username Attempted:</strong> {username_attempted}</p>
            <p><a href="{FRONTEND_URL}/admin/security">🔒 View Security Dashboard</a></p>
        </div>
    </body>
    </html>
    """
    
    return send_email(admin_email, subject, html_content)

def send_admin_new_post_background(post, admin_email=None):
    """Send admin new post notification in background"""
    from services.email_service import notify_admin_new_post
    send_email_background(notify_admin_new_post, post, admin_email)

def send_post_author_post_created_background(post):
    """Send author post created notification in background"""
    from services.email_service import notify_post_author_post_created
    send_email_background(notify_post_author_post_created, post)

def send_admin_new_comment_background(comment, post, admin_email=None):
    """Send admin new comment notification in background"""
    from services.email_service import notify_admin_new_comment
    send_email_background(notify_admin_new_comment, comment, post, admin_email)

def send_author_new_comment_background(comment, post):
    """Send author new comment notification in background"""
    from services.email_service import notify_author_new_comment
    send_email_background(notify_author_new_comment, comment, post)

def send_welcome_email_background(email, name, username, password):
    """Send welcome email in background"""
    from services.email_service import send_welcome_email
    send_email_background(send_welcome_email, email, name, username, password)

def send_admin_intrusion_detected_background(threat, ip_address, endpoint):
    """Send intrusion alert in background"""
    from services.email_service import notify_admin_intrusion_detected
    send_email_background(notify_admin_intrusion_detected, threat, ip_address, endpoint)

def send_admin_failed_login_background(ip_address, attempts_count, username_attempted):
    """Send failed login alert in background"""
    from services.email_service import notify_admin_failed_login
    send_email_background(notify_admin_failed_login, ip_address, attempts_count, username_attempted)