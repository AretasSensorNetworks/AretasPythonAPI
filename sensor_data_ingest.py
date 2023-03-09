import logging

from .auth import APIAuth
from .utils import Utils as AUtils
import requests
from requests.models import PreparedRequest
import json


class SensorDataIngest:
    """
    Class for sending data / sensor messages to the API
    currently supports single datums
    to add:
        - batch messages
        - extended types (PCM, thermal, etc.)
        - extended types batch
    """

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def send_datum_auth_check(self, datum: dict, overwritetimestamp: bool = True, n_retries: int = 2) -> bool:
        """
        Send a datum using automatic auth token refresh
        """
        ts = AUtils.now_ms()

        if overwritetimestamp is False:
            ts = datum['timestamp']

        mac = int(datum['mac'])
        sensor_type = int(datum['type'])
        sensor_data = float(datum['data'])

        url = self.api_auth.api_config.get_api_url() + "ingest/secured/std/get"
        params = {
            't': ts,
            'm': mac,
            'st': sensor_type,
            'd': sensor_data
        }

        req = PreparedRequest()
        req.prepare_url(url, params)

        auth_token = self.api_auth.get_token()
        if auth_token is None:
            """
            This isn't ideal, but we'll let it slide for now until we decide what to do when a user has provided
            invalid access credentials or the API is malfunctioning
            """
            auth_token = ""

        headers = {"Authorization": "Bearer " + auth_token, "X-AIR-Token": str(mac)}

        response = requests.get(req.url, headers=headers)

        if response.status_code == 200:

            json_response = json.loads(response.content.decode())
            self.logger.info("API Response:{0}".format(json_response))
            return True

        elif (response.status_code == 401 or response.status_code == 403) and (n_retries > 0):
            self.logger.info("Response [{}], refreshing authtoken".format(response.status_code))
            n_retries = n_retries - 1
            self.api_auth.refresh_token()
            return self.send_datum_auth_check(datum, overwritetimestamp, n_retries)
        else:
            self.logger.error("Could not send datum to API. Invalid response code:{}".format(response.status_code))
            return False

    def send_datum(self, datum: dict, overwritetimestamp: bool = True) -> bool:
        """
        Send a datum if you know you have a valid auth token and/or are manually
        managing token refresh
        """
        ts = AUtils.now_ms()

        if overwritetimestamp is False:
            ts = datum['timestamp']

        mac = int(datum['mac'])
        sensor_type = int(datum['type'])
        sensor_data = float(datum['data'])

        url = self.api_auth.api_config.get_api_url() + "ingest/secured/std/get"
        params = {
            't': ts,
            'm': mac,
            'st': sensor_type,
            'd': sensor_data
        }

        req = PreparedRequest()
        req.prepare_url(url, params)

        headers = {"Authorization": "Bearer " + self.api_auth.get_token(), "X-AIR-Token": str(mac)}

        response = requests.get(req.url, headers=headers)

        if response.status_code == 200:

            json_response = json.loads(response.content.decode())
            self.logger.info("API Response:{0}".format(json_response))
            return True

        else:
            self.logger.error("Invalid response code:{0}".format(response.status_code))
            return False
        pass

    def send_data(self, data: dict):
        """
        Send several sensor data readings to the API (batch method)
        :param data:
        :return:
        """
        pass
