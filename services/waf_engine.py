# services/waf_engine.py
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from services.waf_blocklist import (
    is_blocked, block_ip, check_rate_limit, 
    get_block_info, update_reputation, get_reputation,
    get_offense_count, increment_offense, record_offense,
    check_brute_force
)
from services.ids_service import IntrusionDetectionSystem
from services.waf_constants import (
    DANGER_THRESHOLD, HIGH_RISK_THRESHOLD, MEDIUM_RISK_THRESHOLD,
    DEFAULT_RATE_LIMIT, DEFAULT_RATE_WINDOW
)

logger = logging.getLogger(__name__)

class WAFEngine:
    """Web Application Firewall Engine"""
    
    @staticmethod
    def evaluate(
        request_data: Optional[Dict[str, Any]], 
        ip: str, 
        endpoint: str, 
        user_agent: Optional[str] = None,
        method: str = 'GET'
    ) -> Dict[str, Any]:
        """
        Evaluate request and return decision
        
        Returns:
            Dict with keys: allow, reason, status, threats, score, block_info
        """
        if not ip:
            return {
                "allow": False,
                "reason": "Invalid IP address",
                "status": "error"
            }
        
        try:
            # 1. Blocklist check
            if is_blocked(ip):
                block_info = get_block_info(ip)
                return {
                    "allow": False,
                    "reason": f"IP blocked: {block_info.get('reason', 'Security policy violation')}",
                    "block_info": block_info,
                    "status": "blocked"
                }
            
            # 2. Rate limiting
            if not check_rate_limit(ip, DEFAULT_RATE_LIMIT, DEFAULT_RATE_WINDOW):
                offense_count = increment_offense(ip)
                block_ip(ip, "Rate limit exceeded", offense_count)
                return {
                    "allow": False,
                    "reason": "Rate limit exceeded",
                    "status": "rate_limited"
                }
            
            # 3. Check for brute force patterns
            if endpoint in ['/api/login', '/api/register']:
                username = request_data.get('username') or request_data.get('email') if request_data else None
                if check_brute_force(ip, username):
                    return {
                        "allow": False,
                        "reason": "Suspicious login pattern detected",
                        "status": "brute_force"
                    }
            
            # 4. IDS scan
            threats = WAFEngine._scan_request(request_data, ip, endpoint)
            
            # Calculate risk score
            risk_score = WAFEngine._calculate_risk_score(threats)
            
            # 5. Decision based on risk score
            if risk_score >= DANGER_THRESHOLD:
                return WAFEngine._handle_critical_threat(ip, threats, endpoint, risk_score)
            
            elif risk_score >= HIGH_RISK_THRESHOLD:
                return WAFEngine._handle_high_risk(ip, threats, endpoint, risk_score)
            
            elif risk_score >= MEDIUM_RISK_THRESHOLD:
                return WAFEngine._handle_medium_risk(ip, threats, risk_score)
            
            elif risk_score > 0:
                return WAFEngine._handle_low_risk(ip, risk_score)
            
            # 6. Safe request
            update_reputation(ip, 1)
            return {
                "allow": True,
                "status": "safe",
                "score": 0
            }
            
        except Exception as e:
            logger.error(f"WAF evaluation error for {ip}: {e}")
            # Allow on error to avoid blocking legitimate users
            return {
                "allow": True,
                "status": "error",
                "error": str(e)
            }
    
    @staticmethod
    def _scan_request(request_data: Optional[Dict], ip: str, endpoint: str) -> List[Dict]:
        """Scan request using IDS"""
        try:
            threats = IntrusionDetectionSystem.scan_request(
                request_data=request_data,
                ip_address=ip,
                endpoint=endpoint
            )
            return threats if threats else []
        except Exception as e:
            logger.error(f"IDS scan error for {ip}: {e}")
            return []
    
    @staticmethod
    def _calculate_risk_score(threats: List[Dict]) -> int:
        """Calculate risk score from threats"""
        score = 0
        severity_weights = {
            'critical': 5,
            'high': 3,
            'medium': 1,
            'low': 0
        }
        
        for threat in threats:
            severity = threat.get('severity', 'low').lower()
            score += severity_weights.get(severity, 0)
        
        return score
    
    @staticmethod
    def _handle_critical_threat(ip: str, threats: List[Dict], endpoint: str, risk_score: int) -> Dict:
        """Handle critical threat - block immediately"""
        offense_count = increment_offense(ip)
        block_ip(ip, f"Critical threat detected (score: {risk_score})", offense_count)
        
        # Update reputation
        update_reputation(ip, -20)
        
        # Send alerts for each threat
        for threat in threats:
            try:
                from services.tasks import send_intrusion_alert
                send_intrusion_alert(threat, ip, endpoint)
            except Exception as e:
                logger.error(f"Failed to send intrusion alert: {e}")
        
        return {
            "allow": False,
            "reason": f"Critical threat detected (score: {risk_score})",
            "threats": threats,
            "status": "blocked_critical",
            "score": risk_score
        }
    
    @staticmethod
    def _handle_high_risk(ip: str, threats: List[Dict], endpoint: str, risk_score: int) -> Dict:
        """Handle high risk - block temporarily"""
        offense_count = increment_offense(ip)
        ban_minutes = block_ip(ip, f"High risk attack (score: {risk_score})", offense_count)
        
        # Send alerts
        for threat in threats:
            try:
                from services.tasks import send_intrusion_alert
                send_intrusion_alert(threat, ip, endpoint)
            except Exception as e:
                logger.error(f"Failed to send intrusion alert: {e}")
        
        update_reputation(ip, -10)
        
        return {
            "allow": False,
            "reason": f"High risk detected (score: {risk_score})",
            "threats": threats,
            "status": "blocked_high",
            "score": risk_score,
            "ban_minutes": ban_minutes
        }
    
    @staticmethod
    def _handle_medium_risk(ip: str, threats: List[Dict], risk_score: int) -> Dict:
        """Handle medium risk - log and monitor only"""
        # Send alerts for medium risk
        for threat in threats:
            try:
                from services.tasks import send_intrusion_alert
                send_intrusion_alert(threat, ip, "unknown")
            except Exception as e:
                logger.error(f"Failed to send intrusion alert: {e}")
        
        update_reputation(ip, -5)
        
        return {
            "allow": True,
            "threats": threats,
            "status": "monitored",
            "score": risk_score
        }
    
    @staticmethod
    def _handle_low_risk(ip: str, risk_score: int) -> Dict:
        """Handle low risk - monitor only"""
        update_reputation(ip, -1)
        return {
            "allow": True,
            "status": "monitored_low",
            "score": risk_score
        }
    
    @staticmethod
    def get_status(ip: str) -> Dict[str, Any]:
        """Get WAF status for an IP"""
        if not ip:
            return {'error': 'Invalid IP'}
        
        status = {
            'ip': ip,
            'blocked': is_blocked(ip),
            'reputation': get_reputation(ip),
            'offense_count': get_offense_count(ip),
            'rate_limit': get_rate_limit_info(ip)
        }
        
        if is_blocked(ip):
            status['block_info'] = get_block_info(ip)
        
        return status

# ========== COMPATIBILITY FUNCTIONS ==========

def is_request_safe(
    request_data: Optional[Dict], 
    ip: str, 
    endpoint: str,
    user_agent: Optional[str] = None,
    method: str = 'GET'
) -> Tuple[bool, List[Dict]]:
    """
    Compatibility function for waf_middleware
    Returns (is_safe, threats)
    """
    result = WAFEngine.evaluate(request_data, ip, endpoint, user_agent, method)
    return result.get('allow', False), result.get('threats', [])

# Singleton instance
waf_engine = WAFEngine()