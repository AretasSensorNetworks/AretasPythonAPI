import sys
sys.path.append('C:\\Users\\aretas\\Documents\\GitHub\\APIExamples\\python\\')
print(sys.path)

from aretasapiclient.api_config import *
from aretasapiclient.sensor_data_query import *
from aretasapiclient.auth import *
from aretasapiclient.aretas_client import *
from aretasapiclient.data_classifier import DataClassifierCRUD
from aretasapiclient.labelled_data_query import LabelledDataQuery
from aretasapiclient.sensor_type_info import *

import pandas as pd
from sklearn.utils import shuffle


config = APIConfig()
auth = APIAuth(config)
client = APIClient(auth)

# we will almost always need the sensortypeinfo class
sensor_type_info = APISensorTypeInfo(auth)

# even if we don't need it right away, it's good practice to fetch the client location view
client_location_view = client.get_client_location_view()

data_classifier_crud = DataClassifierCRUD(auth)
labelled_data_query = LabelledDataQuery(auth)
my_data_classifiers = data_classifier_crud.list()

for data_classifier in my_data_classifiers:
    print("Description: {0} Label: {1} Id: {2}".format(
        data_classifier['description'],
        data_classifier['label'],
        data_classifier['id']))

labelled_data_occupied = labelled_data_query.get_labelled_data("4f99014965334c5384faebfbe65231fd")
labelled_data_unoccupied = labelled_data_query.get_labelled_data("ba831fd52d2041ae83c4eeffb27c1426")

"""
We get a list of dicts where the 'key' is the timestamp and the 'value' is a dict of columns 
(each column is a dict indexed by type):
[
    {
        'key': 1546581659276, 
        'value': {
            '32': 0.0, 
            '33': 0.0, 
            '34': 0.0, 
            '181': 424.0, 
            '246': 11.41, 
            '248': 69.23}
    },{
        'key': 1546581751425, 
        'value': {
            '32': 0.0, 
            '33': 0.0, 
            '34': 0.0, 
            '181': 432.0, 
            '246': 11.43, 
            '248': 69.42
    }
]
"""
print(labelled_data_occupied)
# extract the column labels from the first
first_row_keys = [key for key in labelled_data_occupied[0]['value']]
columns = sensor_type_info.get_labels(first_row_keys)
columns.insert(0, 'timestamp')
print(columns)


def reshape_dataset(dataset):
    data = []
    for datum in labelled_data_occupied:
        row = []
        timestamp = datum['key']
        row.append(timestamp)
        data_dict = datum['value']

        for key in data_dict:
            row.append(data_dict[key])

        data.append(row)
    return data


df_occupied = pd.DataFrame(reshape_dataset(labelled_data_occupied), columns=columns)
df_occupied['occupied'] = 1

df_not_occupied = pd.DataFrame(reshape_dataset(labelled_data_unoccupied), columns=columns)
df_not_occupied['occupied'] = 0

print(df_occupied.head(3))
print(df_not_occupied.head(3))

full_ds = pd.concat([df_occupied, df_not_occupied])

full_ds = shuffle(full_ds)
print(full_ds.head(10))




