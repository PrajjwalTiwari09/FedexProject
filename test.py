from flask import Flask, request, jsonify, render_template
import requests
import json
import urllib3  # To suppress SSL verification warnings

# Suppress SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# Geocoding function to convert place name to latitude and longitude using Here Geocoding API
def get_coordinates(place_name):
    # Your Here API Key
    here_api_key = "s2QMNkBVvxO1Mxy3L3ZQSLFoBDA-p7yvcz10WO-fMkk"  # Replace with your Here API Key
    url = f"https://geocode.search.hereapi.com/v1/geocode?q={place_name}&apiKey={here_api_key}"
    
    response = requests.get(url, verify=False)  # Bypass SSL certificate validation
    
    if response.status_code == 200:
        data = response.json()
        if 'items' in data and data['items']:
            latitude = data['items'][0]['position']['lat']
            longitude = data['items'][0]['position']['lng']
            return latitude, longitude
    return None

def get_realtime_traffic(origin, destination, tomtom_api_key):
    origin_formatted = f"{origin[0]},{origin[1]}"
    destination_formatted = f"{destination[0]},{destination[1]}"
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin_formatted}:{destination_formatted}/json?traffic=true&key={tomtom_api_key}"
    
    response = requests.get(url, verify=False)  # Bypass SSL certificate validation
    return response.json()

def get_weather_data(location, weather_api_key):
    # WeatherAPI endpoint for current weather data with AQI
    url = f"http://api.weatherapi.com/v1/current.json?key={weather_api_key}&q={location[0]},{location[1]}&aqi=yes"
    response = requests.get(url, verify=False)  # Bypass SSL certificate validation
    return response.json()

def get_route(origin, destination, vehicle_details, osrm_base_url):
    url = f"{osrm_base_url}/route/v1/driving/{origin[1]},{origin[0]};{destination[1]},{destination[0]}?overview=full"
    
    response = requests.get(url, verify=False)  # Bypass SSL certificate validation
    route_data = response.json()
    
    if 'routes' in route_data and route_data['routes']:
        route_info = route_data['routes'][0]
        route_distance = route_info['distance']  # meters
        route_duration = route_info['duration']  # seconds
        return route_distance, route_duration

    return None, None

def calculate_emissions(distance, vehicle_emission_rate):
    distance_km = distance / 1000  # Convert meters to kilometers
    emissions = distance_km * vehicle_emission_rate
    return emissions

def calculate_emission_rate(vehicle_type, fuel_type, model_year, current_year):
    emission_rate = 0

    # Default emission factors (g CO₂ per kilometer)
    if vehicle_type == "Passenger Car":
        if fuel_type == "Petrol":
            emission_rate = 130  # average for Petrol cars
        elif fuel_type == "Diesel":
            emission_rate = 160  # average for diesel cars
        elif fuel_type == "Electric":
            emission_rate = 0  # no emissions for electric vehicles

    elif vehicle_type == "Heavy-duty Truck":
        if fuel_type == "Petrol":
            emission_rate = 320  # average for etrol trucks
        elif fuel_type == "Diesel":
            emission_rate = 380  # average for diesel trucks

    # Adjust for the vehicle's age (older vehicles emit more)
    vehicle_age = current_year - model_year
    if vehicle_age > 10:
        emission_rate *= 1.2  # increase by 20% for vehicles older than 10 years

    return emission_rate

# New function to get AQI from AQICN API
def get_aqi_from_aqicn(lat, lon, aqicn_api_key):
    # AQICN API URL for retrieving AQI
    url = f"http://api.waqi.info/feed/geo:{lat};{lon}/?token={aqicn_api_key}"
    
    response = requests.get(url, verify=False)  # Bypass SSL certificate validation
    
    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'ok':
            aqi = data['data']['aqi']
            return aqi
    return None

@app.route('/')
def home():
    return render_template('index.html')  # This is your HTML file

@app.route('/calculate', methods=['POST'])
def calculate_route():
    # Retrieve form data from the HTML form
    origin_place = request.form['origin_place']
    dest_place = request.form['dest_place']
    vehicle_type = request.form['vehicle_type']
    fuel_type = request.form['fuel_type']
    model_year = int(request.form['model_year'])  # Vehicle model year
    current_year = 2025  # Or dynamically calculate using datetime
    
    # Calculate emission rate based on vehicle details
    emission_rate = calculate_emission_rate(vehicle_type, fuel_type, model_year, current_year)
    
    # Convert place names to coordinates using Here Geocoding API
    origin_coords = get_coordinates(origin_place)
    dest_coords = get_coordinates(dest_place)

    if origin_coords is None or dest_coords is None:
        return jsonify({"error": "Unable to geocode one or both locations."})

    # API keys
    tomtom_api_key = "SvAuSOH7Z458LUZLkG5NnNZ2I96vwgTB"  # Example API key
    weather_api_key = "1b61f76cf4fa4c44a1091646250401"  # WeatherAPI key
    aqicn_api_key = "82f673e22a7aac18dde439965cd8ea8a5e070e5a"  # AQICN API key
    osrm_base_url = "http://router.project-osrm.org"

    # Get traffic data, weather data, and route data
    traffic_data = get_realtime_traffic(origin_coords, dest_coords, tomtom_api_key)
    weather_data = get_weather_data(origin_coords, weather_api_key)
    route_distance, route_duration = get_route(origin_coords, dest_coords, {'emission_rate': emission_rate}, osrm_base_url)

    if route_distance is None or route_duration is None:
        return jsonify({"error": "Unable to retrieve route information."})

    # Get AQI data from AQICN API
    aqi = get_aqi_from_aqicn(origin_coords[0], origin_coords[1], aqicn_api_key)

    # Calculate emissions
    emissions = calculate_emissions(route_distance, emission_rate)

    # Format the weather data for better presentation
    weather_info = {
        "temperature": weather_data['current']['temp_c'],  # Temperature in Celsius
        "humidity": weather_data['current']['humidity'],  # Humidity percentage
        "condition": weather_data['current']['condition']['text'],  # Weather condition
        "aqi": aqi if aqi is not None else 'N/A'  # AQI from AQICN API
    }

    result = {
        "route_distance_km": round(route_distance / 1000, 2),
        "route_duration_min": round(route_duration / 60, 2),
        "emissions_kg": round(emissions / 1000, 2),
        "traffic_data": traffic_data,
        "weather_data": weather_info,
        "origin_coords": origin_coords,
        "dest_coords": dest_coords,
        "origin_place": origin_place,
        "dest_place": dest_place
    }

    # Return origin and destination coordinates, along with other details
    return jsonify({
        "route_distance_km": result["route_distance_km"],
        "route_duration_min": result["route_duration_min"],
        "emissions_kg": result["emissions_kg"],
        "traffic_data": result["traffic_data"],
        "weather_data": result["weather_data"],
        "origin_coords": result["origin_coords"],
        "dest_coords": result["dest_coords"],
        "origin_place": result["origin_place"],
        "dest_place": result["dest_place"]
    })


if __name__ == "__main__":
    app.run(debug=True)