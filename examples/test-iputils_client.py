import logging

from api_config import APIConfig
from auth import APIAuth
from iputils_client import IpUtilAPIClient
import os

os.chdir("../")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    config = APIConfig('config.ini')
    auth = APIAuth(config)
    client = IpUtilAPIClient(auth)

    # Retrieve and print the client's IP address.
    ip = client.get_client_ip()
    if ip:
        # should print your IP
        print("Client IP:", ip)
    else:
        print("Failed to get client IP.")

    # Retrieve and print the client's location.
    location = client.get_client_location()
    if location:
        # should print your approximate lat lng
        print("Client Location (lat, lng):", location)
    else:
        print("Failed to get client location.")
