# blueprints/upload.py
from flask import jsonify, request, session, make_response
from exts import db, csrf
from models import User
from funcs import login_required, allowed_file, validate_and_sanitize_image
from middleware.security_middleware import security_middleware  
from . import upload_bp
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from services.logging_service import logger   # optional for security logs

# ========== UPLOAD FOLDERS ==========
UPLOAD_FOLDERS = {
    'posts': os.path.join('static', 'posts'),
    'profiles': os.path.join('static', 'profiles')
}

def ensure_upload_folders():
    for folder in UPLOAD_FOLDERS.values():
        os.makedirs(folder, exist_ok=True)

# ========== CORS HELPER ==========
def get_allowed_origin():
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork1.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    return origin if origin in allowed_origins else 'https://rootnetwork1.netlify.app'

# ---------- SINGLE POST IMAGE ----------
@upload_bp.route('/upload-post-image', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def upload_post_image():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    ensure_upload_folders()

    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"post_{datetime.now().timestamp()}.{ext}")
    filepath = os.path.join(UPLOAD_FOLDERS['posts'], filename)
    file.save(filepath)

    is_valid, msg, w, h = validate_and_sanitize_image(filepath)
    if not is_valid:
        os.remove(filepath)
        return jsonify({'error': msg}), 400

    # Optional: log upload
    user = User.query.get(session.get('user_id'))
    if user:
        logger.log_image_upload(user, 'post', filename)

    return jsonify({
        'image_url': f"/static/posts/{filename}",
        'message': 'Image uploaded successfully'
    }), 200

# ---------- SINGLE PROFILE IMAGE ----------
@upload_bp.route('/upload-profile-image', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def upload_profile_image():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    ensure_upload_folders()

    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"user_{session['user_id']}_{datetime.now().timestamp()}.{ext}")
    filepath = os.path.join(UPLOAD_FOLDERS['profiles'], filename)
    file.save(filepath)

    is_valid, msg, w, h = validate_and_sanitize_image(filepath)
    if not is_valid:
        os.remove(filepath)
        return jsonify({'error': msg}), 400

    user = User.query.get(session['user_id'])
    if user:
        if user.profile_image and user.profile_image != 'default-avatar.png':
            old = os.path.join(UPLOAD_FOLDERS['profiles'], os.path.basename(user.profile_image))
            if os.path.exists(old):
                os.remove(old)
        user.profile_image = f"profiles/{filename}"
        db.session.commit()
        # Optional: log
        logger.log_image_upload(user, 'profile', filename)

    return jsonify({
        'image_url': f"/static/profiles/{filename}",
        'message': 'Profile image uploaded successfully'
    }), 200

# ---------- MULTIPLE POST IMAGES ----------
@upload_bp.route('/upload-post-images', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def upload_post_images():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    ensure_upload_folders()

    if 'images' not in request.files:
        return jsonify({'error': 'No images provided'}), 400

    files = request.files.getlist('images')
    if not files:
        return jsonify({'error': 'No images selected'}), 400

    if len(files) > 10:
        return jsonify({'error': 'Maximum 10 images allowed'}), 400

    uploaded = []
    saved_paths = []

    for file in files:
        if file.filename == '':
            continue
        if not allowed_file(file.filename):
            # Cleanup all saved files
            for path in saved_paths:
                if os.path.exists(path):
                    os.remove(path)
            return jsonify({'error': f'File type not allowed: {file.filename}'}), 400

        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"post_{datetime.now().timestamp()}_{os.urandom(4).hex()}.{ext}")
        filepath = os.path.join(UPLOAD_FOLDERS['posts'], filename)
        file.save(filepath)
        saved_paths.append(filepath)

        is_valid, msg, w, h = validate_and_sanitize_image(filepath)
        if not is_valid:
            for path in saved_paths:
                if os.path.exists(path):
                    os.remove(path)
            return jsonify({'error': msg}), 400

        url = f"/static/posts/{filename}"
        uploaded.append({
            'url': url,
            'caption': '',
            'alt': ''
        })

    # Optional: log (could log count instead of each file)
    user = User.query.get(session.get('user_id'))
    if user:
        logger.log_activity(
            user_id=user.id,
            username=user.username,
            action='upload_images',
            action_details=f'Uploaded {len(uploaded)} images',
            endpoint='/api/upload-post-images',
            method='POST',
            status=200
        )

    return jsonify({
        'images': uploaded,
        'message': f'{len(uploaded)} images uploaded successfully'
    }), 200
