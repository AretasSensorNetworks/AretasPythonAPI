from auth import *
from aretas_client import *
from data_classifier import DataClassifierCRUD
from data_classifier_record import DataClassifierRecord, DataClassifierRecordCRUD
from sensor_type_info import *
from utils import Utils as AretasUtils, WebServiceBoolean

"""
This example shows how to fetch labelled data from the API
"""

config = APIConfig('../config.ini')
auth = APIAuth(config)
client = APIClient(auth)

# we will almost always need the sensortypeinfo class
sensor_type_info = APISensorTypeInfo(auth)

# even if we don't need it right away, it's good practice to fetch the client location view
client_location_view = client.get_client_location_view()

data_classifier_crud = DataClassifierCRUD(auth)
data_classifier_record_crud = DataClassifierRecordCRUD(auth)

my_data_classifiers = data_classifier_crud.list()

for data_classifier in my_data_classifiers:
    print("Description: {0} Label: {1} Id: {2}".format(
        data_classifier.get_description(),
        data_classifier.get_label(),
        data_classifier.get_self_id()))

test_classifier_id = "57d4198ee732443ba722df31a266b4a3"

req_types = [1, 2, 3, 4]
end_timestamp = AretasUtils.now_ms()
start_timestamp = end_timestamp - (5 * 60 * 1000)  # 5 minutes ago
record = DataClassifierRecord(
    data_classifier_id=test_classifier_id,
    start_timestamp=start_timestamp,
    end_timestamp=end_timestamp,
    assoc_macs=[1234567890, 2345678910],
    target_types=req_types,
    regression_value=-1.0
)

# test saving
ws_resp: WebServiceBoolean = data_classifier_record_crud.save(record)
print(ws_resp)

# test listing by data classifier id
record_list: list[DataClassifierRecord] = data_classifier_record_crud.get_by_id(test_classifier_id)
[print(record) for record in record_list]
