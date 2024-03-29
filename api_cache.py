import logging

from auth import APIAuth
import requests
import json


class APICache:
    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def get_latest_data(self, macs: list):

        base_url = self.api_auth.api_config.get_api_url() + "sensorreport/latest"

        headers = {
            "Authorization": "Bearer " + self.api_auth.get_token(),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(base_url, headers=headers, data=json.dumps(macs))

        if response.status_code == 200:

            json_response = json.loads(response.content.decode())

            return json_response

        else:
            self.logger.warning("Invalid response code:".format(response.status_code))
            return None



