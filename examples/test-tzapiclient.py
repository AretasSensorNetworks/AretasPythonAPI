from auth import *
from aretas_client import *
from tzapiclient import TimeZoneAPIClient
import os

os.chdir("../")

'''
Test the lat/lng to timezone API endpoint
'''

if __name__ == '__main__':
    config = APIConfig('config.ini')
    auth = APIAuth(config)

    # Example usage:
    logging.basicConfig(level=logging.INFO)
    # Replace with your actual API base URL
    client = TimeZoneAPIClient(auth)
    # Example coordinates (latitude, longitude)
    timezone = client.get_timezone_id(37.7749, -122.4194)
    if timezone:
        # should emit: Timezone for coordinates: America/Los_Angeles
        print(f"Timezone for coordinates: {timezone}")
    else:
        print("Timezone not found.")
