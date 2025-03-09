import logging
import requests
from typing import Optional, Tuple

from api_config import APIConfig
from auth import APIAuth  # Assumes an APIAuth class is available for API configuration and token management


class IpUtilAPIClient:
    """
    Client for interacting with the IpUtils JAX-RS endpoints.
    """

    def __init__(self, api_auth: APIAuth):
        """
        Initializes the IpUtilAPIClient with the provided API authentication.

        Args:
            api_auth (APIAuth): An instance containing API URL and authentication token details.
        """
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def get_client_ip(self) -> Optional[str]:
        """
        Retrieves the client's IP address from the API.

        Returns:
            Optional[str]: The client's IP address as a string if successful; otherwise, None.
        """
        url = self.api_auth.api_config.get_api_url() + "iputil/getip"
        headers = {
            "Authorization": "Bearer " + self.api_auth.get_token()
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                # The endpoint returns a JSON string containing the IP address.
                ip_address = response.text
                return ip_address
            else:
                self.logger.warning("Failed to retrieve client IP. HTTP status: %s", response.status_code)
        except Exception as e:
            self.logger.error("Exception during get_client_ip: %s", e)

        return None

    def get_client_location(self) -> Optional[Tuple[float, float]]:
        """
        Retrieves the client's geographical location (latitude and longitude) based on their IP.

        Returns:
            Optional[Tuple[float, float]]: A tuple (latitude, longitude) if successful; otherwise, None.
        """
        url = self.api_auth.api_config.get_api_url() + "iputil/getlocation"
        headers = {
            "Authorization": "Bearer " + self.api_auth.get_token(),
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                # Expecting a JSON object with keys "lat" and "lng"
                lat = data.get("lat")
                lng = data.get("lng")
                if lat is not None and lng is not None:
                    return lat, lng
                else:
                    self.logger.warning("Unexpected response format: %s", data)
            else:
                self.logger.warning("Failed to retrieve client location. HTTP status: %s", response.status_code)
        except Exception as e:
            self.logger.error("Exception during get_client_location: %s", e)

        return None

