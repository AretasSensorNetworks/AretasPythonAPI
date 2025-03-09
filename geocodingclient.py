import logging
import requests
import json
from typing import Optional, Tuple
from auth import APIAuth


class GeocodingAPIClient:
    """
    Client for interacting with the GeocodingService JAX-RS endpoint.
    """

    def __init__(self, api_auth: APIAuth):
        """
        Initializes the GeocodingAPIClient with the provided API authentication.

        Args:
            api_auth (APIAuth): An instance of APIAuth containing authentication details.
        """
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def get_client_location(self, location_str: str) -> Optional[Tuple[float, float]]:
        """
        Converts a location string into latitude and longitude coordinates by
        invoking the geocoder endpoint.

        Args:
            location_str (str): The location string to be geocoded.

        Returns:
            Optional[Tuple[float, float]]: A tuple containing (latitude, longitude) if successful,
            otherwise None.
        """
        url = self.api_auth.api_config.get_api_url() + "geocoder/fromstring"
        headers = {
            "Authorization": "Bearer " + self.api_auth.get_token(),
            "Content-Type": "application/json"
        }

        try:
            # The endpoint expects a JSON string in the request body.
            response = requests.post(url, headers=headers, data=json.dumps(location_str))
            if response.status_code == 200:
                data = response.json()
                # Assumes the returned JSON has "lat" and "lng" fields.
                lat = data.get("lat")
                lng = data.get("lng")
                if lat is not None and lng is not None:
                    return lat, lng
                else:
                    self.logger.warning("Unexpected response format: %s", data)
            else:
                self.logger.warning("Failed to geocode location. HTTP status: %s", response.status_code)
        except Exception as e:
            self.logger.error("Exception during geocoding: %s", e)

        return None

