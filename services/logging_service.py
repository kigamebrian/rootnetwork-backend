from flask import request, has_request_context
from models import ActivityLog, db
import traceback

class ActivityLogger:
    
    @staticmethod
    def get_request_info():
        """Safely get request information, handling cases where there's no request context"""
        if not has_request_context():
            return {
                'ip': 'CLI',
                'user_agent': 'Command Line',
                'endpoint': 'CLI',
                'method': 'CLI'
            }
        
        return {
            'ip': request.headers.get('X-Forwarded-For', request.remote_addr),
            'user_agent': request.headers.get('User-Agent', '')[:500],
            'endpoint': request.path[:200] if has_request_context() else 'Unknown',
            'method': request.method if has_request_context() else 'Unknown'
        }
    
    @staticmethod
    def log_activity(user_id, username, action, action_details, endpoint, method, status):
        """Log user activity with error handling"""
        try:
            request_info = ActivityLogger.get_request_info()
            
            log = ActivityLog(
                user_id=user_id,
                username=username[:80] if username else 'Unknown',
                action=action[:50],
                action_details=action_details[:500] if action_details else None,
                ip_address=request_info['ip'][:50],
                user_agent=request_info['user_agent'][:500],
                endpoint=endpoint[:200] if endpoint else request_info['endpoint'],
                method=method[:10] if method else request_info['method'],
                status=status
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"Failed to log activity: {e}")
            db.session.rollback()
    
    @staticmethod
    def log_login(user, success=True):
        """Log login attempts"""
        action = 'login_success' if success else 'login_failed'
        
        # Get request info safely
        request_info = ActivityLogger.get_request_info()
        
        ActivityLogger.log_activity(
            user_id=user.id if user else None,
            username=user.username if user else 'Unknown',
            action=action,
            action_details=f"Login attempt from {request_info['ip']}",
            endpoint='/api/login',
            method='POST',
            status=200 if success else 401
        )
    
    @staticmethod
    def log_logout(user):
        """Log logout events"""
        ActivityLogger.log_activity(
            user_id=user.id,
            username=user.username,
            action='logout',
            action_details='User logged out',
            endpoint='/api/logout',
            method='POST',
            status=200
        )
    
    @staticmethod
    def log_post_creation(user, post_id, post_title):
        """Log post creation"""
        ActivityLogger.log_activity(
            user_id=user.id,
            username=user.username,
            action='create_post',
            action_details=f'Created post: {post_title[:100]}',
            endpoint='/api/admin/posts',
            method='POST',
            status=201
        )
    
    @staticmethod
    def log_post_update(user, post_id, post_title):
        """Log post update"""
        ActivityLogger.log_activity(
            user_id=user.id,
            username=user.username,
            action='update_post',
            action_details=f'Updated post: {post_title[:100]} (ID: {post_id})',
            endpoint=f'/api/admin/posts/{post_id}',
            method='PUT',
            status=200
        )
    
    @staticmethod
    def log_post_deletion(user, post_id, post_title):
        """Log post deletion"""
        ActivityLogger.log_activity(
            user_id=user.id,
            username=user.username,
            action='delete_post',
            action_details=f'Deleted post: {post_title[:100]} (ID: {post_id})',
            endpoint=f'/api/admin/posts/{post_id}',
            method='DELETE',
            status=200
        )
    
    @staticmethod
    def log_image_upload(user, image_type, filename):
        """Log image uploads"""
        ActivityLogger.log_activity(
            user_id=user.id,
            username=user.username,
            action='upload_image',
            action_details=f'Uploaded {image_type} image: {filename}',
            endpoint='/api/upload-post-image',
            method='POST',
            status=200
        )
    
    @staticmethod
    def log_comment_action(user, comment_id, action, post_title):
        """Log comment actions (approve, delete, etc.)"""
        ActivityLogger.log_activity(
            user_id=user.id if user else None,
            username=user.username if user else 'Anonymous',
            action=f'comment_{action}',
            action_details=f'{action} comment on post: {post_title[:100]}',
            endpoint='/api/admin/comments',
            method='POST',
            status=200
        )

logger = ActivityLogger()