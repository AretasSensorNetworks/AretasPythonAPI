import time
import datetime

from sensor_type_info import APISensorTypeInfo
import pandas as pd


class Utils:
    def __init__(self):
        pass

    @staticmethod
    def now_ms():
        """
        Utility function to get the time in milliseconds
        :return:
        """
        return int(time.time() * 1000)

    @staticmethod
    def fn_date_conv(x):
        """
        This allows you to convert a datetime string into a unix epoch timestamp
        for querying Aretas backend
        Note that everything is converted based on your local TZ
        :param x:
        :return: unix epoch timestamp
        """
        dt = datetime.datetime.strptime(x, '%m/%d/%Y %H:%M:%S')
        return int(dt.timestamp() * 1000)

    @staticmethod
    def convert_ts(ts):
        """
        Convert a unix timestamp in milliseconds to a timestamp string (UTC)
        :param ts:
        :return:
        """
        ts = ts / 1000
        return str(datetime.datetime.utcfromtimestamp(int(ts)).strftime('%d-%m-%Y %H:%M:%S'))

    @staticmethod
    def get_dict_template(init_keys):
        """
        returns a dict containing keys specified by init_keys, but each value set to None
        :param init_keys:
        :return:
        """
        ret = dict()

        for i in init_keys:
            if i not in ret.keys():
                ret[i] = None

        return ret

    # we construct an object to hold the *required* sensor data
    # when it is "full" and time-aligned within a certain threshold, we call the model
    @staticmethod
    def is_full(data):
        """Ensure we have all the required types - the data dict has been preinitialized"""
        for sensor_type in data:
            if data[sensor_type] is None:
                return False
        return True

    @staticmethod
    def is_aligned(data, max_timestamp_diff:int = 30000):
        """ensure that all of the datums in the dict are within max_timestamp_diff of one another"""
        timestamps = []
        for sensor_type in data:
            timestamps.append(data[sensor_type]['timestamp'])

        min_ = min(timestamps)
        max_ = max(timestamps)
        diff = max_ - min_
        if abs(diff) <= max_timestamp_diff:
            return True
        return False

    @staticmethod
    def is_full_and_aligned(data):
        """
        Call is_aligned only after is_full passes since is_aligned tries to access the data[type]['timestamp'] index
        and will by stymied when it is set to None by default.
        There's also no point in checking it if the dict isn't full
        :param data:
        :return:
        """
        is_aligned = False

        is_full = Utils.is_full(data)
        if is_full:
            is_aligned = Utils.is_aligned(data)

        return is_full and is_aligned

    @staticmethod
    def add_sensor_datum(sensor_datum: dict, mac: int, required_types, ingest_sensor_data: dict):
        """
        Add a sensor_datum contents to the target dict only if
        the type is already in required_types and the mac matches
        :param sensor_datum:
        :param mac:
        :param required_types:
        :param ingest_sensor_data:
        :return:
        """
        sensor_type = str(sensor_datum['type'])
        datum_mac = sensor_datum['mac']
        timestamp = sensor_datum['timestamp']
        sensor_data = sensor_datum['data']

        # ensure it matches our mac
        if datum_mac == mac:
            # ensure it's one of our required sensor types
            if sensor_type in required_types:
                ingest_sensor_data[sensor_type] = {
                    'timestamp': timestamp,
                    'data': sensor_data
                }

        return ingest_sensor_data

    @staticmethod
    def get_datum_df(data, sensor_type_info: APISensorTypeInfo):
        """
            Get a structured dataframe for a single "row" of data
            steps:
            1. Get an average timestamp for the timestamp column
            2. reshape the data into a matrix with one row [[col1, col2, col3, ...]]
            3. prepend the timestamp
            4. create a dataframe and set the columns
        """
        timestamp_acc = 0
        for sensor_type in data:
            timestamp_acc += data[sensor_type]['timestamp']
        timestamp_avg = int(timestamp_acc/len(data))

        # the data comes out of the API sorted by key (sensortype) ascending
        sorted_data = dict(sorted(data.items()))

        sensor_types = [i for i in sorted_data]

        sensor_data = [sorted_data[i]['data'] for i in sorted_data]

        timestamp_str = Utils.convert_ts(timestamp_avg)
        sensor_data.insert(0, timestamp_str)

        sensor_labels = sensor_type_info.get_labels(sensor_types)
        sensor_labels.insert(0, 'timestamp')

        df_datum = pd.DataFrame([sensor_data], columns=sensor_labels)

        return df_datum


