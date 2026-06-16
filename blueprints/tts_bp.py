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

def get_cache_key(text, title):
    """Generate a unique cache key based on content"""
    # Use first 300 chars + title to generate hash (reduced from 500)
    content_hash = hashlib.md5(text[:300].encode()).hexdigest()
    title_hash = hashlib.md5(title.encode()).hexdigest()
    return f"{title_hash}_{content_hash}.mp3"

def clean_text(text):
    """Clean HTML and extract meaningful text for TTS - FASTER"""
    if not text:
        return ""
    
    # Simplified cleaning for speed
    text = re.sub(r'<[^>]+>', ' ', text)  # Remove HTML
    text = re.sub(r'\s+', ' ', text)       # Normalize whitespace
    text = re.sub(r'[^\w\s\.\,\!\?\-\'\"]', ' ', text)  # Keep basic punctuation
    
    return text.strip()[:2000]  # Reduced from 3000 to 2000 chars for faster generation

@tts_bp.route('/speak', methods=['POST', 'OPTIONS'])
@csrf.exempt
def text_to_speech():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "http://localhost:3000")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
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
        
        # Clean the text (reduced length for speed)
        cleaned_text = clean_text(text)
        
        if len(cleaned_text) < 30:
            return jsonify({'error': 'No readable text found'}), 400
        
        print(f"📝 Cleaned text length: {len(cleaned_text)} chars")
        
        # Generate cache key
        cache_key = get_cache_key(cleaned_text, title)
        cache_path = os.path.join(CACHE_DIR, cache_key)
        
        # Check if audio already exists in cache
        if os.path.exists(cache_path):
            file_size = os.path.getsize(cache_path)
            print(f"✅ Cache HIT! Time: {time.time() - start_time:.2f}s")
            
            return send_file(
                cache_path,
                mimetype='audio/mpeg',
                as_attachment=False
            )
        
        # Generate new audio (cache miss)
        print(f"🎤 Generating NEW audio...")
        
        # Generate speech with timeout handling
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