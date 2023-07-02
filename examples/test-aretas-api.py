from auth import *
from aretas_client import *
from api_cache import APICache

"""
This code will connect to an account with the supplied credentials in config.ini and

1. List the Client's Locations Containing Active Devices
2. List the Active Devices in each Location
3. Fetch the latest sensor data for each Active Device
4. The resulting sensor_data_map is dict indexed by mac/device id 
   Each item in that dict is a dict of data indexed by sensor type 

You can map sensor types back to sensor metadata labels using the APISensorTypeInfo class
sensor_type_info = APISensorTypeInfo(auth)

then call:

sensor_type_info.get_sensor_type_metadata(type)

This is useful where you want labels, units, color coding hints, band stops for gauges, etc. 

Some of the more common types will also have citations to recommended levels etc.

You can see an example of the type of metadata you can get in sample_metadata\co2_example_type.json
"""
config = APIConfig('./config.ini')
auth = APIAuth(config)
client = APIClient(auth)

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

# get the latest data for all the devices
active_macs = [device['mac'] for device in active_devices]

# we can always fetch the most recent readings for a device, process, or prediction from the fast cache
cache = APICache(auth)
latest_data_macs = cache.get_latest_data(active_macs)

sensor_data_map = dict()

for mac in active_macs:
    b = [datum for datum in latest_data_macs if datum["mac"] == mac]

    for datum in b:
        if mac not in sensor_data_map:
            sensor_data_map[mac] = dict()

        sensor_type = datum['type']

        if sensor_type not in sensor_data_map[mac]:
            sensor_data_map[mac][sensor_type] = dict()

        sensor_data_map[mac][sensor_type] = {
            "data": datum['data'],
            "timestamp": datum['timestamp']
        }

print(sensor_data_map)






