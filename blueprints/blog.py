# blueprints/blog.py
from flask import jsonify, request, make_response
from models import Post, Category, Comment, CommentReply
from exts import db, csrf
from funcs import sanitize_html, limiter
from . import blog_bp
from datetime import datetime
from utils.seo import seo_helper  
from services import send_admin_new_comment_background, send_author_new_comment_background
from services.logging_service import logger

# ---------- GET posts (public listing) ----------
@blog_bp.route('/posts', methods=['GET'], endpoint='blog_posts')
@csrf.exempt
def get_posts():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    category_id = request.args.get('category_id', type=int)
    query = Post.query.filter_by(status='published').order_by(Post.timestamp.desc())
    if category_id:
        query = query.filter_by(category_id=category_id)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    posts = []
    for post in pagination.items:
        posts.append({
            'id': post.id,
            'slug': post.slug,
            'title': post.title,
            'content': post.content[:300] + '...' if len(post.content) > 300 else post.content,
            'image': post.image,
            'images': post.images or [],
            'timestamp': post.timestamp.isoformat(),
            'category': {
                'id': post.category.id,
                'name': post.category.name
            } if post.category else None,
            'comment_count': post.comments.count(),
            'author': {
                'id': post.author.id,
                'username': post.author.username,
                'full_name': post.author.full_name,
                'profile_image': post.author.profile_image
            } if post.author else None
        })
    return jsonify({'posts': posts, 'total': pagination.total, 'page': page, 'pages': pagination.pages})

# ---------- GET single post ----------
@blog_bp.route('/posts/<string:identifier>', methods=['GET'])
@csrf.exempt
def get_post(identifier):
    post = Post.query.filter_by(slug=identifier).first()
    if not post and identifier.isdigit():
        post = Post.query.get(int(identifier))
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    comments = []
    for comment in post.comments:
        if comment.reviewed:
            replies = []
            for reply in comment.comment_replies:
                if reply.reviewed:
                    replies.append({
                        'id': reply.id,
                        'author': reply.author,
                        'content': reply.comment_reply,
                        'timestamp': reply.timestamp.isoformat(),
                        'from_admin': reply.from_admin
                    })
            comments.append({
                'id': comment.id,
                'author': comment.author,
                'email': comment.email,
                'site': comment.site,
                'content': comment.comment,
                'timestamp': comment.timestamp.isoformat(),
                'from_admin': comment.from_admin,
                'reviewed': comment.reviewed,
                'replies': replies
            })

    meta_description = seo_helper.generate_meta_description(post.content)
    reading_time = seo_helper.calculate_read_time(post.content)
    keywords = seo_helper.generate_keywords(post.title, post.category.name if post.category else None)

    return jsonify({
        'id': post.id,
        'slug': post.slug,
        'title': post.title,
        'content': post.content,
        'image': post.image,
        'images': post.images or [],
        'timestamp': post.timestamp.isoformat(),
        'category': {
            'id': post.category.id,
            'name': post.category.name
        } if post.category else None,
        'author': {
            'id': post.author.id,
            'username': post.author.username,
            'full_name': post.author.full_name,
            'profile_image': post.author.profile_image
        } if post.author else None,
        'comments': comments,
        'meta_description': meta_description,
        'reading_time': reading_time,
        'keywords': keywords
    })

# ---------- GET categories (FIXED: added slug) ----------
@blog_bp.route('/categories', methods=['GET'])
@csrf.exempt
def get_categories():
    categories = Category.query.order_by(Category.name.asc()).all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'slug': cat.name.lower().replace(' ', '-'),  # <-- FIXED: added slug
        'post_count': cat.posts.count()
    } for cat in categories])

# ---------- ADD COMMENT (and reply) ----------
@blog_bp.route('/posts/<int:post_id>/comments', methods=['POST', 'OPTIONS'])
@csrf.exempt
def add_comment(post_id):
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://rootnetwork1.netlify.app')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    post = Post.query.get_or_404(post_id)
    data = request.json

    author = data.get('author', 'Anonymous')[:50]
    email = data.get('email', '')[:254]
    site = data.get('site', '')[:255]
    content = sanitize_html(data.get('content', ''))

    if not content:
        return jsonify({'error': 'Comment content is required'}), 400

    parent_id = data.get('parent_id')

    try:
        if parent_id:
            parent_comment = Comment.query.get(parent_id)
            if not parent_comment:
                return jsonify({'error': 'Parent comment not found'}), 404

            reply = CommentReply(
                author=author,
                email=email,
                site=site,
                comment_reply=content,
                comment_id=parent_id,
                reviewed=False,
                from_admin=False,
                timestamp=datetime.now()
            )
            db.session.add(reply)
            db.session.commit()

            logger.log_activity(
                user_id=None,
                username=author,
                action='add_reply',
                action_details=f'Added reply to comment {parent_id} on post: {post.title}',
                endpoint=f'/api/posts/{post_id}/comments',
                method='POST',
                status=201
            )

            send_admin_new_comment_background(reply, post)
            send_author_new_comment_background(reply, post)

            return jsonify({'message': 'Reply added successfully. Awaiting approval.'}), 201

        else:
            comment = Comment(
                author=author,
                email=email,
                site=site,
                comment=content,
                post_id=post_id,
                reviewed=False,
                from_admin=False,
                timestamp=datetime.now()
            )
            db.session.add(comment)
            db.session.commit()

            logger.log_activity(
                user_id=None,
                username=author,
                action='add_comment',
                action_details=f'Added comment on post: {post.title}',
                endpoint=f'/api/posts/{post_id}/comments',
                method='POST',
                status=201
            )

            send_admin_new_comment_background(comment, post)
            send_author_new_comment_background(comment, post)

            return jsonify({'message': 'Comment added successfully. Awaiting approval.'}), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error adding comment/reply: {e}")
        return jsonify({'error': str(e)}), 500

# ---------- RELATED POSTS ----------
@blog_bp.route('/posts/<int:post_id>/related', methods=['GET'])
@csrf.exempt
def get_related_posts(post_id):
    try:
        post = Post.query.get_or_404(post_id)
        related = []

        if post.category_id:
            same_category = Post.query.filter(
                Post.category_id == post.category_id,
                Post.id != post_id
            ).order_by(Post.timestamp.desc()).limit(4).all()
            related.extend(same_category)

        if len(related) < 4:
            remaining = 4 - len(related)
            recent_posts = Post.query.filter(
                Post.id != post_id,
                Post.id.notin_([p.id for p in related]) if related else True
            ).order_by(Post.timestamp.desc()).limit(remaining).all()
            related.extend(recent_posts)

        return jsonify([{
            'id': p.id,
            'slug': p.slug,
            'title': p.title,
            'content': p.content[:150] + '...' if len(p.content) > 150 else p.content,
            'image': p.image,
            'images': p.images or [],
            'timestamp': p.timestamp.isoformat(),
            'category': p.category.name if p.category else 'Uncategorized',
            'author': p.author.username if p.author else 'Unknown'
        } for p in related]), 200

    except Exception as e:
        print(f"Error getting related posts: {e}")
        return jsonify([]), 200

# ---------- NAV CATEGORIES ----------
@blog_bp.route('/nav-categories', methods=['GET'])
@csrf.exempt
def get_nav_categories():
    try:
        categories = Category.query.order_by(Category.name.asc()).limit(5).all()
        return jsonify([{
            'id': cat.id,
            'name': cat.name,
            'slug': cat.name.lower().replace(' ', '-'),
            'post_count': cat.posts.count()
        } for cat in categories]), 200
    except Exception as e:
        print(f"Error getting nav categories: {e}")
        return jsonify([]), 200
