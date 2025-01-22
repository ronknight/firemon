from flask import Flask, render_template, jsonify, request
import requests
import time
import threading
import os

app = Flask(__name__)

# NWS API endpoint for active alerts in California
NWS_API_URL = "https://api.weather.gov/alerts/active?area=CA"

# Default map center (Los Angeles)
DEFAULT_MAP_CENTER = [34.0522, -118.2437]

# Cache for storing fetched alerts
alert_cache = {
    "alerts": None,
    "last_updated": 0,
    "relevant_alerts": [],
}

# Update interval in seconds (1 hour)
UPDATE_INTERVAL = 3600

# Keywords for fire and evacuation alerts
KEYWORDS = ["fire", "evacuate", "wildfire", "red flag", "burn"]

# NWS Event Types for filtering
EVENT_TYPES = [
    "Red Flag Warning",
    "Fire Weather Watch",
    "Evacuation Immediate",
    "Evacuation Order",
]


# Function to fetch active alerts
def fetch_alerts():
    headers = {"User-Agent": "FireAlertMonitor/1.0 (webmaster@pinoyitsolution.com)"}
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            response = requests.get(NWS_API_URL, headers=headers)
            response.raise_for_status()
            if not response.text:
                print("Warning: Empty response received from NWS API.")
                return None
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay *= 2
    print("Failed to fetch alerts after multiple retries.")
    return None


# Function to check if the alert is relevant to your location
def is_alert_relevant(alert, user_location):
    properties = alert.get("properties", {})
    area_desc = properties.get("areaDesc", "").lower()
    event_type = properties.get("event", "").lower()

    # Check if user_location is not None before accessing its attributes
    if user_location:
        is_location_relevant = (
            user_location["county"].lower() in area_desc
            or user_location["city"].lower() in area_desc
            or user_location["postal_code"] in area_desc
        )
    else:
        is_location_relevant = False

    is_keyword_relevant = any(
        keyword.lower() in area_desc or keyword.lower() in event_type
        for keyword in KEYWORDS
    )
    is_event_type_relevant = any(
        event.lower() in event_type.lower() for event in EVENT_TYPES
    )
    return is_location_relevant and (is_keyword_relevant or is_event_type_relevant)


# Function to get the user's location using their IP address
def get_user_location():
    try:
        # Use ip-api.com to get location data based on IP
        response = requests.get("http://ip-api.com/json/").json()

        # Extract relevant information
        location_data = {
            "county": response.get("regionName", ""),
            "city": response.get("city", ""),
            "postal_code": response.get("zip", ""),
            "latitude": response.get("lat", DEFAULT_MAP_CENTER[0]),
            "longitude": response.get("lon", DEFAULT_MAP_CENTER[1]),
        }
        return location_data

    except Exception as e:
        print(f"Error getting user location: {e}")
        return None


# Function to update the alert cache
def update_alert_cache(user_location=None):
    global alert_cache
    print("Updating alert cache...")
    alerts = fetch_alerts()

    if alerts and "features" in alerts:
        relevant_alerts = []
        for alert in alerts["features"]:
            try:
                if is_alert_relevant(alert, user_location):
                    relevant_alerts.append(alert)
            except Exception as e:
                print(f"Error processing alert: {e}")

        alert_cache = {
            "alerts": alerts,
            "last_updated": time.time(),
            "relevant_alerts": relevant_alerts,
        }
        print(f"Alert cache updated. Found {len(relevant_alerts)} relevant alerts.")
    else:
        print("Alert cache not updated due to fetch failure or no alerts.")


# Background thread for periodic updates
def background_update():
    while True:
        update_alert_cache()
        time.sleep(UPDATE_INTERVAL)

@app.route('/update_map_center', methods=['POST'])
def update_map_center():
    global DEFAULT_MAP_CENTER
    data = request.json
    DEFAULT_MAP_CENTER = data.get('map_center', DEFAULT_MAP_CENTER)
    return jsonify({"status": "success", "map_center": DEFAULT_MAP_CENTER})

# Start the background thread
update_thread = threading.Thread(target=background_update, daemon=True)
update_thread.start()


# Flask routes
@app.route("/", methods=["GET", "POST"])
def index():
    user_location = None
    map_center = DEFAULT_MAP_CENTER  # Set a default map center

    if request.method == "POST":
        # Update user_location based on form data
        user_location = {
            "county": request.form.get("county"),
            "city": request.form.get("city"),
            "postal_code": request.form.get("postal_code"),
            "latitude": None,  # Latitude and longitude are not used in this version
            "longitude": None,
        }
        # Use form data for filtering alerts
        update_alert_cache(user_location)

        # Update map_center based on form submission
        if user_location:
            user_location_from_ip = get_user_location()
            map_center = [
                user_location_from_ip["latitude"],
                user_location_from_ip["longitude"],
            ]
    else:
        # Get user's location from IP on initial load
        user_location = get_user_location()
        update_alert_cache(user_location)  # Pass user_location to update_alert_cache

        # Set map center from IP-based location on initial load
        if user_location:
            map_center = [user_location["latitude"], user_location["longitude"]]

    # Extract coordinates for relevant alerts
    alert_coordinates = []
    for alert in alert_cache["relevant_alerts"]:
        if alert["geometry"] and alert["geometry"]["type"] == "Polygon":
            # Take the first point of the polygon as the marker location
            coordinates = alert["geometry"]["coordinates"][0][0]
            alert_coordinates.append(coordinates)

    return render_template(
        "index.html",
        user_location=user_location,
        relevant_alerts=alert_cache["relevant_alerts"],
        last_updated=alert_cache["last_updated"],
        map_center=map_center,
        alert_coordinates=alert_coordinates,
    )


@app.route("/alerts")
def get_alerts():
    return jsonify(
        {
            "last_updated": alert_cache["last_updated"],
            "relevant_alerts": alert_cache["relevant_alerts"],
        }
    )


@app.route('/get_map_center', methods=['GET'])
def get_map_center():
    return jsonify({"map_center": DEFAULT_MAP_CENTER})


@app.template_filter("datetimeformat")
def datetimeformat(value, format="%Y-%m-%d %H:%M:%S"):
    if value:
        return time.strftime(format, time.localtime(value))
    else:
        return "N/A"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)