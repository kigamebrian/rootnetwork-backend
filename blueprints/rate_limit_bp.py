from flask import Blueprint, jsonify, request, session
from exts import db, csrf
from funcs import super_admin_required
from models  import RateLimitRule, RateLimitLog
from models import BlockedIP  # Import from main models.py
from services.rate_limit_service import rate_limit_service
from datetime import datetime

# Create the blueprint
rate_limit_bp = Blueprint('rate_limit', __name__, url_prefix='/api')

@rate_limit_bp.route('/rate-limits/rules', methods=['GET'])
@csrf.exempt
@super_admin_required
def get_rules():
    """Get all rate limit rules"""
    rules = RateLimitRule.query.order_by(RateLimitRule.priority.desc()).all()
    return jsonify([rule.to_dict() for rule in rules]), 200

@rate_limit_bp.route('/rate-limits/rules', methods=['POST'])
@csrf.exempt
@super_admin_required
def create_rule():
    """Create a new rate limit rule"""
    data = request.json
    
    required_fields = ['name', 'endpoint_pattern', 'limit_count', 'time_window']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    rule = RateLimitRule(
        name=data['name'],
        endpoint_pattern=data['endpoint_pattern'],
        method=data.get('method', 'ALL'),
        limit_count=data['limit_count'],
        time_window=data['time_window'],
        is_active=data.get('is_active', True),
        priority=data.get('priority', 0)
    )
    
    db.session.add(rule)
    db.session.commit()
    
    return jsonify(rule.to_dict()), 201

@rate_limit_bp.route('/rate-limits/rules/<int:rule_id>', methods=['PUT'])
@csrf.exempt
@super_admin_required
def update_rule(rule_id):
    """Update an existing rate limit rule"""
    rule = RateLimitRule.query.get_or_404(rule_id)
    data = request.json
    
    if 'name' in data:
        rule.name = data['name']
    if 'endpoint_pattern' in data:
        rule.endpoint_pattern = data['endpoint_pattern']
    if 'method' in data:
        rule.method = data['method']
    if 'limit_count' in data:
        rule.limit_count = data['limit_count']
    if 'time_window' in data:
        rule.time_window = data['time_window']
    if 'is_active' in data:
        rule.is_active = data['is_active']
    if 'priority' in data:
        rule.priority = data['priority']
    
    rule.updated_at = datetime.now()
    db.session.commit()
    
    return jsonify(rule.to_dict()), 200

@rate_limit_bp.route('/rate-limits/rules/<int:rule_id>', methods=['DELETE'])
@csrf.exempt
@super_admin_required
def delete_rule(rule_id):
    """Delete a rate limit rule"""
    rule = RateLimitRule.query.get_or_404(rule_id)
    db.session.delete(rule)
    db.session.commit()
    
    return jsonify({'message': 'Rule deleted successfully'}), 200

@rate_limit_bp.route('/rate-limits/blocked-ips', methods=['GET'])
@csrf.exempt
@super_admin_required
def get_blocked_ips():
    """Get all blocked IPs"""
    blocked_ips = BlockedIP.query.order_by(BlockedIP.blocked_at.desc()).all()
    return jsonify([ip.to_dict() for ip in blocked_ips]), 200

@rate_limit_bp.route('/rate-limits/blocked-ips', methods=['POST'])
@csrf.exempt
@super_admin_required
def block_ip():
    """Block an IP address"""
    data = request.json
    
    if 'ip_address' not in data:
        return jsonify({'error': 'IP address required'}), 400
    
    rate_limit_service.block_ip(
        ip_address=data['ip_address'],
        reason=data.get('reason', 'Manually blocked by admin'),
        blocked_by=session.get('username', 'Admin'),
        minutes=data.get('minutes')  # None = permanent
    )
    
    return jsonify({'message': f"IP {data['ip_address']} blocked successfully"}), 200

@rate_limit_bp.route('/rate-limits/blocked-ips/<string:ip_address>', methods=['DELETE'])
@csrf.exempt
@super_admin_required
def unblock_ip(ip_address):
    """Unblock an IP address"""
    if rate_limit_service.unblock_ip(ip_address):
        return jsonify({'message': f"IP {ip_address} unblocked successfully"}), 200
    return jsonify({'error': 'IP not found'}), 404

@rate_limit_bp.route('/rate-limits/status', methods=['GET'])
@csrf.exempt
@super_admin_required
def get_rate_limit_status():
    """Get current rate limit status for dashboard"""
    ip_address = request.args.get('ip')
    status = rate_limit_service.get_rate_limit_status(ip_address)
    return jsonify(status), 200

@rate_limit_bp.route('/rate-limits/logs', methods=['GET'])
@csrf.exempt
@super_admin_required
def get_rate_limit_logs():
    """Get rate limit logs with filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    ip_filter = request.args.get('ip')
    
    query = RateLimitLog.query.order_by(RateLimitLog.timestamp.desc())
    
    if ip_filter:
        query = query.filter_by(ip_address=ip_filter)
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'logs': [log.to_dict() for log in pagination.items],
        'total': pagination.total,
        'page': page,
        'pages': pagination.pages
    }), 200