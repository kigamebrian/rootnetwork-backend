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

# Upload folders
UPLOAD_FOLDERS = {
    'posts': os.path.join('static', 'posts'),
    'profiles': os.path.join('static', 'profiles')
}

def ensure_upload_folders():
    """Create upload folders if they don't exist."""
    for folder in UPLOAD_FOLDERS.values():
        os.makedirs(folder, exist_ok=True)

# ========== SINGLE IMAGE UPLOAD (post) ==========
@upload_bp.route('/upload-post-image', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def upload_post_image():
    # Handle preflight
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://rootnetwork1.netlify.app')
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

    valid, msg, w, h = validate_and_sanitize_image(filepath)
    if not valid:
        os.remove(filepath)
        return jsonify({'error': msg}), 400

    return jsonify({
        'image_url': f"/static/posts/{filename}",
        'message': 'Image uploaded successfully'
    }), 200

# ========== SINGLE IMAGE UPLOAD (profile) ==========
@upload_bp.route('/upload-profile-image', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def upload_profile_image():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://rootnetwork1.netlify.app')
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

    valid, msg, w, h = validate_and_sanitize_image(filepath)
    if not valid:
        os.remove(filepath)
        return jsonify({'error': msg}), 400

    user = User.query.get(session['user_id'])
    if user:
        # Remove old profile image if not default
        if user.profile_image and user.profile_image != 'default-avatar.png':
            old_path = os.path.join(UPLOAD_FOLDERS['profiles'], os.path.basename(user.profile_image))
            if os.path.exists(old_path):
                os.remove(old_path)
        user.profile_image = f"profiles/{filename}"
        db.session.commit()

    return jsonify({
        'image_url': f"/static/profiles/{filename}",
        'message': 'Profile image uploaded successfully'
    }), 200

# ========== MULTIPLE IMAGES UPLOAD (post) ==========
@upload_bp.route('/upload-post-images', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def upload_post_images():
    # Handle preflight
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://rootnetwork1.netlify.app')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    ensure_upload_folders()

    if 'images' not in request.files:
        return jsonify({'error': 'No images provided'}), 400

    files = request.files.getlist('images')
    if not files or len(files) == 0:
        return jsonify({'error': 'No images selected'}), 400

    if len(files) > 10:
        return jsonify({'error': 'Maximum 10 images allowed'}), 400

    uploaded = []
    saved_paths = []

    for file in files:
        if file.filename == '':
            continue

        if not allowed_file(file.filename):
            # Clean up already saved files
            for path in saved_paths:
                if os.path.exists(path):
                    os.remove(path)
            return jsonify({'error': f'File type not allowed: {file.filename}'}), 400

        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = secure_filename(f"post_{datetime.now().timestamp()}_{os.urandom(4).hex()}.{ext}")
        filepath = os.path.join(UPLOAD_FOLDERS['posts'], filename)
        file.save(filepath)
        saved_paths.append(filepath)

        # Validate and sanitize
        valid, msg, w, h = validate_and_sanitize_image(filepath)
        if not valid:
            for path in saved_paths:
                if os.path.exists(path):
                    os.remove(path)
            return jsonify({'error': msg}), 400

        url = f"/static/posts/{filename}"
        uploaded.append({
            'url': url,
            'caption': '',
            'alt': '',
        })

    return jsonify({
        'images': uploaded,
        'message': f'{len(uploaded)} images uploaded successfully'
    }), 200
