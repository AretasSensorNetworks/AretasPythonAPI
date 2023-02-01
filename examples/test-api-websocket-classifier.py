import sys
import time
sys.path.append('C:\\Users\\aretas\\Documents\\GitHub\\APIExamples\\python\\')
print(sys.path)

from aretasapiclient.api_config import *
from aretasapiclient.sensor_data_query import *
from aretasapiclient.auth import *
from aretasapiclient.aretas_client import *
from aretasapiclient.data_classifier import DataClassifierCRUD
from aretasapiclient.labelled_data_query import LabelledDataQuery
from aretasapiclient.sensor_type_info import *
from aretasapiclient.utils import Utils as AUtils
from aretasapiclient.client_websocket import SensorDataWebsocket

import pandas as pd

"""

To test the various ensemble methods for the general classifier services we
copy many of the workflow steps for getting a classifier, getting the labeled data, then stream processing

"""
config = APIConfig()
auth = APIAuth(config)
client = APIClient(auth)

# we will almost always need the sensortypeinfo class
sensor_type_info = APISensorTypeInfo(auth)

# even if we don't need it right away, it's good practice to fetch the client location view
client_location_view = client.get_client_location_view()

data_classifier_crud = DataClassifierCRUD(auth)
labelled_data_query = LabelledDataQuery(auth)

data_classifiers = data_classifier_crud.list()

for data_classifier in data_classifiers:
    print("Description: {0} Label: {1} Id: {2}".format(
        data_classifier['description'],
        data_classifier['label'],
        data_classifier['id']))

labelled_data_occupied = labelled_data_query.get_labelled_data("4f99014965334c5384faebfbe65231fd")
labelled_data_unoccupied = labelled_data_query.get_labelled_data("ba831fd52d2041ae83c4eeffb27c1426")

# we extract the column names for the table using the sensor type label from the metadata service
first_row_keys = [key for key in labelled_data_occupied[0]['value']]

# let's preserve the types for later use
classifier_sensor_types = first_row_keys

# get the labels from the sensor metadata service
columns = sensor_type_info.get_labels(first_row_keys)

# prepend the timestamp column label
columns.insert(0, 'timestamp')
print(columns)

# we stored the required types earlier in classifier_sensor_types
# get a dict templated with the required types as keys with None placeholder values
ingest_sensor_data = AUtils.get_dict_template(classifier_sensor_types)

active_devices = client.get_active_devices()
df_devices = pd.DataFrame(active_devices)
# drop a few messy columns to clean up the view
df_devices.drop(["areaUsageHints", "buildingMapId"], axis=1, inplace=True)
df_devices[:len(df_devices)]

# get the gym monitor
gym_device = df_devices.loc[df_devices["description"] == "Gym"]

# the owner of the device is the locationid and let's also get the mac
mac = gym_device.iloc[0]["mac"]
location_id = gym_device.iloc[0]["owner"]
print(mac, location_id)


def do_predict_one(data_df):
    print(data_df.head(1))
    pass


def process_message(sensor_datum):
    global ingest_sensor_data
    print(sensor_datum)
    # add the datum to the dict only after meeting numerous conditions
    tmp = AUtils.add_sensor_datum(sensor_datum, mac, classifier_sensor_types, ingest_sensor_data)

    # if the ingest_sensor_data dict now has all of our required data and is time_aligned
    # we get the single row data frame and call the prediction
    if AUtils.is_full_and_aligned(tmp):

        # get the dataframe then massage it
        df_datum = AUtils.get_datum_df(tmp, sensor_type_info)
        do_predict_one(df_datum)


stream = SensorDataWebsocket(auth, location_id, [mac], process_message)
stream.start()

time.sleep(30)
print("Stopping")
stream.stop()
