from auth import APIAuth
import requests
import json
from utils import Utils as AUtils


class APIClient:
    """Various methods for Client BO stuff"""
    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self._client_location_view = None

    def get_client_location_view(self, invalidate_cache = False):
        """Get a list of all the locations, sensorlocations, buildingmaps and macs for this account
        :return:
        """
        params = {
            'invalidateCache': 'true' if invalidate_cache is True else 'false'
        }
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        url = self.api_auth.api_config.get_api_url() + "client/locationview"
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            self._client_location_view = json.loads(response.content.decode())
            return self._client_location_view
        else:
            print("Bad response code: " + str(response.status_code))
            return None

    def get_active_locations(self):
        devices_and_locations = self._client_location_view['locationSensorViews']
        return [location for location in devices_and_locations if location['lastSensorReportTime'] != -1]

    def get_active_devices(self, duration: int = (24 * 60 * 60 * 1000)):
        active_locs = self.get_active_locations()
        now = AUtils.now_ms()

        active_devices = []
        for loc in active_locs:
            for device in loc['sensorList']:
                if(now - device['lastReportTime']) < duration:
                    active_devices.append(device)

        return active_devices

    def get_locations(self):
        devices_and_locations = self._client_location_view['locationSensorViews']
        return [location['location'] for location in devices_and_locations]

    def get_location_by_id(self, location_id: str):
        devices_and_locations = self._client_location_view['locationSensorViews']
        for location in devices_and_locations:
            if location['location']['id'] == location_id:
                return location
        return None

    def get_device_by_id(self, device_id: str):
        devices_and_locations = self._client_location_view['locationSensorViews']
        for location in devices_and_locations:
            for device in location['sensorList']:
                if device['id'] == device_id:
                    return device

        return None

