from flask import jsonify, request, session
from exts import db, csrf
from models import User
from funcs import login_required, allowed_file, validate_and_sanitize_image, limiter
from middleware.security_middleware import security_middleware  
from . import upload_bp
from datetime import datetime
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDERS = {
    'posts': os.path.join('static', 'posts'),
    'profiles': os.path.join('static', 'profiles')
}

@upload_bp.route('/upload-post-image', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def upload_post_image():
    if request.method == 'OPTIONS':
        return '', 200
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    extension = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"post_{datetime.now().timestamp()}.{extension}")
    filepath = os.path.join(UPLOAD_FOLDERS['posts'], filename)
    file.save(filepath)
    
    is_valid, message, width, height = validate_and_sanitize_image(filepath)
    
    if not is_valid:
        os.remove(filepath)
        return jsonify({'error': message}), 400
    
    return jsonify({'image_url': f"/static/posts/{filename}", 'message': 'Image uploaded successfully'}), 200

@upload_bp.route('/upload-profile-image', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def upload_profile_image():
    from flask import session
    if request.method == 'OPTIONS':
        return '', 200
    
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    extension = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"user_{session['user_id']}_{datetime.now().timestamp()}.{extension}")
    filepath = os.path.join(UPLOAD_FOLDERS['profiles'], filename)
    file.save(filepath)
    
    is_valid, message, width, height = validate_and_sanitize_image(filepath)
    
    if not is_valid:
        os.remove(filepath)
        return jsonify({'error': message}), 400
    
    user = User.query.get(session['user_id'])
    if user:
        if user.profile_image and user.profile_image != 'default-avatar.png':
            old_path = os.path.join(UPLOAD_FOLDERS['profiles'], os.path.basename(user.profile_image))
            if os.path.exists(old_path):
                os.remove(old_path)
        user.profile_image = f"profiles/{filename}"
        db.session.commit()
    
    return jsonify({'image_url': f"/static/profiles/{filename}", 'message': 'Profile image uploaded successfully'}), 200