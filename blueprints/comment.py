# blueprints/comment.py
from flask import jsonify, request, session, make_response
from models import Comment, User
from exts import db, csrf
from funcs import login_required, limiter, get_session_id
from middleware.security_middleware import security_middleware
from . import comment_bp
from datetime import datetime

def track_action(action_type, action_details, target_id, target_type):
    """Helper function to track user actions"""
    try:
        from models import UserAction
        session_id = get_session_id()
        user_id = session.get('user_id')
        
        action = UserAction(
            user_id=user_id,
            session_id=session_id,
            action_type=action_type[:50],
            action_details=action_details[:500],
            target_id=target_id,
            target_type=target_type[:50],
            timestamp=datetime.now()
        )
        db.session.add(action)
        db.session.commit()
    except Exception as e:
        print(f"Failed to track action: {e}")

@comment_bp.route('/comments', methods=['GET'])
@csrf.exempt
def get_comments():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        user = User.query.get(session['user_id'])
        filter_type = request.args.get('filter', 'all')
        
        if user.is_super_admin:
            query = Comment.query.order_by(Comment.timestamp.desc())
        else:
            user_post_ids = [post.id for post in user.posts]
            if not user_post_ids:
                return jsonify([])
            query = Comment.query.filter(Comment.post_id.in_(user_post_ids)).order_by(Comment.timestamp.desc())
        
        if filter_type == 'reviewed':
            query = query.filter_by(reviewed=True)
        elif filter_type == 'unreviewed':
            query = query.filter_by(reviewed=False)
        
        comments = query.all()
        return jsonify([{
            'id': c.id,
            'author': c.author,
            'email': c.email,
            'content': c.comment[:200] if len(c.comment) > 200 else c.comment,
            'timestamp': c.timestamp.isoformat(),
            'reviewed': c.reviewed,
            'from_admin': c.from_admin,
            'post_title': c.post.title if c.post else 'Unknown',
            'post_id': c.post_id,
            'post_author_id': c.post.author_id if c.post else None
        } for c in comments])
    except Exception as e:
        print(f"Error in get_comments: {e}")
        return jsonify({'error': str(e)}), 500

@comment_bp.route('/comments/<int:comment_id>/approve', methods=['POST'])
@csrf.exempt
@login_required
@security_middleware
def approve_comment(comment_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        user = User.query.get(session['user_id'])
        
        if not user.is_super_admin:
            return jsonify({'error': 'Only super admin can approve comments'}), 403
        
        comment = Comment.query.get_or_404(comment_id)
        comment.reviewed = True
        db.session.commit()
        
        # Track action
        track_action(
            action_type='approve_comment',
            action_details=f'Approved comment on post: {comment.post.title if comment.post else "Unknown"}',
            target_id=comment_id,
            target_type='comment'
        )
        
        return jsonify({'message': 'Comment approved successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error in approve_comment: {e}")
        return jsonify({'error': str(e)}), 500

@comment_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@csrf.exempt
@login_required
@security_middleware
def delete_comment(comment_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        user = User.query.get(session['user_id'])
        comment = Comment.query.get_or_404(comment_id)
        post_title = comment.post.title if comment.post else 'Unknown'
        
        if user.is_super_admin:
            db.session.delete(comment)
            db.session.commit()
            
            track_action(
                action_type='delete_comment',
                action_details=f'Deleted comment from post: {post_title}',
                target_id=comment_id,
                target_type='comment'
            )
            return jsonify({'message': 'Comment deleted successfully'})
        
        if comment.post and comment.post.author_id == user.id:
            db.session.delete(comment)
            db.session.commit()
            
            track_action(
                action_type='delete_comment',
                action_details=f'Deleted comment from own post: {post_title}',
                target_id=comment_id,
                target_type='comment'
            )
            return jsonify({'message': 'Comment deleted successfully'})
        
        return jsonify({'error': 'You can only delete comments on your own posts'}), 403
    except Exception as e:
        db.session.rollback()
        print(f"Error in delete_comment: {e}")
        return jsonify({'error': str(e)}), 500