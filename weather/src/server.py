import json
import logging
import typing
import httpx
from starlette.responses import PlainTextResponse
from mcp.server.fastmcp import FastMCP

# Constants
NWS_API_BASE = 'https://api.weather.gov'
USER_AGENT = 'weather-mcp/1.0 (jotsu.com, getjotsu@gmail.com)'


async def make_nws_request(url: str) -> dict[str, typing.Any] | None:
    """Make a request to the NWS API with proper error handling."""
    headers = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/geo+json'
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


def format_alert(feature: dict) -> str:
    """Format an alert feature into a readable string."""
    props = feature['properties']
    return f"""
Event: {props.get('event', 'Unknown')}
Area: {props.get('areaDesc', 'Unknown')}
Severity: {props.get('severity', 'Unknown')}
Description: {props.get('description', 'No description available')}
Instructions: {props.get('instruction', 'No specific instructions provided')}
"""


def setup_server():
    mcp = FastMCP('NWS Weather MCP Server', stateless_http=True)

    @mcp.tool()
    async def get_alerts(state: str) -> str:
        """Get weather alerts for a US state.

        Args:
            state: Two-letter US state code (e.g. CA, NY)
        """
        url = f'{NWS_API_BASE}/alerts/active/area/{state}'
        data = await make_nws_request(url)

        if not data or 'features' not in data:
            return 'Unable to fetch alerts or no alerts found.'

        if not data['features']:
            return 'No active alerts for this state.'

        alerts = [format_alert(feature) for feature in data['features']]
        return '\n---\n'.join(alerts)

    @mcp.tool()
    async def get_forecast(latitude: float, longitude: float) -> str:
        """Get weather forecast for a location.

        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
        """
        # First get the forecast grid endpoint
        points_url = f'{NWS_API_BASE}/points/{latitude},{longitude}'
        points_data = await make_nws_request(points_url)

        if not points_data:
            return 'Unable to fetch forecast data for this location.'

        # Get the forecast URL from the points response
        forecast_url = points_data['properties']['forecast']
        forecast_data = await make_nws_request(forecast_url)

        if not forecast_data:
            return 'Unable to fetch detailed forecast.'

        # Format the periods into a  readable forecast
        periods = forecast_data['properties']['periods']
        forecasts = []
        for period in periods[:5]:  # Only show next 5 periods
            forecast = f"""
    {period['name']}:
    Temperature: {period['temperature']}°{period['temperatureUnit']}
    Wind: {period['windSpeed']} {period['windDirection']}
    Forecast: {period['detailedForecast']}
    """
            forecasts.append(forecast)

        return '\n---\n'.join(forecasts)

    @mcp.custom_route('/', methods=['GET'])
    async def root(*_args):
        return PlainTextResponse(f'{mcp.name}\n')

    return mcp
