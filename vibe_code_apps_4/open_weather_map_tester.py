import os
import requests
from dotenv import load_dotenv

load_dotenv()

"""
Change in .env file

metric = Celsius
imperial = Fahrenheit
standard = Kelvin
"""

API_KEY = os.getenv("OPENWEATHER_API_KEY")
CITY = os.getenv("CITY", "Madison,WI,US")
UNITS = os.getenv("UNITS", "metric")

if not API_KEY:
    raise ValueError("OPENWEATHER_API_KEY is not set in the .env file")

BASE_URL = (
    f"http://api.openweathermap.org/data/2.5/weather"
    f"?q={CITY}&appid={API_KEY}&units={UNITS}"
)

print(BASE_URL)

response = requests.get(BASE_URL)

if response.status_code == 200:
    data = response.json()
    main = data["main"]
    weather = data["weather"][0]

    unit_symbol = "°C" if UNITS == "metric" else "°F" if UNITS == "imperial" else "K"

    print(f"Weather in {CITY}:")
    print(f"Temperature: {main['temp']}{unit_symbol}")
    print(f"Humidity: {main['humidity']}%")
    print(f"Description: {weather['description']}")
else:
    print("Error fetching data")
    print(response.text)