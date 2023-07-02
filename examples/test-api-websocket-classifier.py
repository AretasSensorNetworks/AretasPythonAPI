import time

from auth import *
from aretas_client import *
from data_classifier import DataClassifierCRUD
from labelled_data_query import LabelledDataQuery
from sensor_type_info import *
from utils import Utils as AUtils
from client_websocket import SensorDataWebsocket

import pandas as pd

"""
This is a template for the type of workflow you need for multivariate sensor data classifiers

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

# list the classifiers in this account
for data_classifier in data_classifiers:
    print("Description: {0} Label: {1} Id: {2}".format(
        data_classifier['description'],
        data_classifier['label'],
        data_classifier['id']))

# fetch the labeled data for each classifier of interest
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

# unless you use the area usage hints and building map features in your model, it's probably best to drop them
df_devices.drop(["areaUsageHints", "buildingMapId"], axis=1, inplace=True)
df_devices[:len(df_devices)]

"""

In our other examples, this is where training and model validation occurs

Once we've trained, validated and are ready to test a model with streaming data, 

we can pick a device and start aligning the multivariate types and one we are ready, 

we trigger the callback to do a prediction (in this case, a mock stub)

"""

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
    # we get the single row data frame and call the prediction (depending on what the model expects for input)
    if AUtils.is_full_and_aligned(tmp):

        # get the dataframe then massage it
        df_datum = AUtils.get_datum_df(tmp, sensor_type_info)
        do_predict_one(df_datum)


# we define the websocket stream the deviceids/macs we want to observe and the callback for message processing
stream = SensorDataWebsocket(auth, location_id, [mac], process_message)
stream.start()

# in this dummy template, we just wait for 30 seconds then stop the stream...
time.sleep(30)
print("Stopping")
stream.stop()
