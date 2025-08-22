import json
import requests
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"  # needed for flash messages

GEO_API = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"


def geocode_city(city: str):
    """Return first geocoding match: {name, country, latitude, longitude, timezone} or None."""
    params = {
        "name": city,
        "count": 1,
        "language": "en",
        "format": "json",
    }
    r = requests.get(GEO_API, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        return None
    r0 = results[0]
    return {
        "name": r0.get("name"),
        "country": r0.get("country"),
        "latitude": r0.get("latitude"),
        "longitude": r0.get("longitude"),
        "timezone": r0.get("timezone"),
    }


def get_forecast(lat: float, lon: float, timezone: str | None = None):
    """Fetch daily + current forecast."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": timezone or "auto",
        "daily": [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "windspeed_10m_max",
        ],
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "wind_speed_10m",
        ],
    }
    params["daily"] = ",".join(params["daily"])
    params["current"] = ",".join(params["current"])

    r = requests.get(FORECAST_API, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        city = (request.form.get("city") or "").strip()
        if not city:
            flash("Please enter a city.")
            return redirect(url_for("index"))

        try:
            place = geocode_city(city)
            if not place:
                flash(f"No results for '{city}'. Try another city.")
                return redirect(url_for("index"))

            wx = get_forecast(place["latitude"], place["longitude"], place["timezone"])

            current = wx.get("current") or {}

            weather = {
                "city": place["name"],
                "temp": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "pressure": None,  # Open-Meteo does not provide pressure
                "desc": "N/A",    # No description from Open-Meteo current data
                # Use a default icon code, you can customize this mapping if needed
                "icon": "01d"
            }

            daily = wx.get("daily") or {}
            dates = daily.get("time", [])
            tmax = daily.get("temperature_2m_max", [])
            precipitation = daily.get("precipitation_sum", [])

            forecast = []
            for i in range(len(dates)):
                forecast.append({
                    "date": dates[i],
                    "temp": tmax[i] if i < len(tmax) else None,
                    "desc": f"Precipitation: {precipitation[i]} mm" if i < len(precipitation) else "",
                    "icon": "01d"  # Default icon for forecast days (customizable)
                })

            return render_template(
                "index.html",
                weather=weather,
                forecast=forecast,
            )

        except requests.HTTPError as e:
            flash(f"API error: {e}")
            return redirect(url_for("index"))
        except requests.RequestException as e:
            flash(f"Network error: {e}")
            return redirect(url_for("index"))
        except Exception as e:
            flash(f"Unexpected error: {e}")
            return redirect(url_for("index"))

    # On GET, render empty template with no weather
    return render_template("index.html", weather=None, forecast=None)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)