from .auth import APIAuth
from .utils import Utils as AUtils
import requests
from requests.models import PreparedRequest
import json


class SensorDataIngest:

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth

    def send_datum(self, datum, overwritetimestamp=True):
        """
        Send a single sensor data reading to the API
        :param overwritetimestamp:
        :param datum:
        :return:
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
            print("API Response:{0}".format(json_response))
            return True

        else:
            print("Invalid response code:{0}".format(response.status_code))
            return False
        pass

    def send_data(self, data: dict):
        """
        Send several sensor data readings to the API (batch method)
        :param data:
        :return:
        """
        pass
