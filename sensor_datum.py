class SensorDatum:
    """
    The contract for a sensor data point from the API
    """
    def __init__(self, mac: int = None, data_type: int = None, timestamp: int = None, data: float = None):
        self.__mac = mac
        self.__data_type = data_type
        self.__timestamp = timestamp
        self.__data = data

    def __repr__(self):
        return "MAC: {} Type:{} Timestamp:{} Data:{}".format(
            self.get_mac(),
            self.get_type(),
            self.get_timestamp(),
            self.get_data()
        )

    def set_mac(self, mac:int):
        self.__mac = mac

    def get_mac(self)->int:
        return self.__mac

    def set_type(self, data_type:int):
        self.__data_type = data_type

    def get_type(self)->int:
        return self.__data_type

    def set_timestamp(self, timestamp:int):
        self.__timestamp = timestamp

    def get_timestamp(self)->int:
        return self.__timestamp

    def set_data(self, data:float):
        self.__data = data

    def get_data(self)->float:
        return self.get_data()
