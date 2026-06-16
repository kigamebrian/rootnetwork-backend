# services/ids_service.py
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from models import db, FailedLoginAttempt, SuspiciousActivity
from services.waf_constants import BRUTE_FORCE_THRESHOLD, BRUTE_FORCE_WINDOW

logger = logging.getLogger(__name__)

class IntrusionDetectionSystem:
    """Intrusion Detection System with improved pattern matching"""
    
    # Compile regex patterns once for performance
    SQL_INJECTION_PATTERNS = [
        re.compile(r"'\s*(or|and)\s+.*?\s*=", re.IGNORECASE),
        re.compile(r"'\s*(or|and)\s+'[^']*'\s*=\s*'[^']*", re.IGNORECASE),
        re.compile(r"'\s*(or|and)\s+\d+\s*=\s*\d+", re.IGNORECASE),
        re.compile(r"\b(or|and)\b\s+\d+\s*=\s*\d+", re.IGNORECASE),
        re.compile(r"admin'\s*#", re.IGNORECASE),
        re.compile(r"admin'\s*--", re.IGNORECASE),
        re.compile(r"'.*\s*(or|and)\s+'.*", re.IGNORECASE),
        re.compile(r"\b(select|insert|update|delete|drop|union|alter|create)\b.*\b(from|into|set|where)\b", re.IGNORECASE),
        re.compile(r"union.*?\bselect\b", re.IGNORECASE),
        re.compile(r";\s*(drop|delete|select|insert)", re.IGNORECASE),
        re.compile(r"(\%27)|(\')|(\-\-)|(\%23)|(#)", re.IGNORECASE),
        re.compile(r"(\%3D)|(=)|(\%20)", re.IGNORECASE),
        re.compile(r"\b(sleep|waitfor|benchmark)\b.*\(", re.IGNORECASE),
        re.compile(r"\b(case|if)\b.*\b(select|sleep)\b", re.IGNORECASE),
    ]
    
    XSS_PATTERNS = [
        re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL),
        re.compile(r"javascript\s*:", re.IGNORECASE),
        re.compile(r"on\w+\s*=\s*['\"][^'\"]*['\"]", re.IGNORECASE),
        re.compile(r"<iframe\b[^>]*>.*?</iframe>", re.IGNORECASE | re.DOTALL),
        re.compile(r"<object\b[^>]*>.*?</object>", re.IGNORECASE | re.DOTALL),
        re.compile(r"<embed\b[^>]*>", re.IGNORECASE),
        re.compile(r"<img\b[^>]*\bonerror\s*=", re.IGNORECASE),
        re.compile(r"<svg\b[^>]*\bonload\s*=", re.IGNORECASE),
        re.compile(r"alert\s*\(.*?\)", re.IGNORECASE),
        re.compile(r"prompt\s*\(.*?\)", re.IGNORECASE),
        re.compile(r"confirm\s*\(.*?\)", re.IGNORECASE),
        re.compile(r"document\.\w+", re.IGNORECASE),
        re.compile(r"eval\s*\(.*?\)", re.IGNORECASE),
        re.compile(r"expression\s*\(.*?\)", re.IGNORECASE),
    ]
    
    # Whitelist to reduce false positives
    SAFE_WORDS = {
        'color', 'orange', 'andromeda', 'oracle', 'order', 
        'normal', 'standard', 'orchestra', 'original', 'orient'
    }
    
    @classmethod
    def detect_sql_injection(cls, data: Any, max_length: int = 1000) -> Tuple[bool, Optional[str]]:
        """Detect SQL injection with improved pattern matching"""
        if not data:
            return False, None
        
        # Convert to string and limit length to prevent ReDoS
        data_str = str(data).lower()[:max_length]
        
        # Quick check for common false positives
        words = set(re.findall(r'\b\w+\b', data_str))
        if words & cls.SAFE_WORDS:
            safe_ratio = len(words & cls.SAFE_WORDS) / len(words) if words else 0
            if safe_ratio > 0.5:
                return False, None
        
        # Check against all patterns
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if pattern.search(data_str):
                # Additional validation to reduce false positives
                if cls._validate_sql_threat(data_str):
                    return True, pattern.pattern
        
        return False, None
    
    @classmethod
    def _validate_sql_threat(cls, data_str: str) -> bool:
        """Additional validation to confirm SQL threat"""
        # Count SQL keywords
        sql_keywords = ['select', 'insert', 'update', 'delete', 'drop', 'union', 'or', 'and', 'where', 'from']
        keyword_count = sum(1 for keyword in sql_keywords if keyword in data_str)
        
        # Check for operators and quotes
        operators = ['=', '>', '<', ';', "'", '"', '--', '#', '/*', '*/']
        operator_count = sum(1 for op in operators if op in data_str)
        
        # Flag as threat if we have both keywords and operators
        if keyword_count >= 2 and operator_count >= 2:
            return True
        
        # For short strings with obvious patterns
        if len(data_str) < 50:
            if "'" in data_str and ('or' in data_str or 'and' in data_str):
                return True
            if 'admin' in data_str and ('#' in data_str or '--' in data_str):
                return True
        
        return False
    
    @classmethod
    def detect_xss(cls, data: Any, max_length: int = 1000) -> Tuple[bool, Optional[str]]:
        """Detect XSS with improved pattern matching"""
        if not data:
            return False, None
        
        data_str = str(data).lower()[:max_length]
        
        # Check against all XSS patterns
        for pattern in cls.XSS_PATTERNS:
            if pattern.search(data_str):
                # Additional validation for XSS
                xss_indicators = [
                    '<script', '</script>', 'javascript:', 'onerror=', 'onload=',
                    'alert(', 'prompt(', 'confirm(', 'document.', 'eval('
                ]
                indicator_count = sum(1 for ind in xss_indicators if ind in data_str)
                if indicator_count >= 1:
                    return True, pattern.pattern
        
        return False, None
    
    @classmethod
    def log_failed_attempt(cls, username: str, ip_address: str, user_agent: Optional[str] = None) -> None:
        """Log failed login attempts and detect brute force"""
        try:
            attempt = FailedLoginAttempt(
                username_attempted=username,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.session.add(attempt)
            db.session.commit()
            
            # Check for brute force
            time_window = datetime.now() - timedelta(minutes=15)
            attempts = FailedLoginAttempt.query.filter(
                FailedLoginAttempt.ip_address == ip_address,
                FailedLoginAttempt.timestamp >= time_window
            ).count()
            
            if attempts >= BRUTE_FORCE_THRESHOLD:
                # Create suspicious activity
                cls.create_suspicious_activity(
                    severity='high',
                    category='brute_force',
                    description=f'Potential brute force attack from IP {ip_address} ({attempts} attempts in 15 minutes)',
                    ip_address=ip_address
                )
                
                # Send alert
                try:
                    from services.tasks import send_bruteforce_alert
                    send_bruteforce_alert(ip_address, attempts, username)
                except Exception as e:
                    logger.error(f"Failed to send brute force alert: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to log failed attempt: {e}")
            db.session.rollback()
    
    @classmethod
    def create_suspicious_activity(
        cls,
        severity: str,
        category: str,
        description: str,
        ip_address: str,
        user_id: Optional[int] = None,
        endpoint: Optional[str] = None,
        request_data: Optional[Dict] = None
    ) -> Optional[SuspiciousActivity]:
        """Create a suspicious activity record"""
        try:
            activity = SuspiciousActivity(
                severity=severity,
                category=category,
                description=description,
                ip_address=ip_address,
                user_id=user_id,
                endpoint=endpoint,
                request_data=str(request_data)[:1000] if request_data else None
            )
            db.session.add(activity)
            db.session.commit()
            
            logger.warning(f"⚠️ [SECURITY] Created suspicious activity: {category} - {severity} from {ip_address}")
            return activity
            
        except Exception as e:
            logger.error(f"Failed to create suspicious activity: {e}")
            db.session.rollback()
            return None
    
    @classmethod
    def scan_request(
        cls,
        request_data: Optional[Dict[str, Any]],
        ip_address: str,
        endpoint: str
    ) -> List[Dict[str, Any]]:
        """Smart request scanning that understands different endpoint types"""
        threats = []
        
        try:
            logger.debug(f"🔍 [IDS] Scanning {endpoint} from {ip_address}")
            
            # Different scanning strategies based on endpoint
            if endpoint.startswith('/api/admin/'):
                threats.extend(cls._scan_admin_endpoint(request_data, ip_address, endpoint))
            
            elif endpoint in ['/api/login', '/api/register']:
                threats.extend(cls._scan_auth_endpoint(request_data, ip_address, endpoint))
            
            else:
                threats.extend(cls._scan_general_endpoint(request_data, ip_address, endpoint))
            
            return threats
            
        except Exception as e:
            logger.error(f"IDS scan error for {endpoint}: {e}")
            return []
    
    @classmethod
    def _scan_admin_endpoint(cls, request_data: Optional[Dict], ip: str, endpoint: str) -> List[Dict]:
        """Scan admin endpoints"""
        threats = []
        
        if not request_data:
            return threats
        
        # Check sensitive fields
        sensitive_fields = ['title', 'content', 'name', 'email', 'username', 'full_name', 'description']
        
        for field in sensitive_fields:
            if field in request_data and request_data[field]:
                value = request_data[field]
                
                # Check SQL injection
                has_sql, pattern = cls.detect_sql_injection(value)
                if has_sql:
                    threat = {
                        'type': 'sql_injection',
                        'pattern': pattern,
                        'severity': 'critical',
                        'field': field,
                        'endpoint': endpoint
                    }
                    threats.append(threat)
                    
                    cls.create_suspicious_activity(
                        severity='critical',
                        category='sql_injection',
                        description=f'SQL injection in {field} - Pattern: {pattern}',
                        ip_address=ip,
                        endpoint=endpoint,
                        request_data={field: value}
                    )
                    
                    try:
                        from services.tasks import send_intrusion_alert
                        send_intrusion_alert(threat, ip, endpoint)
                    except Exception as e:
                        logger.error(f"Failed to send alert: {e}")
                
                # Check XSS
                has_xss, xss_pattern = cls.detect_xss(value)
                if has_xss:
                    threat = {
                        'type': 'xss',
                        'pattern': xss_pattern,
                        'severity': 'high',
                        'field': field,
                        'endpoint': endpoint
                    }
                    threats.append(threat)
                    
                    cls.create_suspicious_activity(
                        severity='high',
                        category='xss',
                        description=f'XSS in {field} - Pattern: {xss_pattern}',
                        ip_address=ip,
                        endpoint=endpoint,
                        request_data={field: value}
                    )
                    
                    try:
                        from services.tasks import send_intrusion_alert
                        send_intrusion_alert(threat, ip, endpoint)
                    except Exception as e:
                        logger.error(f"Failed to send alert: {e}")
        
        return threats
    
    @classmethod
    def _scan_auth_endpoint(cls, request_data: Optional[Dict], ip: str, endpoint: str) -> List[Dict]:
        """Scan authentication endpoints"""
        threats = []
        
        if not request_data:
            return threats
        
        # Check login fields
        login_fields = ['identifier', 'email', 'username', 'password']
        
        for field in login_fields:
            if field in request_data and request_data[field]:
                value = request_data[field]
                
                # Only check SQL injection in username/email fields
                if field != 'password':
                    has_sql, pattern = cls.detect_sql_injection(value)
                    if has_sql:
                        threat = {
                            'type': 'sql_injection',
                            'pattern': pattern,
                            'severity': 'critical',
                            'field': field,
                            'endpoint': endpoint
                        }
                        threats.append(threat)
                        
                        cls.create_suspicious_activity(
                            severity='critical',
                            category='sql_injection',
                            description=f'SQL injection in {field} - Pattern: {pattern}',
                            ip_address=ip,
                            endpoint=endpoint,
                            request_data={field: value}
                        )
                        
                        try:
                            from services.tasks import send_intrusion_alert
                            send_intrusion_alert(threat, ip, endpoint)
                        except Exception as e:
                            logger.error(f"Failed to send alert: {e}")
        
        return threats
    
    @classmethod
    def _scan_general_endpoint(cls, request_data: Optional[Dict], ip: str, endpoint: str) -> List[Dict]:
        """Scan general endpoints"""
        threats = []
        
        if not request_data:
            return threats
        
        # Convert to string for scanning
        data_str = str(request_data)
        
        # Check SQL injection
        has_sql, pattern = cls.detect_sql_injection(data_str)
        if has_sql:
            threat = {
                'type': 'sql_injection',
                'pattern': pattern,
                'severity': 'critical',
                'endpoint': endpoint
            }
            threats.append(threat)
            
            cls.create_suspicious_activity(
                severity='critical',
                category='sql_injection',
                description=f'SQL injection attempt at {endpoint} - Pattern: {pattern}',
                ip_address=ip,
                endpoint=endpoint,
                request_data=request_data
            )
            
            try:
                from services.tasks import send_intrusion_alert
                send_intrusion_alert(threat, ip, endpoint)
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
        
        # Check XSS
        has_xss, xss_pattern = cls.detect_xss(data_str)
        if has_xss:
            threat = {
                'type': 'xss',
                'pattern': xss_pattern,
                'severity': 'high',
                'endpoint': endpoint
            }
            threats.append(threat)
            
            cls.create_suspicious_activity(
                severity='high',
                category='xss',
                description=f'XSS attempt at {endpoint} - Pattern: {xss_pattern}',
                ip_address=ip,
                endpoint=endpoint,
                request_data=request_data
            )
            
            try:
                from services.tasks import send_intrusion_alert
                send_intrusion_alert(threat, ip, endpoint)
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
        
        return threats

# Singleton instance
ids = IntrusionDetectionSystem()