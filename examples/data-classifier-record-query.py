from auth import *
from aretas_client import *
from data_classifier import DataClassifierCRUD
from data_classifier_record import DataClassifierRecord, DataClassifierRecordCRUD
from entities import SensorDatum
from sensor_data_query import SensorDataQuery
from sensor_type_info import *
import os

os.chdir("../")


class DataClassifierRecordQueryTest:
    def __init__(self):
        """
        we want to fetch the dataclassifier records for a label then query the data
        """
        self.config = APIConfig('config.ini')
        self.auth = APIAuth(self.config)
        self.client = APIClient(self.auth)

        # we will almost always need the sensortypeinfo class
        self.sensor_type_info = APISensorTypeInfo(self.auth)

        # even if we don't need it right away, it's good practice to fetch the client location view
        self.client_location_view: ClientLocationView = self.client.get_client_location_view()

        self.data_classifier_crud = DataClassifierCRUD(self.auth)
        self.data_classifier_record_crud = DataClassifierRecordCRUD(self.auth)

    def fetch_classifier_record_data(self, data_classifier_record: DataClassifierRecord):
        """
        For each mac in assoc_macs, we're going to fetch the data from the API for the particular type
        """
        sdq = SensorDataQuery(self.auth)

        ret = {}

        for mac in data_classifier_record.assoc_macs:
            record_data: list[SensorDatum] = sdq.get_data(
                mac=mac,
                begin=data_classifier_record.get_start_timestamp(),
                end=data_classifier_record.get_end_timestamp(),
                types=data_classifier_record.get_target_types(),
                down_sample=False
            )

            if len(record_data) > 0:
                ret[mac] = record_data

        return ret

    def main(self):
        my_data_classifiers = self.data_classifier_crud.list()

        for data_classifier in my_data_classifiers:
            print("Description: {0} Label: {1} Id: {2}".format(
                data_classifier.get_description(),
                data_classifier.get_label(),
                data_classifier.get_self_id()))

        classifier_id = "d19359107b474399bb4c9a9ff61ef3dd"

        # test listing by data classifier id
        record_list: list[DataClassifierRecord] = self.data_classifier_record_crud.get_by_id(classifier_id)

        if record_list:
            [print(record) for record in record_list]

        record_sample = record_list[0]

        record_data = self.fetch_classifier_record_data(record_sample)


if __name__ == "__main__":
    DataClassifierRecordQueryTest().main()
