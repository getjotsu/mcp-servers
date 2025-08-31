import json
import logging
import typing

import httpx
from mcp.server.fastmcp import FastMCP


# Constants
OPEN_METEO_API_BASE = 'https://api.open-meteo.com/v1'
USER_AGENT = 'weather/1.0 (jotsu.com, getjotsu@gmail.com)'

UNITS = 'temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch'


async def make_open_meteo_request(url: str) -> dict[str, typing.Any] | None:
    """Make requests to the Open Meteo API."""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json'
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            if response.status_code != 200:
                logging.error(json.dumps(dict(response.headers)))
                logging.error(response.text)
            response.raise_for_status()
            return response.json()
        except Exception as e:  # noqa
            logging.error(e)
            return None


DEFAULT_PORT = 8000


def setup_server():
    mcp = FastMCP('Open Meteo MCP Server', stateless_http=True, port=DEFAULT_PORT)

    @mcp.tool()
    async def get_current_weather(latitude: float, longitude: float) -> str:
        """Get current weather for a location.
          Args:
            latitude: Latitude of the location
            longitude: Longitude of the location

        Returns:
            str: JSON string with current weather data
        """
        current = 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code'
        url = f'{OPEN_METEO_API_BASE}/forecast?latitude={latitude}&longitude={longitude}&{UNITS}&current={current}'
        data = await make_open_meteo_request(url)

        if not data:
            return 'Unable to fetch weather data.'

        return json.dumps(data, indent=2)

    @mcp.tool()
    async def get_forecast(latitude: float, longitude: float) -> str:
        """Get weather forecast for a location.
        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location

        Returns:
            str: Formatted weather forecast
        """
        daily = 'temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code'
        url = f'{OPEN_METEO_API_BASE}/forecast?latitude={latitude}&longitude={longitude}&{UNITS}&daily={daily}&timezone=auto'  # noqa
        data = await make_open_meteo_request(url)

        if not data:
            return 'Unable to fetch forecast data.'

        # Format the data for readability
        daily = data.get('daily', {})
        forecasts = []

        for i in range(len(daily.get('time', []))):
            forecast = f"""Date: {daily['time'][i]}
Max Temperature: {daily['temperature_2m_max'][i]}°F
Min Temperature: {daily['temperature_2m_min'][i]}°F
Precipitation: {daily['precipitation_sum'][i]} in"""
            forecasts.append(forecast)

        return '\n---\n'.join(forecasts)

    return mcp
