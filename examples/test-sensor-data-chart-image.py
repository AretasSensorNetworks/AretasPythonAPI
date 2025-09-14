"""
Basic testing for the SensorDataChartImage client

This script demonstrates fetching a PNG chart image for recent sensor data.
"""
# Standard imports
from api_config import APIConfig
from auth import APIAuth
from aretas_client import APIClient
from sensor_data_query import SensorDataQuery
from sensor_data_chart_image import SensorDataChartImage
from utils import Utils as AUtils
import os
import io
import matplotlib.pyplot as plt
from PIL import Image

# Change to project root
os.chdir('../')

# Initialize configuration and authentication
config = APIConfig('config.ini')
auth = APIAuth(config)

# Initialize clients
client = APIClient(auth)
sdq = SensorDataQuery(auth)
sdci = SensorDataChartImage(auth)

# Fetch active devices
active_devices = client.get_active_devices()
if not active_devices:
    print("No active devices to test chart image.")
    exit(1)

# Select a device MAC address
mac = active_devices[0].mac

# Fetch recent sensor data to determine types
raw_data = sdq.get_data(
    mac=mac,
    begin=AUtils.now_ms() - (24 * 60 * 60 * 1000),
    end=AUtils.now_ms()
)
if not raw_data:
    print("No sensor data available to test chart image.")
    exit(1)

# Pick the first sensor type
unique_types = {datum.get_type() for datum in raw_data}
types_list = list(unique_types)[:3]
print(f"Testing chart image for mac={mac}, types={types_list}")

def show_image(image_bytes: bytes, title: str = None):
    """
    Display image data in a matplotlib window.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        plt.imshow(img)
        if title:
            plt.title(title)
        plt.axis('off')
        plt.show()
    except Exception as e:
        print(f"Error displaying image: {e}")

# Fetch the chart image
image_data = sdci.get_chart_image(
    mac=mac,
    begin=AUtils.now_ms() - (2 * 60 * 60 * 1000),
    end=AUtils.now_ms(),
    types=types_list
)
if image_data:
    print(f"Successfully retrieved chart image: {len(image_data)} bytes")
    # Display the image
    show_image(image_data, title=f"Chart Image for MAC {mac}, Types {types_list}")
else:
    print("Failed to retrieve chart image.")