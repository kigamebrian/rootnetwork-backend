# blueprints/sitemap.py
from flask import Blueprint, Response, request, current_app
from models import Post, Category, generate_slug   # ✅ generate_slug imported
from datetime import datetime
import time
import logging

logger = logging.getLogger(__name__)

sitemap_bp = Blueprint('sitemap', __name__)

# In‑memory cache fallback
_memory_cache = {
    'content': None,
    'timestamp': 0
}
CACHE_TTL = 3600  # 1 hour

def _get_redis_client():
    try:
        from services.redis_client import redis_client
        return redis_client
    except ImportError:
        return None

def _generate_sitemap_xml(base_url):
    """Generate the sitemap XML content."""
    posts = Post.query.filter_by(status='published').order_by(Post.timestamp.desc()).all()
    
    # Static pages
    static_pages = [
        {'loc': '/', 'lastmod': datetime.now().date().isoformat()},
        {'loc': '/about', 'lastmod': datetime.now().date().isoformat()},
        {'loc': '/blog', 'lastmod': datetime.now().date().isoformat()},
    ]
    
    # Add category pages – generate slug from name using generate_slug
    categories = Category.query.all()
    for cat in categories:
        slug = generate_slug(cat.name)
        static_pages.append({
            'loc': f'/category/{slug}',
            'lastmod': datetime.now().date().isoformat()
        })
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'
    xml += ' xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
    
    # Static pages
    for page in static_pages:
        xml += '  <url>\n'
        xml += f'    <loc>{base_url}{page["loc"]}</loc>\n'
        xml += f'    <lastmod>{page["lastmod"]}</lastmod>\n'
        xml += '    <changefreq>monthly</changefreq>\n'
        xml += '    <priority>0.8</priority>\n'
        xml += '  </url>\n'
    
    # Published posts
    for post in posts:
        lastmod = post.published_at or post.timestamp
        lastmod_str = lastmod.strftime('%Y-%m-%d') if lastmod else datetime.now().date().isoformat()
        
        xml += '  <url>\n'
        xml += f'    <loc>{base_url}/blog/post/{post.slug}</loc>\n'
        xml += f'    <lastmod>{lastmod_str}</lastmod>\n'
        xml += '    <changefreq>weekly</changefreq>\n'
        xml += '    <priority>0.9</priority>\n'
        
        if post.image:
            if post.image.startswith('http'):
                image_url = post.image
            else:
                image_url = f"{base_url}{post.image}" if post.image.startswith('/') else f"{base_url}/{post.image}"
            xml += f'    <image:image>\n'
            xml += f'      <image:loc>{image_url}</image:loc>\n'
            xml += f'      <image:title>{post.title}</image:title>\n'
            xml += f'    </image:image>\n'
        
        xml += '  </url>\n'
    
    xml += '</urlset>'
    return xml

@sitemap_bp.route('/sitemap.xml')
def sitemap():
    base_url = request.host_url.rstrip('/')
    
    redis_client = _get_redis_client()
    cache_key = 'sitemap:xml'
    
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                return Response(cached, mimetype='application/xml')
        except Exception as e:
            logger.warning(f"Redis read error: {e}")
    
    now = time.time()
    if _memory_cache['content'] and (now - _memory_cache['timestamp']) < CACHE_TTL:
        return Response(_memory_cache['content'], mimetype='application/xml')
    
    xml_content = _generate_sitemap_xml(base_url)
    
    if redis_client:
        try:
            redis_client.setex(cache_key, CACHE_TTL, xml_content)
        except Exception as e:
            logger.warning(f"Redis write error: {e}")
    
    _memory_cache['content'] = xml_content
    _memory_cache['timestamp'] = now
    
    # ✅ Removed the stray 'and'
    return Response(xml_content, mimetype='application/xml')
