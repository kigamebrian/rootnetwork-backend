# backend/blueprints/tts_bp.py
from flask import Blueprint, jsonify, request, send_file, make_response
from gtts import gTTS
from exts import db, csrf
import os
import uuid
import re
import hashlib
from datetime import datetime, timedelta
import time

tts_bp = Blueprint('tts', __name__, url_prefix='/api/tts')

# Cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'audio_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# ========== HELPER FOR CORS ==========
def get_allowed_origin():
    origin = request.headers.get('Origin', '')
    allowed_origins = [
        'https://rootnetwork1.netlify.app',
        'http://localhost:3000',
        'http://127.0.0.1:3000'
    ]
    if origin in allowed_origins:
        return origin
    return 'https://rootnetwork1.netlify.app'

def get_cache_key(text, title):
    """Generate a unique cache key based on content"""
    content_hash = hashlib.md5(text[:300].encode()).hexdigest()
    title_hash = hashlib.md5(title.encode()).hexdigest()
    return f"{title_hash}_{content_hash}.mp3"

def clean_text(text):
    """Clean HTML and extract meaningful text for TTS - FASTER"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s\.\,\!\?\-\'\"]', ' ', text)
    return text.strip()[:2000]

@tts_bp.route('/speak', methods=['POST', 'OPTIONS'])
@csrf.exempt
def text_to_speech():
    # Handle preflight OPTIONS
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', get_allowed_origin())
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        return response, 200

    start_time = time.time()
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        text = data.get('text', '')
        title = data.get('title', 'Article')
        
        print(f"🎤 TTS Request: {title[:50]}...")
        print(f"📝 Text length: {len(text)} chars")
        
        if not text or len(text) < 50:
            return jsonify({'error': f'Text too short ({len(text)} chars)'}), 400
        
        cleaned_text = clean_text(text)
        
        if len(cleaned_text) < 30:
            return jsonify({'error': 'No readable text found'}), 400
        
        print(f"📝 Cleaned text length: {len(cleaned_text)} chars")
        
        # Cache check
        cache_key = get_cache_key(cleaned_text, title)
        cache_path = os.path.join(CACHE_DIR, cache_key)
        
        if os.path.exists(cache_path):
            file_size = os.path.getsize(cache_path)
            print(f"✅ Cache HIT! Time: {time.time() - start_time:.2f}s")
            return send_file(
                cache_path,
                mimetype='audio/mpeg',
                as_attachment=False
            )
        
        print(f"🎤 Generating NEW audio...")
        tts = gTTS(text=cleaned_text, lang='en', slow=False)
        tts.save(cache_path)
        
        file_size = os.path.getsize(cache_path)
        elapsed = time.time() - start_time
        print(f"✅ Audio generated in {elapsed:.2f}s! Size: {file_size} bytes")
        
        return send_file(
            cache_path,
            mimetype='audio/mpeg',
            as_attachment=False
        )
        
    except Exception as e:
        print(f"❌ TTS Error after {time.time() - start_time:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
