import logging

from api_config import APIConfig
from aretas_client import APIClient
from auth import APIAuth
from entities import Point, ClientLocationView, LocationSensorView
from building_maps import BuildingMapAPIClient
import matplotlib.pyplot as plt
from PIL import Image
import io

import os

os.chdir('../')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def show_image(image_data: bytes, title: str):
    """
    Displays an image from byte data using matplotlib.

    Args:
        image_data (bytes): The image data in bytes.
        title (str): The title to display on the image window.
    """
    image = Image.open(io.BytesIO(image_data))
    plt.imshow(image)
    plt.axis('off')  # Hide axes
    plt.title(title)
    plt.show()


def test_get_map_image():
    """
    Tests the get_map_image method of the BuildingMapAPIClient and displays the image.
    """

    config = APIConfig('config.ini')
    api_auth = APIAuth(config)
    client = APIClient(api_auth)

    # Initialize BuildingMapAPIClient
    building_map_client = BuildingMapAPIClient(api_auth)

    client_location_view: ClientLocationView = client.get_client_location_view()

    location_view :LocationSensorView = client.get_random_location_with_building_map()

    location_id = location_view.location.id
    map_id = location_view.buildingMapList[0].id

    # Test get_map_image
    logger.info(f"Testing get_map_image with location_id={location_id} and map_id={map_id}")
    image_data = building_map_client.get_map_image(location_id, map_id)

    if image_data:
        logger.info("Image retrieved successfully")
        show_image(image_data, "Building Map Image")
    else:
        logger.error("Failed to retrieve the map image.")


def test_get_map_image_with_points():
    """
    Tests the get_map_image_with_points method of the BuildingMapAPIClient and displays the image.
    """
    config = APIConfig('config.ini')
    api_auth = APIAuth(config)
    client = APIClient(api_auth)

    # Initialize BuildingMapAPIClient
    building_map_client = BuildingMapAPIClient(api_auth)

    client_location_view: ClientLocationView = client.get_client_location_view()

    location_view: LocationSensorView = client.get_random_location_with_building_map()

    location_id = location_view.location.id
    map_id = location_view.buildingMapList[0].id

    # Define points to be drawn on the map image
    points = [
        Point(x=100, y=150, z=0),
        Point(x=200, y=250, z=0),
        Point(x=300, y=350, z=0)
    ]

    # Test get_map_image_with_points
    logger.info(
        f"Testing get_map_image_with_points with location_id={location_id}, map_id={map_id}, and points={points}")
    image_data = building_map_client.get_map_image_with_points(location_id, map_id, points)

    if image_data:
        logger.info("Image with points retrieved successfully")
        show_image(image_data, "Building Map Image with Points")
    else:
        logger.error("Failed to retrieve the map image with points.")


if __name__ == "__main__":
    test_get_map_image()
    test_get_map_image_with_points()
