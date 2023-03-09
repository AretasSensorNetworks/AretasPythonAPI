import time
from auth import *
from aretas_client import *
from client_websocket import SensorDataWebsocket

"""
Let's load up the API, get our client location view then find some active devices and subscribe by websocket

"""
# this is the basic API config object
config = APIConfig("./config.ini")

# the auth object we need to pass to various other Aretas classes
auth = APIAuth(config)

# the client object
client = APIClient(auth)

# the client location view is a hierarchical structure of the user's objects (locations, building maps, devices, etc)
client_location_view = client.get_client_location_view()

# get your client UUID
my_client_id = client_location_view['id']

# get the entire list of devices (just device IDs)
all_macs = client_location_view['allMacs']
my_devices_and_locations = client_location_view['locationSensorViews']


def sensor_message_callback(message):
    """
    A callback for the websocket handler, just prints sensor data messages to the console
    """
    print(message)


# we want to print out a list of active locations containing devices
# fetch the active locations, these are locations containing devices that have sent data recently
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

# pick one location (you must choose your own ID here or pick one out of the list
location_obj = client.get_location_by_id(active_loc_objs[0]['id'])

# get all the device ids / macs for the location
macs = [int(device['mac']) for device in location_obj['sensorList']]

stream = SensorDataWebsocket(auth, location_obj['location']['id'], macs, sensor_message_callback)
stream.start()

time.sleep(30)
print("Stopping")
stream.stop()
