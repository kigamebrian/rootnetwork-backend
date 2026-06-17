# blueprints/upload.py – FINAL (Cloudinary)
from flask import jsonify, request, session, make_response
from exts import db, csrf
from models import User
from funcs import login_required, allowed_file
from middleware.security_middleware import security_middleware  
from . import upload_bp
import cloudinary.uploader
import cloudinary

# ---------- POST IMAGE ----------
@upload_bp.route('/upload-post-image', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def upload_post_image():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', 'https://rootnetwork1.netlify.app')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    try:
        result = cloudinary.uploader.upload(
            file,
            folder="blog_posts",
            transformation={"quality": "auto", "fetch_format": "auto"}
        )
        return jsonify({
            'image_url': result['secure_url'],
            'public_id': result['public_id'],
            'message': 'Image uploaded successfully'
        }), 200
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return jsonify({'error': 'Upload failed'}), 500

# ---------- PROFILE IMAGE ----------
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

    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    try:
        result = cloudinary.uploader.upload(
            file,
            folder="profile_pictures",
            transformation={"quality": "auto", "fetch_format": "auto", "width": 300, "height": 300, "crop": "fill"}
        )
        user = User.query.get(session['user_id'])
        if user:
            # Remove old Cloudinary image if exists
            if user.profile_image and 'cloudinary' in user.profile_image:
                public_id = user.profile_image.split('/')[-1].split('.')[0]
                cloudinary.uploader.destroy(public_id)
            user.profile_image = result['secure_url']
            db.session.commit()

        return jsonify({
            'image_url': result['secure_url'],
            'public_id': result['public_id'],
            'message': 'Profile image uploaded successfully'
        }), 200
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return jsonify({'error': 'Upload failed'}), 500
