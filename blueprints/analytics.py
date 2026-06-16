# blueprints/analytics.py
from flask import jsonify, request
from models import PageView, UserAction, Post
from exts import db, csrf
from funcs import super_admin_required
from services.geo_service import get_country_code
from . import analytics_bp
from datetime import datetime, timedelta

@analytics_bp.route('/analytics', methods=['GET', 'OPTIONS'])
@csrf.exempt
@super_admin_required
def get_analytics():
    if request.method == 'OPTIONS':
        return '', 200
    
    days = request.args.get('days', 7, type=int)
    start_date = datetime.now() - timedelta(days=days)
    
    try:
        total_views = PageView.query.filter(PageView.timestamp >= start_date).count()
        unique_visitors = db.session.query(PageView.session_id).filter(PageView.timestamp >= start_date).distinct().count()
        
        popular_posts = db.session.query(
            Post.id, Post.title, Post.slug, db.func.count(PageView.id).label('view_count')
        ).join(PageView, PageView.post_id == Post.id)\
         .filter(PageView.timestamp >= start_date)\
         .group_by(Post.id)\
         .order_by(db.desc('view_count'))\
         .limit(10).all()
        
        action_counts = db.session.query(
            UserAction.action_type, db.func.count(UserAction.id).label('count')
        ).filter(UserAction.timestamp >= start_date)\
         .group_by(UserAction.action_type).all()
        
        daily_views = db.session.query(
            db.func.date(PageView.timestamp).label('date'),
            db.func.count(PageView.id).label('count')
        ).filter(PageView.timestamp >= start_date)\
         .group_by(db.func.date(PageView.timestamp)).all()
        
        return jsonify({
            'total_views': total_views,
            'unique_visitors': unique_visitors,
            'popular_posts': [{
                'id': p.id,
                'title': p.title,
                'slug': p.slug,
                'views': p.view_count
            } for p in popular_posts],
            'action_counts': [{'action': a.action_type, 'count': a.count} for a in action_counts],
            'daily_views': [{'date': str(d.date), 'count': d.count} for d in daily_views]
        }), 200
    except Exception as e:
        print(f"Error in get_analytics: {e}")
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/analytics/locations', methods=['GET', 'OPTIONS'])
@csrf.exempt
@super_admin_required
def get_location_analytics():
    if request.method == 'OPTIONS':
        return '', 200
    
    days = request.args.get('days', 30, type=int)
    start_date = datetime.now() - timedelta(days=days)
    
    try:
        # FIXED: Added city to the query
        locations = db.session.query(
            PageView.country,
            PageView.city,  # ADD THIS LINE
            db.func.count(PageView.session_id.distinct()).label('visitor_count')
        ).filter(
            PageView.timestamp >= start_date
        ).filter(
            PageView.country.isnot(None)
        ).filter(
            PageView.country != ''
        ).filter(
            PageView.country != 'Unknown'
        ).filter(
            PageView.country != 'Local'
        ).group_by(
            PageView.country,
            PageView.city  # ADD THIS LINE - group by city too
        ).order_by(
            db.desc('visitor_count')
        ).limit(20).all()
        
        views_by_country = db.session.query(
            PageView.country,
            db.func.count(PageView.id).label('view_count')
        ).filter(
            PageView.timestamp >= start_date
        ).filter(
            PageView.country.isnot(None)
        ).filter(
            PageView.country != ''
        ).filter(
            PageView.country != 'Unknown'
        ).filter(
            PageView.country != 'Local'
        ).group_by(
            PageView.country
        ).order_by(
            db.desc('view_count')
        ).all()
        
        # Get total views for percentage calculation
        total_views = db.session.query(
            db.func.count(PageView.id)
        ).filter(
            PageView.timestamp >= start_date
        ).filter(
            PageView.country.isnot(None)
        ).filter(
            PageView.country != ''
        ).filter(
            PageView.country != 'Unknown'
        ).filter(
            PageView.country != 'Local'
        ).scalar() or 1
        
        return jsonify({
            'visitor_locations': [{
                'country': loc.country,
                'city': loc.city or 'Unknown',  # ADD THIS - return city
                'country_code': get_country_code(loc.country),
                'visitor_count': loc.visitor_count
            } for loc in locations],
            'views_by_country': [{
                'country': v.country,
                'views': v.view_count,
                'percentage': round((v.view_count / total_views) * 100, 1)
            } for v in views_by_country],
            'total_views': total_views
        }), 200
    except Exception as e:
        print(f"Error in get_location_analytics: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500