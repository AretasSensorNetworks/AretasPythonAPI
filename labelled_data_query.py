import logging

from auth import APIAuth
import requests
from requests import PreparedRequest
import json


class LabelledDataQuery:
    """
    This is a class for interacting with the labelled data service in the Aretas API
    """
    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def get_labelled_data(self, classifier_id: str,
                          restrict_types: bool = True,
                          down_sample: bool = False,
                          threshold: int = 300,
                          moving_average: bool = False,
                          window_size: int = 10,
                          moving_average_type: int = 0,
                          iq_range: float = -1.0,
                          interpolate_data: bool = False,
                          interpolate_timestep: int = 30000,
                          interpolate_type: int = 0,
                          record_limit: int = 100000000,
                          max_time_align_diff: int = 100000,
                          ):
        """
        Get the column ordered labelled data from the API for this classifier id.
         :param classifier_id - classifierId the classifier ID (UUID from the BO Object)
         :param restrict_types - restrictTypes whether to restrict the returned data to the types specified in the classifier definition
         :param down_sample - downsample - whether to downsample the data
         :param threshold - threshold - the threshold for downsampling (essentially the number of records to downsample to)
         :param moving_average - movingAverage - whether to enable moving average
         :param window_size - windowSize - the moving average window size
         :param moving_average_type - movingAverageType - the type of moving average (see API docs)
         :param iq_range - iqRange - the interquartile range for interquartile filtering. -1 disables (API default)
         :param interpolate_data - interpolateData - whether to interpolate the data
         :param interpolate_timestep - interpolateTimestep - the interpolation timestep
         :param interpolate_type - interpolateType - the interpolation type (0 = Akima, 1 = Linear, etc)
         :param record_limit - recordLimit - specify the record limit for the query (API defaults are very large)
         :param max_time_align_diff - maxTimeAlignDiff - this is an important setting for column ordered results, since
         the API does not receive packets from the same MAC at the exact same millisecond timestamp, the various types
         have different timestamps - in fact, some columns (sensor types) might miss an interval. Columns are therefore
         always "full and aligned", meaning all the timestamps from each value in the column must be within
         max_time_align_diff in this way, we do not return columns with NaN or empty values. If you find a columns is
          missing too many values, you can simply interpolate first.
        :return:
        """

        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        base_url = self.api_auth.api_config.get_api_url() + "labelleddata/exportjson"

        params = {
            'classifierId': classifier_id,
            'restrict_types': restrict_types,
            'maxTimeAlignDiff': max_time_align_diff,
            'recordLimit': record_limit,
        }

        if down_sample:
            params['downsample'] = down_sample
            params['threshold'] = threshold

        if moving_average:
            params['movingAverage'] = moving_average
            params['windowSize'] = window_size
            params['movingAverageType'] = moving_average_type

        if iq_range > 0:
            params['iqRange'] = iq_range

        if interpolate_data:
            params['interpolateData'] = interpolate_data
            params['interpolateTimestep'] = interpolate_timestep
            params['interpolateType'] = interpolate_type

        req = PreparedRequest()
        req.prepare_url(base_url, params)
        # print(req.url)

        response = requests.get(req.url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content.decode())
            return response_content
        else:
            self.logger.warning("Bad response code: " + str(response.status_code))
            return None

    @staticmethod
    def reshape_dataset(dataset: dict, can_cols: list):
        """
        We are building a list of rows for pandas, numpy, etc. however, we need to account for missing values
        As such, we should either discard the datum or let pandas/numpy fill it in for us
        the canonical definition of 'what columns belong in the rows' should be defined beforehand
        """
        count = 0
        data = []
        for datum in dataset:
            row = []
            timestamp = datum['key']
            row.append(int(timestamp))
            for sensor_type in can_cols:
                data_dict_keyset = [int(i) for i in datum['value'].keys()]
                if sensor_type in data_dict_keyset:
                    data_value = float(datum['value'][str(sensor_type)])
                else:
                    data_value = float("NaN")

                count += 1
                row.append(data_value)

            data.append(row)

        return data

    @staticmethod
    def get_columns(dataset: dict) -> list:
        """
        get the distinct columns from the dataset to use for indexing
        (these columns will be passed to reshape_dataset)
        """
        cols = set[int]()
        for datum in dataset:
            dict_data = datum['value']
            sensor_types = [int(i) for i in dict_data.keys()]
            for k in sensor_types:
                cols.add(k)

        return sorted(cols)

