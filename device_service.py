import logging
from typing import List, Optional

from auth import APIAuth
from entities import WebServiceBoolean
from rest_helper import authed_request, ws_bool_from_response


class DeviceService:
    """
    Create, list, update and remove devices (the API calls them sensor locations).

    A device's `owner` is the id of the site location it belongs to; `mac` is a decimal
    integer. MACs are unique platform-wide — creating a device with a MAC that already
    exists (and is not shared) fails with the API's duplicate-MAC error. The API never
    returns the id of a newly created device, so `create()` is normally followed by
    `find_by_mac()`.
    """

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def build(owner: str, mac: int, description: str, lat: float = 0.0, lon: float = 0.0,
              notify_if_down: bool = False, down_interval_ms: int = 24 * 3600 * 1000,
              area_type: int = 0, is_shared_public: bool = False) -> dict:
        """
        Build a device document ready for create()

        :param owner: the id of the site location the device belongs to
        :param mac: the device MAC as a decimal integer
        :param description: display name of the device
        :param lat: latitude
        :param lon: longitude
        :param notify_if_down: whether the platform should raise down notifications for this device
        :param down_interval_ms: how long the device may stay silent before it counts as down (ms)
        :param area_type: area type code
        :param is_shared_public: whether the device's data is publicly shared
        :return: dict in the API's device shape
        """
        return {
            "id": None, "owner": owner, "description": description, "mac": int(mac),
            "lat": float(lat), "lon": float(lon), "areaType": int(area_type),
            "notifyIfDown": bool(notify_if_down), "downInterval": int(down_interval_ms),
            "isSharedPublic": bool(is_shared_public), "buildingMapId": "", "imgMapX": -1, "imgMapY": -1,
            "areaUsageHints": {"floorArea": 0, "ceilingHeight": 0, "hasPeople": 0,
                               "occupantCountHint": 0, "hasOpeningWindows": 0},
        }

    def list(self, location_id: str) -> Optional[List[dict]]:
        """
        List the devices belonging to a site location

        :param location_id: the site location id
        :return: list of device dicts or None if the request fails
        """
        response = authed_request(self.api_auth, "GET", "sensorlocation/list", params={'id': location_id})
        if response.status_code != 200:
            self.logger.error("Failed to list devices: HTTP {}".format(response.status_code))
            return None
        return response.json()

    def find_by_mac(self, location_id: str, mac: int) -> Optional[dict]:
        """
        Find a device in a site location by MAC

        :param location_id: the site location id
        :param mac: the device MAC
        :return: the device dict or None if not found
        """
        for device in self.list(location_id) or []:
            if int(device.get('mac', -1)) == int(mac):
                return device
        return None

    def create(self, device: dict) -> WebServiceBoolean:
        """
        Create a device. The response does not carry the new id; use find_by_mac().

        :param device: device dict (see build())
        :return: WebServiceBoolean; a duplicate MAC yields booleanResponse False with the API's error message
        """
        response = authed_request(self.api_auth, "POST", "sensorlocation/create", json_body=device)
        return ws_bool_from_response(response, "Failed to create device")

    def update(self, device: dict) -> WebServiceBoolean:
        """
        Update a device (full document, including id and owner)

        :param device: the device dict as returned by list()
        :return: WebServiceBoolean
        """
        response = authed_request(self.api_auth, "POST", "sensorlocation/update", json_body=device)
        return ws_bool_from_response(response, "Failed to update device")

    def remove(self, device: dict) -> WebServiceBoolean:
        """
        Remove a device

        :param device: the device dict as returned by list() (id and owner are required)
        :return: WebServiceBoolean
        """
        response = authed_request(self.api_auth, "POST", "sensorlocation/remove", json_body=device)
        return ws_bool_from_response(response, "Failed to remove device")

    def print_config(self):
        """Print the API configuration URL"""
        print(self.api_auth.api_config.get_api_url())
