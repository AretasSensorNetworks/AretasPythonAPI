from .auth import APIAuth
import requests
from requests.models import PreparedRequest
import json


class SensorDataQuery:

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth

    def refresh_token(self):
        """Refresh the API token"""
        self.api_auth.refresh_token()

    def get_data(self, mac: int,
                 begin: int,
                 end: int,
                 types: list = [],
                 limit: int = 1000000,
                 down_sample: bool = False,
                 threshold: int = 300,
                 moving_average: bool = False,
                 window_size: int = 10,
                 moving_average_type: int = 0,
                 offset_data: bool = False,
                 requested_indexes: list = [],
                 arr_ieq_assumptions: list = [],
                 iq_range: float = -1.0,
                 interpolate_data: bool = False,
                 interpolate_timestep: int = 120000,
                 interpolate_type: int = 0
                 ):
        """This is the main sensor data query end point, most other data query
        endpoints are rarely used or may ultimately be deprecated
        :param mac - the MAC address of the device being queried
        :param types - zero, one or many sensor types. If no types are specified,
         all the types belonging to the MAC are returned
        :param begin - the begin / start timestamp in unix epoch milliseconds
        (GMT)
        :param end - the end timestamp in unix epoch milliseconds (GMT)
        :param limit - the query size limit, defaults to 2,000,000 records
        :param down_sample - downsample - whether or not to downsample the data
        :param threshold - the threshold value for the downsampler
        :param moving_average - movingAverage - whether or not to enable moving average
        :param window_size - windowSize - the window size for the moving average
        :param moving_average_type - movingAverageType - the moving average type
        :param offset_data - offsetData - whether or not to offset the query time from when the
        sensor last reported
        :param requested_indexes - requestedIndexes - any IEQ indexes requested
        :param arr_ieq_assumptions - arrIEQAssumptions - an array of IEQ assumptions for the indexes
        :param iq_range - iqRange - whether or not to filter outliers, -1 (default) is
        disabled, otherwise specify an interquartile range
        :param interpolate_data - interpolateData - whether or not to interpolate the data
        :param interpolate_timestep - interpolateTimestep - the interpolation timestep
        :param interpolate_type - interpolateType - the interpolation type (akima, linear_


        :return:
        """
        url = self.api_auth.api_config.get_api_url() + "sensordata/byrange"
        params = {
            'mac': mac,
            'begin': begin,
            'end': end,
            'limit': limit,
            'offsetData': offset_data
        }

        if len(types) > 0:
            params['types'] = types

        if down_sample:
            params['downsample'] = down_sample
            params['threshold'] = threshold

        if moving_average:
            params['movingAverage'] = moving_average
            params['windowSize'] = window_size
            params['movingAverageType'] = moving_average_type

        if iq_range > 0:
            params['iqRange'] = iq_range

        if len(requested_indexes) > 0:
            params['requestedIndexes'] = requested_indexes
            params['arrIEQAssumptions'] = arr_ieq_assumptions

        if interpolate_data:
            params['interpolateData'] = interpolate_data
            params['interpolateTimestep'] = interpolate_timestep
            params['interpolateType'] = interpolate_type

        req = PreparedRequest()
        req.prepare_url(url, params)
        print(req.url)

        headers = {"Authorization": "Bearer " + self.api_auth.get_token(), "X-AIR-Token": str(mac)}

        response = requests.get(req.url, headers=headers)

        if response.status_code == 200:

            sensor_data = []

            json_response = json.loads(response.content.decode())

            for sensorDatum in json_response:
                datum = {'timestamp': datetime.utcfromtimestamp(sensorDatum.get("timestamp") / 1000), 'data': sensorDatum.get("data")}

                sensor_data.append(datum)

            return sensor_data

        else:
            print("Invalid response code:")
            print(response.status_code)
            print('\n')
            return None

    def print_config(self):
        print(self.api_auth.api_config.get_api_url())
