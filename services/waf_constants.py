# services/waf_constants.py
"""
Shared constants and configuration for WAF system
"""

# Redis key prefixes
BLOCK_PREFIX = "waf:block:"
RATE_PREFIX = "waf:rate:"
REPUTATION_PREFIX = "waf:reputation:"
OFFENSE_PREFIX = "waf:offense:"
ALERT_PREFIX = "waf:alert:"
LOGIN_ATTEMPTS_PREFIX = "waf:login_attempts:"
STATS_CACHE_PREFIX = "waf:stats:"

# Progressive banning levels
BAN_LEVELS = {
    1: {'minutes': 10, 'label': 'Temporary'},
    2: {'minutes': 60, 'label': 'Hourly'},
    3: {'minutes': 1440, 'label': 'Daily'},
    4: {'minutes': 10080, 'label': 'Weekly'},
    5: {'minutes': 43200, 'label': 'Monthly'},
}

# Risk thresholds
DANGER_THRESHOLD = 8
HIGH_RISK_THRESHOLD = 5
MEDIUM_RISK_THRESHOLD = 2

# Rate limiting defaults
DEFAULT_RATE_LIMIT = 100
DEFAULT_RATE_WINDOW = 60  # seconds

# Offense thresholds
OFFENSE_BLOCK_THRESHOLD = 3
BRUTE_FORCE_THRESHOLD = 5
BRUTE_FORCE_WINDOW = 900  # 15 minutes in seconds

# Reputation defaults
DEFAULT_REPUTATION = 100
MAX_REPUTATION = 100
MIN_REPUTATION = 0

# Cache TTLs
STATS_CACHE_TTL = 30  # seconds
REPUTATION_TTL = 2592000  # 30 days in seconds

def get_ban_duration(offense_count):
    """Get ban duration based on offense count"""
    if offense_count >= 5:
        return BAN_LEVELS[5]['minutes']
    return BAN_LEVELS.get(offense_count, BAN_LEVELS[1])['minutes']

def get_ban_label(offense_count):
    """Get ban label based on offense count"""
    if offense_count >= 5:
        return BAN_LEVELS[5]['label']
    return BAN_LEVELS.get(offense_count, BAN_LEVELS[1])['label']