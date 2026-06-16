# backend/services/geo_service.py
import requests
from datetime import datetime, timedelta
import ipaddress
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple in-memory cache to reduce API calls
geo_cache = {}

def is_private_ip(ip_address):
    """Check if an IP address is private/local/internal"""
    if not ip_address:
        return True
    
    if isinstance(ip_address, str):
        ip_address = ip_address.strip()
    
    try:
        ip = ipaddress.ip_address(ip_address)
        return ip.is_private
    except ValueError:
        return True

def get_public_ip(ip_string):
    """Extract the first public IP from X-Forwarded-For or use the IP directly"""
    if not ip_string:
        return None
    
    # If it's a comma-separated list (X-Forwarded-For), take the first one
    if ',' in ip_string:
        first_ip = ip_string.split(',')[0].strip()
        return first_ip
    
    return ip_string.strip()

def get_geolocation(ip_address):
    """Get geolocation using multiple free services with caching"""
    if not ip_address:
        logger.warning("No IP address provided")
        return 'Unknown', 'Unknown'
    
    clean_ip = get_public_ip(ip_address)
    
    if not clean_ip:
        logger.warning("Could not extract clean IP from: %s", ip_address)
        return 'Unknown', 'Unknown'
    
    if is_private_ip(clean_ip):
        logger.info("Private IP detected: %s", clean_ip)
        return 'Local', 'Local'
    
    # Check cache first (24 hour TTL)
    if clean_ip in geo_cache:
        cached_time, country, city = geo_cache[clean_ip]
        if datetime.now() - cached_time < timedelta(hours=24):
            logger.debug("Cache hit for IP: %s -> %s, %s", clean_ip, country, city)
            return country, city
    
    logger.info("Looking up geolocation for IP: %s", clean_ip)
    
    # Try services in order
    services = [
        _geo_ip_api,
        _geo_ipwhois,
        _geo_ipinfo,
    ]
    
    for service in services:
        try:
            country, city = service(clean_ip)
            if country and country != 'Unknown':
                geo_cache[clean_ip] = (datetime.now(), country, city)
                logger.info("Geolocation found: %s, %s for IP: %s", country, city, clean_ip)
                return country, city
        except Exception as e:
            logger.warning("Service %s failed for IP %s: %s", service.__name__, clean_ip, str(e))
            continue
    
    logger.warning("All geolocation services failed for IP: %s", clean_ip)
    return 'Unknown', 'Unknown'

def _geo_ip_api(ip_address):
    """ip-api.com - 45 req/min, free for non-commercial"""
    try:
        response = requests.get(f'https://ipapi.co/{ip_address}/json/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('country_name'):
                return data.get('country_name', 'Unknown'), data.get('city', 'Unknown')
    except requests.exceptions.RequestException as e:
        logger.debug("ipapi.co request failed: %s", e)
    
    try:
        response = requests.get(f'http://ip-api.com/json/{ip_address}', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success':
                return data.get('country', 'Unknown'), data.get('city', 'Unknown')
    except requests.exceptions.RequestException as e:
        logger.debug("ip-api.com fallback failed: %s", e)
    
    return 'Unknown', 'Unknown'

def _geo_ipwhois(ip_address):
    """ipwhois.io - 10,000 requests per month free"""
    try:
        response = requests.get(f'https://ipwhois.io/json/{ip_address}', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') != False and data.get('country'):
                return data.get('country', 'Unknown'), data.get('city', 'Unknown')
    except requests.exceptions.RequestException as e:
        logger.debug("ipwhois.io request failed: %s", e)
    return 'Unknown', 'Unknown'

def _geo_ipinfo(ip_address):
    """ipinfo.io - 50,000 requests per month free"""
    try:
        response = requests.get(f'https://ipinfo.io/{ip_address}/json', timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('country'):
                return data.get('country', 'Unknown'), data.get('city', 'Unknown')
    except requests.exceptions.RequestException as e:
        logger.debug("ipinfo.io request failed: %s", e)
    return 'Unknown', 'Unknown'

def get_country_code(country_name):
    """Get ISO country code from country name for flags"""
    country_codes = {
        'United States': 'US',
        'United Kingdom': 'GB',
        'Canada': 'CA',
        'Australia': 'AU',
        'Germany': 'DE',
        'France': 'FR',
        'Japan': 'JP',
        'China': 'CN',
        'India': 'IN',
        'Brazil': 'BR',
        'Russia': 'RU',
        'Italy': 'IT',
        'Spain': 'ES',
        'Mexico': 'MX',
        'Netherlands': 'NL',
        'South Korea': 'KR',
        'Kenya': 'KE',
        'Nigeria': 'NG',
        'South Africa': 'ZA',
        'Egypt': 'EG',
        'Ghana': 'GH',
        'Tanzania': 'TZ',
        'Uganda': 'UG',
        'Rwanda': 'RW',
        'Ethiopia': 'ET',
        'Somalia': 'SO',
        'Sudan': 'SD',
        'Zimbabwe': 'ZW',
        'Zambia': 'ZM',
        'Mozambique': 'MZ',
        'Angola': 'AO',
        'Botswana': 'BW',
        'Namibia': 'NA',
        'Malawi': 'MW',
        'Mauritius': 'MU',
        'Seychelles': 'SC',
        'Madagascar': 'MG',
        'Comoros': 'KM',
        'Mauritania': 'MR',
        'Senegal': 'SN',
        'Mali': 'ML',
        'Niger': 'NE',
        'Chad': 'TD',
        'Cameroon': 'CM',
        'Gabon': 'GA',
        'Congo': 'CG',
        'DR Congo': 'CD',
        'Ivory Coast': 'CI',
        'Burkina Faso': 'BF',
        'Benin': 'BJ',
        'Togo': 'TG',
        'Sierra Leone': 'SL',
        'Liberia': 'LR',
        'Guinea': 'GN',
        'Gambia': 'GM',
        'Morocco': 'MA',
        'Algeria': 'DZ',
        'Tunisia': 'TN',
        'Libya': 'LY',
        'Egypt': 'EG',
        'United Arab Emirates': 'AE',
        'Saudi Arabia': 'SA',
        'Qatar': 'QA',
        'Oman': 'OM',
        'Kuwait': 'KW',
        'Bahrain': 'BH',
        'Lebanon': 'LB',
        'Jordan': 'JO',
        'Iraq': 'IQ',
        'Iran': 'IR',
        'Israel': 'IL',
        'Palestine': 'PS',
        'Syria': 'SY',
        'Turkey': 'TR',
        'Pakistan': 'PK',
        'Afghanistan': 'AF',
        'Bangladesh': 'BD',
        'Sri Lanka': 'LK',
        'Nepal': 'NP',
        'Bhutan': 'BT',
        'Myanmar': 'MM',
        'Thailand': 'TH',
        'Vietnam': 'VN',
        'Cambodia': 'KH',
        'Laos': 'LA',
        'Malaysia': 'MY',
        'Singapore': 'SG',
        'Philippines': 'PH',
        'Indonesia': 'ID',
        'New Zealand': 'NZ',
        'Fiji': 'FJ',
        'Samoa': 'WS',
        'Tonga': 'TO',
    }
    return country_codes.get(country_name, '')

def clear_cache():
    """Clear the geolocation cache"""
    global geo_cache
    geo_cache = {}
    logger.info("Geolocation cache cleared")

def get_cache_stats():
    """Get cache statistics"""
    return {
        'cache_size': len(geo_cache),
        'cache_keys': list(geo_cache.keys())
    }