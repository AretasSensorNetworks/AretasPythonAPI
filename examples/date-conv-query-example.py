from auth import *
from aretas_client import *
from sensor_data_query import SensorDataQuery
from utils import Utils

"""
This example demonstrates how to use human readable
date/time strings for constructing queries

The demo will query your account

- Get a list of active devices / locations
- Pick the first one as the device to query, then 
- convert the provided date / time strings into timestamps and query the data

Change the date/time strings to times when you know you have data
"""

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
mac = active_devices[2]['mac']

# start time for event
dt1 = "09/04/2023 12:00:00"
# end time for event
dt2 = "09/04/2023 16:00:00"

# convert to timestamp
start = Utils.fn_date_conv(dt1)
end = Utils.fn_date_conv(dt2)

sensor_data = sdq.get_data(mac=mac, begin=start, end=end)

print(sensor_data[0:10])


