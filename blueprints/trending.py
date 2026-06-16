# blueprints/trending.py
from flask import jsonify, request, current_app
from models import TrendingNews
from exts import db, csrf
from funcs import super_admin_required
from middleware.security_middleware import security_middleware
from . import trending_bp
from datetime import datetime, timedelta
import requests

HTTP_SESSION = requests.Session()

# City coordinates for Kenya
CITY_COORDINATES = {
    'Nairobi': {'lat': -1.2921, 'lon': 36.8219},
    'Mombasa': {'lat': -4.0435, 'lon': 39.6682},
    'Kisumu': {'lat': -0.1022, 'lon': 34.7617},
    'Nakuru': {'lat': -0.3031, 'lon': 36.0800},
}

# Weather code to description mapping
WEATHER_CODES = {
    0: ('Clear sky', '☀️'),
    1: ('Mainly clear', '🌤️'),
    2: ('Partly cloudy', '⛅'),
    3: ('Overcast', '☁️'),
    45: ('Foggy', '🌫️'),
    48: ('Depositing rime fog', '🌫️'),
    51: ('Light drizzle', '🌦️'),
    53: ('Moderate drizzle', '🌦️'),
    55: ('Dense drizzle', '🌧️'),
    61: ('Slight rain', '🌧️'),
    63: ('Moderate rain', '🌧️'),
    65: ('Heavy rain', '🌧️'),
    71: ('Slight snow', '❄️'),
    73: ('Moderate snow', '❄️'),
    75: ('Heavy snow', '❄️'),
    80: ('Slight rain showers', '🌦️'),
    81: ('Moderate rain showers', '🌦️'),
    82: ('Violent rain showers', '🌧️'),
    95: ('Thunderstorm', '⛈️'),
}

def get_weather_for_city(city="Nairobi"):
    """Fetch weather for a city using Open-Meteo API"""
    coords = CITY_COORDINATES.get(city, CITY_COORDINATES['Nairobi'])

    try:
        print(f"📡 Attempting to fetch weather for {city}...")
        print(f"   Params: lat={coords['lat']}, lon={coords['lon']}")
        
        response = HTTP_SESSION.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                'latitude': coords['lat'],
                'longitude': coords['lon'],
                'current_weather': 'true',
                'temperature_unit': 'celsius',
                'timezone': 'Africa/Nairobi'
            },
            timeout=10
        )

        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ API returned {response.status_code}: {response.text[:200]}")
        
        response.raise_for_status()

        data = response.json()
        current = data.get('current_weather', {})
        
        print(f"✅ Success! Weather data: temp={current.get('temperature')}, code={current.get('weathercode')}")

        weather_code = current.get('weathercode', 0)
        condition, icon = WEATHER_CODES.get(
            weather_code,
            ('Unknown', '🌡️')
        )

        return {
            'city': city,
            'temp': round(current.get('temperature', 22)),
            'condition': condition,
            'icon': icon
        }

    except requests.exceptions.Timeout:
        current_app.logger.warning(f"Weather API timeout for {city}")
        print(f"⏰ Timeout for {city}")

    except requests.exceptions.ConnectionError as ce:
        current_app.logger.warning(f"Weather API connection error for {city}: {ce}")
        print(f"🔌 Connection error: {ce}")

    except Exception as e:
        current_app.logger.exception(f"Weather API error for {city}")
        print(f"❌ Unexpected error: {type(e).__name__}: {e}")

    # Fallback to default weather
    print(f"⚠️ Returning fallback weather for {city}")
    return {
        'city': city,
        'temp': 22,
        'condition': 'Partly Cloudy',
        'icon': '☁️'
    }


@trending_bp.route('/trending', methods=['GET'])
@csrf.exempt
def get_trending_news():
    """Get all active trending news headlines, with weather fallback"""
    try:
        now = datetime.now()

        trending = TrendingNews.query.filter(
            TrendingNews.is_active.is_(True),
            TrendingNews.expires_at > now
        ).order_by(
            TrendingNews.created_at.desc()
        ).all()
        
        # If no trending news, return weather data
        if not trending:
            weather_data = get_weather_for_city("Nairobi")
            return jsonify({
                'type': 'weather',
                'data': weather_data,
                'message': 'No trending news at the moment'
            }), 200
        
        return jsonify({
            'type': 'trending',
            'data': [{
                'id': t.id,
                'headline': t.headline,
                'created_at': t.created_at.isoformat(),
                'expires_at': t.expires_at.isoformat()
            } for t in trending]
        }), 200
        
    except Exception as e:
        print(f"Error getting trending news: {e}")
        weather_data = get_weather_for_city("Nairobi")
        return jsonify({
            'type': 'weather',
            'data': weather_data,
            'message': 'Weather update'
        }), 200


@trending_bp.route('/trending/weather', methods=['GET'])
@csrf.exempt
def get_weather_update():
    """Get weather update for multiple cities"""
    try:
        cities = ['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru']
        weather_updates = []
        
        print(f"🌍 Fetching weather for {len(cities)} cities...")
        
        for city in cities:
            weather_updates.append(get_weather_for_city(city))
        
        return jsonify({
            'type': 'weather',
            'data': weather_updates,
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        print(f"Error getting weather: {e}")
        return jsonify({'error': str(e)}), 500


@trending_bp.route('/trending/weather/city/<city>', methods=['GET'])
@csrf.exempt
def get_weather_by_city(city):
    city = city.title()

    if city not in CITY_COORDINATES:
        return jsonify({
            "error": "Unsupported city"
        }), 404

    weather_data = get_weather_for_city(city)
    return jsonify(weather_data), 200


# ========== ADMIN ENDPOINTS ==========

@trending_bp.route('/admin/trending', methods=['GET'])
@csrf.exempt
@super_admin_required
def get_admin_trending():
    """Get all trending news (admin view)"""
    try:
        trending = TrendingNews.query.order_by(TrendingNews.created_at.desc()).all()
        return jsonify([{
            'id': t.id,
            'headline': t.headline,
            'is_active': t.is_active,
            'created_at': t.created_at.isoformat(),
            'expires_at': t.expires_at.isoformat()
        } for t in trending]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@trending_bp.route('/admin/trending', methods=['POST', 'OPTIONS'])
@csrf.exempt
@super_admin_required
@security_middleware
def create_trending():
    """Create a new trending news headline"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.json
        
        if not data or 'headline' not in data or not data['headline'].strip():
            return jsonify({'error': 'Headline is required'}), 400
        
        expires_at = datetime.now() + timedelta(hours=12)
        
        trending = TrendingNews(
            headline=data['headline'].strip(),
            is_active=True,
            expires_at=expires_at
        )
        db.session.add(trending)
        db.session.commit()
        
        return jsonify({
            'message': 'Trending news created successfully',
            'id': trending.id,
            'expires_at': expires_at.isoformat()
        }), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Error creating trending")
        return jsonify({'error': str(e)}), 500


@trending_bp.route('/admin/trending/<int:trending_id>', methods=['DELETE', 'OPTIONS'])
@csrf.exempt
@super_admin_required
@security_middleware
def delete_trending(trending_id):
    """Delete trending news"""
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        trending = TrendingNews.query.get_or_404(trending_id)
        db.session.delete(trending)
        db.session.commit()
        
        return jsonify({'message': 'Trending news deleted successfully'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting trending: {e}")
        return jsonify({'error': str(e)}), 500