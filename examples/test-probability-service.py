"""
Basic testing for the sensor data query object

A kind soul could eventually flesh this out to test all the extended args like
interpolation, moving average, decimation, etc. etc.
"""
from auth import *
from aretas_client import *
from probability import ProbabilityServiceAPIClient
from sensor_data_query import SensorDataQuery

import os

os.chdir('../')

config = APIConfig('config.ini')
auth = APIAuth(config)
client = APIClient(auth)
sdq = SensorDataQuery(auth)

client_location_view: ClientLocationView = client.get_client_location_view()

my_client_id = client_location_view.id
all_macs = client_location_view.allMacs
my_devices_and_locations = client_location_view.locationSensorViews

active_locs = client.get_active_locations()
active_locs_objs = [loc.location for loc in active_locs]
# show locations with active devices
print("\nLocations with active devices:")
for active in active_locs_objs:
    print("Description: {0} Country: {1} State/Province: {2} City: {3} Lat: {4} Lon: {5}".format(
        active.description,
        active.country,
        active.state,
        active.city,
        active.lat,
        active.lon))

print("\nActive Devices:")
active_devices = client.get_active_devices()
for active_device in active_devices:
    print("Description: {0} Mac: {1} Lat: {2} Lon: {3}".format(
        active_device.description,
        active_device.mac,
        active_device.lat,
        active_device.lon))

# fetch one active device mac out of the list
mac = active_devices[0].mac

probability_client = ProbabilityServiceAPIClient(auth)

end_ms = AUtils.now_ms()
begin_ms = end_ms - (24 * 60 * 60 * 1000)

# Get a univariate histogram
histogram = probability_client.get_univariate_histogram(
    macs=[mac],
    sensor_type=246,
    start_time=begin_ms,
    end_time=end_ms,
    record_limit=1000000,
    n_bins=50
)

if histogram:
    print(histogram)
else:
    print("Failed to retrieve histogram.")

# Calculate the probability of specific sensor data events occurring using the fetched histogram
sensor_data_values = [21.0, 30.0, 11.2]  # Example sensor data values
probabilities = []

if histogram:
    for value in sensor_data_values:
        # Find the bin that the value falls into
        for bin in histogram.bins:
            if bin.min <= value < bin.max:
                probabilities.append(bin.probability)
                break
        else:
            probabilities.append(0.0)  # If no bin is found, probability is 0

    print("Calculated probabilities for the given sensor data:", probabilities)
else:
    print("Failed to retrieve histogram.")
