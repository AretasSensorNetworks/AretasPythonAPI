import logging
from typing import List, Optional

from auth import APIAuth
from entities import WebServiceBoolean
from rest_helper import authed_request, ws_bool_from_response


class SiteLocationService:
    """
    Create, list, update and delete site locations (buildings / sites) in the account.

    Site locations are the parents of devices: a device's `owner` is its site location's id.
    The API never returns the id of a newly created location, so `create()` is normally
    followed by `find_by_description()`.
    """

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def build(owner: str, description: str, lat: float = 0.0, lon: float = 0.0, timezone: str = "",
              street_address: str = "", city: str = "", state: str = "", country: str = "",
              zip_code: str = "") -> dict:
        """
        Build a site location document ready for create()

        :param owner: the account's client id (must be the authenticated account)
        :param description: display name of the location
        :param lat: latitude
        :param lon: longitude
        :param timezone: IANA timezone id (e.g. "America/Vancouver"); used by the alert engine for time-windowed thresholds
        :return: dict in the API's site location shape
        """
        return {
            "id": None, "owner": owner, "description": description,
            "streetAddress": street_address, "city": city, "state": state, "country": country,
            "zipCode": zip_code, "timezone": timezone, "lat": float(lat), "lon": float(lon),
        }

    def list(self, client_id: str) -> Optional[List[dict]]:
        """
        List the site locations owned by a client

        :param client_id: the account's client id
        :return: list of site location dicts or None if the request fails
        """
        response = authed_request(self.api_auth, "GET", "sitelocation/list", params={'id': client_id})
        if response.status_code != 200:
            self.logger.error("Failed to list site locations: HTTP {}".format(response.status_code))
            return None
        return response.json()

    def find_by_description(self, client_id: str, description: str) -> Optional[dict]:
        """
        Find a site location by its exact description

        :param client_id: the account's client id
        :param description: the description to match
        :return: the site location dict or None if not found
        """
        locations = self.list(client_id) or []
        for location in locations:
            if location.get('description') == description:
                return location
        return None

    def create(self, location: dict) -> WebServiceBoolean:
        """
        Create a site location. The response does not carry the new id; use find_by_description().

        :param location: site location dict (see build())
        :return: WebServiceBoolean
        """
        response = authed_request(self.api_auth, "POST", "sitelocation/create", json_body=location)
        return ws_bool_from_response(response, "Failed to create site location")

    def update(self, location: dict) -> WebServiceBoolean:
        """
        Update a site location (full document, including id and owner)

        :param location: the site location dict as returned by list()
        :return: WebServiceBoolean
        """
        response = authed_request(self.api_auth, "POST", "sitelocation/update", json_body=location)
        return ws_bool_from_response(response, "Failed to update site location")

    def delete(self, location: dict) -> WebServiceBoolean:
        """
        Delete a site location. WARNING: this cascades — every device and building map
        belonging to the location is deleted with it.

        :param location: dict carrying at least the location's `id` and `owner`
        :return: WebServiceBoolean
        """
        body = {'id': location['id'], 'owner': location['owner']}
        response = authed_request(self.api_auth, "POST", "sitelocation/delete", json_body=body)
        return ws_bool_from_response(response, "Failed to delete site location")

    def print_config(self):
        """Print the API configuration URL"""
        print(self.api_auth.api_config.get_api_url())
