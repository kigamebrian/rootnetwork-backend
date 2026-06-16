from flask import jsonify, request, session
from exts import csrf
from funcs import login_required, limiter
from middleware.security_middleware import security_middleware 
from . import ai_bp


@ai_bp.route('/write', methods=['POST', 'OPTIONS'])
@csrf.exempt
@login_required
@security_middleware
def ai_write():
    if request.method == 'OPTIONS':
        return '', 200
    
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        category_id = data.get('category_id')
        title = data.get('title', '')
        
        from services.ai_service import ai_write as ai_write_service
        
        generated_content = ai_write_service(category_id, title)
        
        return jsonify({'content': generated_content}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@ai_bp.route('/comment', methods=['POST', 'OPTIONS'])
@csrf.exempt
@security_middleware
def ai_comment():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        from services.ai_service import ai_comment as ai_comment_service
        
        comment_data = ai_comment_service()
        
        return jsonify({
            'author': comment_data[0],
            'email': comment_data[1],
            'site': comment_data[2],
            'content': comment_data[3]
        }), 200
    except Exception as e:
        return jsonify({
            'author': 'AI Writer',
            'email': 'ai@example.com',
            'site': 'https://example.com',
            'content': 'Great article! Thanks for sharing this informative content.'
        }), 200