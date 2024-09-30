import logging
from typing import Optional, List
import requests
import json
from auth import APIAuth
from entities import BuildingMap, Point


class BuildingMapAPIClient:
    """Methods for interacting with the Building Map functionality."""

    def __init__(self, api_auth: APIAuth):
        """
        Initializes the BuildingMapAPIClient with the provided API authentication.

        Args:
            api_auth (APIAuth): An instance of APIAuth containing authentication details.
        """
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def create_building_map(self, building_map: BuildingMap) -> bool:
        """
        Creates a new BuildingMap.

        Args:
            building_map (BuildingMap): The building map to create.

        Returns:
            bool: True if creation is successful, False otherwise.
        """
        url = self.api_auth.api_config.get_api_url() + "buildingmaps/create"
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        response = requests.post(url, headers=headers, json=building_map.to_dict())

        if response.status_code == 200:
            data = json.loads(response.content.decode())
            return data.get("success", False)
        else:
            self.logger.warning("Failed to create building map: " + str(response.status_code))
            return False

    def update_building_map(self, building_map: BuildingMap) -> bool:
        """
        Updates an existing BuildingMap.

        Args:
            building_map (BuildingMap): The building map to update.

        Returns:
            bool: True if update is successful, False otherwise.
        """
        url = self.api_auth.api_config.get_api_url() + "buildingmaps/update"
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        response = requests.post(url, headers=headers, json=building_map.to_dict())

        if response.status_code == 200:
            data = json.loads(response.content.decode())
            return data.get("success", False)
        else:
            self.logger.warning("Failed to update building map: " + str(response.status_code))
            return False

    def delete_building_map(self, building_map_id: str) -> bool:
        """
        Deletes a BuildingMap by ID.

        Args:
            building_map_id (str): The ID of the building map to delete.

        Returns:
            bool: True if deletion is successful, False otherwise.
        """
        url = self.api_auth.api_config.get_api_url() + f"buildingmaps/delete?id={building_map_id}"
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = json.loads(response.content.decode())
            return data.get("success", False)
        else:
            self.logger.warning("Failed to delete building map: " + str(response.status_code))
            return False

    def list_building_maps_by_location(self, location_id: str) -> Optional[List[BuildingMap]]:
        """
        Lists all BuildingMaps by Location ID.

        Args:
            location_id (str): The ID of the location.

        Returns:
            Optional[List[BuildingMap]]: A list of BuildingMap objects, or None if the request failed.
        """
        url = self.api_auth.api_config.get_api_url() + f"buildingmaps/list?locationId={location_id}"
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = json.loads(response.content.decode())
            return [BuildingMap.from_dict(bm) for bm in data]
        else:
            self.logger.warning("Failed to list building maps: " + str(response.status_code))
            return None

    def get_map_image(self, location_id: str, map_id: str) -> Optional[bytes]:
        """
        Retrieves a building map image by location and map ID.

        Args:
            location_id (str): The ID of the location.
            map_id (str): The ID of the map.

        Returns:
            Optional[bytes]: The image data as bytes, or None if the request failed.
        """
        url = (self.api_auth.api_config.get_api_url() +
               f"buildingmaps/getimage?bearerToken={self.api_auth.get_token()}&locationId={location_id}&mapId={map_id}")

        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            return response.content
        else:
            self.logger.warning("Failed to get map image: " + str(response.status_code))
            return None

    def get_map_image_with_points(self, location_id: str, map_id: str, points: List[Point]) -> Optional[bytes]:
        """
        Retrieves a building map image with points drawn on it.

        Args:
            location_id (str): The ID of the location.
            map_id (str): The ID of the map.
            points (List[Point]): A list of points to draw on the image.

        Returns:
            Optional[bytes]: The image data as bytes, or None if the request failed.
        """
        url = self.api_auth.api_config.get_api_url() + f"buildingmaps/getimagewithpoints?locationId={location_id}&mapId={map_id}"

        print(url)

        headers = {
            "Authorization": "Bearer " + self.api_auth.get_token(),
            "Content-Type": "application/json"
        }

        response = requests.post(url, headers=headers, json=[point.to_dict() for point in points])

        if response.status_code == 200:
            return response.content
        else:
            self.logger.warning("Failed to get map image with points: " + str(response.status_code))
            return None
