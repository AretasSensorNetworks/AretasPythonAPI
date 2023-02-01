import sys
sys.path.append('C:\\Users\\aretas\\Documents\\GitHub\\APIExamples\\python\\')
print(sys.path)

from aretasapiclient.api_config import *
from aretasapiclient.sensor_data_query import *
from aretasapiclient.auth import *
from aretasapiclient.aretas_client import *
from aretasapiclient.api_cache import APICache


config = APIConfig()
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
            "timestmap": datum['timestamp']
        }

print(sensor_data_map)






