from flask import jsonify, request, session
from models import ActivityLog, SuspiciousActivity, FailedLoginAttempt
from exts import db, csrf
from funcs import super_admin_required
from . import security_bp
from datetime import datetime, timedelta

@security_bp.route('/activity-logs', methods=['GET', 'OPTIONS'])
@csrf.exempt
@super_admin_required
def get_activity_logs():
    if request.method == 'OPTIONS':
        return '', 200
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    action_type = request.args.get('action', None)
    
    try:
        query = ActivityLog.query.order_by(ActivityLog.timestamp.desc())
        
        if action_type and action_type != 'all':
            query = query.filter_by(action=action_type)
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'logs': [{
                'id': log.id,
                'username': log.username,
                'action': log.action,
                'action_details': log.action_details,
                'ip_address': log.ip_address,
                'endpoint': log.endpoint,
                'method': log.method,
                'status': log.status,
                'timestamp': log.timestamp.isoformat()
            } for log in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/suspicious-activities', methods=['GET', 'OPTIONS'])
@csrf.exempt
@super_admin_required
def get_suspicious_activities():
    if request.method == 'OPTIONS':
        return '', 200
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    resolved = request.args.get('resolved', None)
    
    try:
        query = SuspiciousActivity.query.order_by(SuspiciousActivity.detected_at.desc())
        
        if resolved is not None:
            query = query.filter_by(resolved=resolved == 'true')
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'activities': [{
                'id': a.id,
                'severity': a.severity,
                'category': a.category,
                'description': a.description,
                'ip_address': a.ip_address,
                'endpoint': a.endpoint,
                'detected_at': a.detected_at.isoformat(),
                'resolved': a.resolved
            } for a in pagination.items],
            'total': pagination.total,
            'page': page,
            'pages': pagination.pages
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/security-stats', methods=['GET', 'OPTIONS'])
@csrf.exempt
@super_admin_required
def get_security_stats():
    if request.method == 'OPTIONS':
        return '', 200
    
    days = request.args.get('days', 7, type=int)
    start_date = datetime.now() - timedelta(days=days)
    
    try:
        failed_logins = FailedLoginAttempt.query.filter(
            FailedLoginAttempt.timestamp >= start_date
        ).count()
        
        suspicious_by_severity = db.session.query(
            SuspiciousActivity.severity,
            db.func.count(SuspiciousActivity.id).label('count')
        ).filter(SuspiciousActivity.detected_at >= start_date)\
         .group_by(SuspiciousActivity.severity).all()
        
        return jsonify({
            'failed_logins': failed_logins,
            'suspicious_by_severity': [{'severity': s.severity, 'count': s.count} for s in suspicious_by_severity],
            'period_days': days
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@security_bp.route('/suspicious-activities/<int:activity_id>/resolve', methods=['POST', 'OPTIONS'])
@csrf.exempt
@super_admin_required
def resolve_suspicious_activity(activity_id):
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        activity = SuspiciousActivity.query.get_or_404(activity_id)
        activity.resolved = True
        activity.resolved_at = datetime.now()
        activity.resolved_by = session.get('user_id')
        activity.notes = request.json.get('notes', 'Resolved by admin')
        db.session.commit()
        
        return jsonify({'message': 'Activity resolved successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500