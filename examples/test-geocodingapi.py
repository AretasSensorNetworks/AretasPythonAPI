from auth import *
from aretas_client import *
from geocodingclient import GeocodingAPIClient
import os
from auth import APIAuth
os.chdir("../")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    config = APIConfig('config.ini')
    auth = APIAuth(config)

    client = GeocodingAPIClient(auth)

    # Example usage: Geocode a location string
    location_string = "1600 Amphitheatre Parkway, Mountain View, CA"
    coordinates = client.get_client_location(location_string)
    if coordinates:
        # should emit: Coordinates for '1600 Amphitheatre Parkway, Mountain View, CA': (37.42263, -122.08467)
        print(f"Coordinates for '{location_string}': {coordinates}")
    else:
        print("Geocoding failed.")
