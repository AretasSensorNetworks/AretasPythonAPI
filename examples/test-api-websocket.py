import sys
import time
sys.path.append('C:\\Users\\aretas\\Documents\\GitHub\\APIExamples\\python\\')
print(sys.path)

from aretasapiclient.api_config import *
from aretasapiclient.sensor_data_query import *
from aretasapiclient.auth import *
from aretasapiclient.aretas_client import *
from aretasapiclient.utils import Utils as autils
from aretasapiclient.api_cache import APICache
from aretasapiclient.client_websocket import SensorDataWebsocket

"""
Let's load up the API, get our client location view then find some active devices and subscribe by websocket

"""

config = APIConfig()
auth = APIAuth(config)
client = APIClient(auth)

client_location_view = client.get_client_location_view()

my_client_id = client_location_view['id']
all_macs = client_location_view['allMacs']
my_devices_and_locations = client_location_view['locationSensorViews']


def sensor_message_callback(message):
    print(message)


# fetch the active locations
active_locs = client.get_active_locations()

active_loc_objs = [loc['location'] for loc in active_locs]
# show locations with active devices
print("\nLocations with active devices:")
for active in active_loc_objs:
    print("Description: {0} Country: {1} State/Province: {2} City: {3} Lat: {4} Lon: {5} Id: {6}".format(
        active['description'],
        active['country'],
        active['state'],
        active['city'],
        active['lat'],
        active['lon'],
        active['id']))

# pick one id
location_obj = client.get_location_by_id("6ec09ce917c94f9c86ef805b44f17cb4")

# get all the macs for the location
macs = [int(device['mac']) for device in location_obj['sensorList']]

stream = SensorDataWebsocket(auth, location_obj['location']['id'], macs, sensor_message_callback)
stream.start()

time.sleep(30)
print("Stopping")
stream.stop()
