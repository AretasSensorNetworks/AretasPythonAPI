import logging
import requests
from typing import Optional

from api_config import APIConfig
from auth import APIAuth


class TimeZoneAPIClient:
    """
    Client for interacting with the TimeZoneIdService JAX-RS endpoint.
    """

    def __init__(self, api_auth: APIAuth):
        """
        Initializes the TimeZoneAPIClient with the provided base URL.

        Args:
            api_auth: APIAuth (str): instantiated APIAuth class
        """
        # Ensure no trailing slash for proper URL construction
        self.base_url = api_auth.api_config.get_api_url()
        self.logger = logging.getLogger(__name__)

    def get_timezone_id(self, lat: float, lon: float) -> Optional[str]:
        """
        Queries the timezone id for the given latitude and longitude.

        Args:
            lat (float): The latitude coordinate.
            lon (float): The longitude coordinate.

        Returns:
            Optional[str]: The timezone id as a string if found, otherwise None.
        """
        url = f"{self.base_url}timezone/query?lat={lat}&lon={lon}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                # Expecting the JSON to contain keys "booleanResponse" and "message"
                if data.get("booleanResponse"):
                    return data.get("message")
                else:
                    self.logger.warning("Timezone not found for coordinates: %s, %s", lat, lon)
            else:
                self.logger.warning("Failed to query timezone. HTTP status: %s", response.status_code)
        except Exception as e:
            self.logger.error("Exception during get_timezone_id: %s", e)

        return None
