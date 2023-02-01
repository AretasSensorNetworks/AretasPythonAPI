from .auth import APIAuth
import requests
import json


class APISensorTypeInfo:
    """
    Helper class to fetch all of the Aretas sensor type info metadata
    Includes helper functions to map type units to SensorTypeInfo classes
    """
    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.sensor_type_metadata = None
        self.refresh_sensor_type_into()

    def refresh_sensor_type_into(self):
        """Fetch all the sensor type metadata"""
        base_url = self.api_auth.api_config.get_api_url() + "sensortype/list"

        headers = {
            "Accept": "application/json"
        }

        response = requests.get(base_url, headers=headers)

        if response.status_code == 200:

            self.sensor_type_metadata = json.loads(response.content.decode())

        else:
            print("Invalid response code:")
            print(response.status_code)
            print('\n')
            return None

    def get_sensor_type_metadata(self, sensor_type: int):
        """ get the sensor type metadata object for that sensor type if one exists
            :param sensor_type - the integer sensor type
        """
        for sensor_type_info in self.sensor_type_metadata:
            if int(sensor_type_info['type']) == sensor_type:
                return sensor_type_info

        return None

    def get_labels(self, types: list):
        """ get a list of labels for a list of sensor types if available, otherwise return the type int as a str
            :param types - a list of sensor types (integers)
        """
        ret = []
        for s_type in types:
            s_type_obj = self.get_sensor_type_metadata(int(s_type))
            if s_type_obj is not None:
                ret.append(s_type_obj['label'] + " " + s_type_obj['units'])
            else:
                ret.append(str(s_type))
        return ret
