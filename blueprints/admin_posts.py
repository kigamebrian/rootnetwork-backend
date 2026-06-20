# blueprints/admin_posts.py
from flask import jsonify, request, session
from models import Post, generate_slug, User
from exts import db, csrf
from funcs import login_required, sanitize_html, get_session_id
from middleware.security_middleware import security_middleware
from . import admin_posts_bp
from datetime import datetime, timezone
from services import send_admin_new_post_background, send_post_author_post_created_background
from services.logging_service import logger   # <-- ADDED for security logs

# ---------- ANALYTICS TRACKING (optional) ----------
def track_action(action_type, action_details, target_id, target_type):
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
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(action)
        db.session.commit()
    except Exception as e:
        print(f"Failed to track action: {e}")

# ---------- HELPER: parse scheduled datetime ----------
def parse_scheduled_datetime(dt_str):
    if not dt_str:
        return None
    try:
        if dt_str.endswith('Z'):
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception as e:
        print(f"Error parsing datetime: {e}")
        return None

# ---------- GET admin posts ----------
@admin_posts_bp.route('/posts', methods=['GET'])
@csrf.exempt
def get_admin_posts():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        user = User.query.get(session['user_id'])
        status_filter = request.args.get('status', 'all')
        if user.is_super_admin:
            query = Post.query.order_by(Post.id.desc())
        else:
            query = Post.query.filter_by(author_id=user.id).order_by(Post.id.desc())
        if status_filter != 'all':
            query = query.filter_by(status=status_filter)
        posts = query.all()
        return jsonify([{
            'id': p.id,
            'slug': p.slug,
            'title': p.title,
            'content': p.content[:500] if len(p.content) > 500 else p.content,
            'image': p.image,
            'images': p.images or [],
            'timestamp': p.timestamp.isoformat() if p.timestamp else None,
            'status': p.status,
            'scheduled_for': p.scheduled_for.isoformat() if p.scheduled_for else None,
            'category': p.category.name if p.category else 'Uncategorized',
            'category_id': p.category.id if p.category else None,
            'author_id': p.author_id,
            'author_name': p.author.username if p.author else 'Unknown',
            'comment_count': p.comments.count()
        } for p in posts])
    except Exception as e:
        print(f"Error in get_admin_posts: {e}")
        return jsonify({'error': str(e)}), 500

# ---------- CREATE post ----------
@admin_posts_bp.route('/posts', methods=['POST'])
@csrf.exempt
@login_required
@security_middleware
def create_post():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        data = request.json
        sanitized_title = data.get('title', '')[:200]
        sanitized_content = sanitize_html(data.get('content', ''))
        if not sanitized_title or len(sanitized_title) < 3:
            return jsonify({'error': 'Title must be at least 3 characters'}), 400

        slug = generate_slug(sanitized_title)
        original_slug = slug
        counter = 1
        while Post.query.filter_by(slug=slug).first():
            slug = f"{original_slug}-{counter}"
            counter += 1

        status = data.get('status', 'draft')
        scheduled_for = None
        timestamp = None
        published_at = None
        now = datetime.now(timezone.utc)

        if status == 'published':
            timestamp = now
            published_at = now
        elif status == 'scheduled':
            scheduled_for = parse_scheduled_datetime(data.get('scheduled_for'))
            if scheduled_for and scheduled_for <= now:
                status = 'published'
                timestamp = now
                published_at = now
                scheduled_for = None

        images = data.get('images', [])
        if not isinstance(images, list):
            images = []

        post = Post(
            title=sanitized_title,
            slug=slug,
            content=sanitized_content,
            image=data.get('image'),
            images=images,
            category_id=data.get('category_id') if data.get('category_id') else None,
            author_id=session['user_id'],
            timestamp=timestamp,
            status=status,
            scheduled_for=scheduled_for,
            published_at=published_at
        )
        db.session.add(post)
        db.session.commit()

        # --- Send notifications ---
        if status == 'published':
            send_admin_new_post_background(post)
            send_post_author_post_created_background(post)

        # --- SECURITY LOGGING ---
        user = User.query.get(session['user_id'])
        logger.log_post_creation(user, post.id, post.title)

        # --- ANALYTICS ---
        track_action(
            action_type='create_post',
            action_details=f'Created post: {sanitized_title} (Status: {status})',
            target_id=post.id,
            target_type='post'
        )

        status_message = {
            'draft': 'saved as draft',
            'published': 'published successfully',
            'scheduled': f'scheduled for {scheduled_for}'
        }.get(status, 'saved')

        return jsonify({
            'message': f'Post {status_message}',
            'id': post.id,
            'slug': post.slug,
            'status': status
        }), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error in create_post: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ---------- GET post for edit ----------
@admin_posts_bp.route('/posts/<string:slug>', methods=['GET'])
@csrf.exempt
def get_post_for_edit(slug):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        post = Post.query.filter_by(slug=slug).first()
        if not post:
            return jsonify({'error': 'Post not found'}), 404
        user = User.query.get(session['user_id'])
        if not user.is_super_admin and post.author_id != user.id:
            return jsonify({'error': 'You can only edit your own posts'}), 403
        return jsonify({
            'id': post.id,
            'slug': post.slug,
            'title': post.title,
            'content': post.content,
            'image': post.image,
            'images': post.images or [],
            'category_id': post.category_id,
            'author_id': post.author_id,
            'status': post.status,
            'scheduled_for': post.scheduled_for.isoformat() if post.scheduled_for else None,
            'published_at': post.published_at.isoformat() if post.published_at else None
        }), 200
    except Exception as e:
        print(f"Error in get_post_for_edit: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ---------- UPDATE post ----------
@admin_posts_bp.route('/posts/<int:post_id>', methods=['PUT'])
@csrf.exempt
@login_required
@security_middleware
def update_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        post = Post.query.get_or_404(post_id)
        user = User.query.get(session['user_id'])
        if not user.is_super_admin and post.author_id != user.id:
            return jsonify({'error': 'You can only edit your own posts'}), 403

        data = request.json
        old_title = post.title
        changes_made = False
        now = datetime.now(timezone.utc)

        if data.get('title'):
            sanitized_title = data['title'][:200]
            if sanitized_title != post.title:
                post.title = sanitized_title
                new_slug = generate_slug(sanitized_title)
                original_slug = new_slug
                counter = 1
                while Post.query.filter(Post.slug == new_slug, Post.id != post.id).first():
                    new_slug = f"{original_slug}-{counter}"
                    counter += 1
                post.slug = new_slug
                changes_made = True

        if data.get('content'):
            sanitized_content = data['content']
            if post.content != sanitized_content:
                post.content = sanitized_content
                changes_made = True

        if 'image' in data:
            if post.image != data['image']:
                post.image = data['image']
                changes_made = True

        if 'images' in data:
            new_images = data['images']
            if isinstance(new_images, list) and post.images != new_images:
                post.images = new_images
                changes_made = True

        if 'category_id' in data:
            if post.category_id != data['category_id']:
                post.category_id = data['category_id']
                changes_made = True

        if 'status' in data:
            new_status = data['status']
            if new_status != post.status:
                old_status = post.status
                post.status = new_status
                changes_made = True
                if new_status == 'scheduled':
                    scheduled_for = parse_scheduled_datetime(data.get('scheduled_for'))
                    post.scheduled_for = scheduled_for
                    post.timestamp = None
                    post.published_at = None
                elif new_status == 'published':
                    post.timestamp = now
                    post.published_at = now
                    post.scheduled_for = None
                elif new_status == 'draft':
                    post.timestamp = None
                    post.published_at = None
                    post.scheduled_for = None
            elif new_status == 'scheduled' and data.get('scheduled_for'):
                scheduled_for = parse_scheduled_datetime(data['scheduled_for'])
                if post.scheduled_for != scheduled_for:
                    post.scheduled_for = scheduled_for
                    changes_made = True

        if changes_made:
            db.session.commit()
            # --- SECURITY LOGGING ---
            logger.log_post_update(user, post.id, post.title)
        else:
            print("No changes detected")

        # --- ANALYTICS ---
        track_action(
            action_type='update_post',
            action_details=f'Updated post: {old_title} -> {post.title}',
            target_id=post_id,
            target_type='post'
        )

        return jsonify({'message': 'Post updated successfully', 'slug': post.slug}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error in update_post: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ---------- DELETE post ----------
@admin_posts_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@csrf.exempt
@login_required
@security_middleware
def delete_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    try:
        post = Post.query.get_or_404(post_id)
        user = User.query.get(session['user_id'])
        if not user.is_super_admin and post.author_id != user.id:
            return jsonify({'error': 'You can only delete your own posts'}), 403

        post_title = post.title
        db.session.delete(post)
        db.session.commit()

        # --- SECURITY LOGGING ---
        logger.log_post_deletion(user, post_id, post_title)

        # --- ANALYTICS ---
        track_action(
            action_type='delete_post',
            action_details=f'Deleted post: {post_title}',
            target_id=post_id,
            target_type='post'
        )

        return jsonify({'message': 'Post deleted successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error in delete_post: {e}")
        return jsonify({'error': str(e)}), 500
