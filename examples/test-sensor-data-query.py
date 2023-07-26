"""
Basic testing for the sensor data query object

A kind soul could eventually flesh this out to test all the extended args like
interpolation, moving average, decimation, etc. etc.
"""
from auth import *
from aretas_client import *
from sensor_data_query import SensorDataQuery

config = APIConfig('./config.ini')
auth = APIAuth(config)
client = APIClient(auth)
sdq = SensorDataQuery(auth)

client_location_view = client.get_client_location_view()

my_client_id = client_location_view['id']
all_macs = client_location_view['allMacs']
my_devices_and_locations = client_location_view['locationSensorViews']

active_locs = client.get_active_locations()
active_locs_objs = [loc['location'] for loc in active_locs]
# show locations with active devices
print("\nLocations with active devices:")
for active in active_locs_objs:
    print("Description: {0} Country: {1} State/Province: {2} City: {3} Lat: {4} Lon: {5}".format(
        active['description'],
        active['country'],
        active['state'],
        active['city'],
        active['lat'],
        active['lon']))

print("\nActive Devices:")
active_devices = client.get_active_devices()
for active_device in active_devices:
    print("Description: {0} Mac: {1} Lat: {2} Lon: {3}".format(
        active_device['description'],
        active_device['mac'],
        active_device['lat'],
        active_device['lon']))

# fetch one active device mac out of the list
mac = active_devices[0]['mac']

# fetch 24 hours of data
sensor_data = sdq.get_data(mac=mac, begin=AUtils.now_ms() - (24 * 60 * 60 * 1000), end=AUtils.now_ms())

# decode the timestamp with python datetime

print(sensor_data)
