import logging
import random
from typing import Optional, List
from auth import APIAuth
import requests
import json
from entities import ClientLocationView, Sensor, Location, LocationSensorView
from utils import Utils as AUtils


class APIClient:
    """Various methods for interacting with the Client BO (Business Object) stuff."""

    def __init__(self, api_auth: APIAuth):
        """
        Initializes the APIClient with the provided API authentication.

        Args:
            api_auth (APIAuth): An instance of APIAuth containing authentication details.
        """
        self.api_auth = api_auth
        self._client_location_view: Optional[ClientLocationView] = None
        self.logger = logging.getLogger(__name__)

    def get_client_location_view(self, invalidate_cache: bool = False) -> Optional[ClientLocationView]:
        """
        Retrieves the Client Location View, which includes all locations, sensor locations, building maps, and MACs.

        Args:
            invalidate_cache (bool): If True, forces the retrieval of fresh data instead of using cached data.

        Returns:
            Optional[ClientLocationView]: An instance of ClientLocationView containing the data, or None if the request failed.
        """
        params = {
            'invalidateCache': 'true' if invalidate_cache else 'false'
        }
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        url = self.api_auth.api_config.get_api_url() + "client/locationview"
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = json.loads(response.content.decode())
            self._client_location_view = ClientLocationView.from_dict(data)
            return self._client_location_view
        else:
            self.logger.warning("Bad response code: " + str(response.status_code))
            return None

    def get_active_locations(self) -> List[LocationSensorView]:
        """
        Retrieves a list of active locations where sensors have reported recently.

        Returns:
            List[LocationSensorView]: A list of LocationSensorView objects representing active locations.
        """
        if not self._client_location_view:
            self.get_client_location_view()
        devices_and_locations = self._client_location_view.locationSensorViews
        return [location for location in devices_and_locations if location.lastSensorReportTime != -1]

    def get_active_devices(self, duration: int = (24 * 60 * 60 * 1000)) -> List[Sensor]:
        """
        Retrieves a list of active devices (sensors) that have reported within the specified duration.

        Args:
            duration (int): The time duration in milliseconds to consider a device as active. Defaults to 24 hours.

        Returns:
            List[Sensor]: A list of Sensor objects representing active devices.
        """
        active_locs = self.get_active_locations()
        now = AUtils.now_ms()

        active_devices = []
        for loc in active_locs:
            for device in loc.sensorList:
                if (now - device.lastReportTime) < duration:
                    active_devices.append(device)

        return active_devices

    def get_locations(self) -> List[Location]:
        """
        Retrieves a list of all locations.

        Returns:
            List[Location]: A list of Location objects.
        """
        if not self._client_location_view:
            self.get_client_location_view()
        devices_and_locations = self._client_location_view.locationSensorViews
        return [location.location for location in devices_and_locations]

    def get_location_by_id(self, location_id: str) -> Optional[LocationSensorView]:
        """
        Retrieves a LocationSensorView by its location ID.

        Args:
            location_id (str): The ID of the location to retrieve.

        Returns:
            Optional[LocationSensorView]: The LocationSensorView object if found, otherwise None.
        """
        if not self._client_location_view:
            self.get_client_location_view()
        devices_and_locations = self._client_location_view.locationSensorViews
        for location in devices_and_locations:
            if location.location.id == location_id:
                return location
        return None

    def get_device_by_id(self, device_id: str) -> Optional[Sensor]:
        """
        Retrieves a Sensor by its device ID.

        Args:
            device_id (str): The ID of the device to retrieve.

        Returns:
            Optional[Sensor]: The Sensor object if found, otherwise None.
        """
        if not self._client_location_view:
            self.get_client_location_view()
        devices_and_locations = self._client_location_view.locationSensorViews
        for location in devices_and_locations:
            for device in location.sensorList:
                if device.id == device_id:
                    return device
        return None

    def get_sensor_by_mac(self, mac: int) -> Optional[Sensor]:
        """
        Searches the ClientLocationView for a Sensor by its MAC address and returns the Sensor object.

        Args:
            mac (int): The MAC address of the sensor to search for.

        Returns:
            Optional[Sensor]: The Sensor object if found, otherwise None.
        """
        if not self._client_location_view:
            self.get_client_location_view()
        devices_and_locations = self._client_location_view.locationSensorViews
        for location in devices_and_locations:
            for sensor in location.sensorList:
                if sensor.mac == mac:
                    return sensor
        self.logger.warning(f"Sensor with MAC {mac} not found.")
        return None

    def get_random_location_with_building_map(self) -> Optional[LocationSensorView]:
        """
        Retrieves a random location that contains at least one BuildingMap.

        Returns:
            Optional[Location]: A Location object with at least one BuildingMap, or None if no such location exists.
        """
        if not self._client_location_view:
            self.get_client_location_view()

        # Filter locations that have at least one building map
        locations_with_building_maps = [
            location_view
            for location_view in self._client_location_view.locationSensorViews
            if location_view.buildingMapList
        ]

        if locations_with_building_maps:
            return random.choice(locations_with_building_maps)
        else:
            self.logger.warning("No locations with BuildingMaps found.")
            return None
