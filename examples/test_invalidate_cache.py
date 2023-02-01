import sys
import time
sys.path.append('C:\\Users\\aretas\\Documents\\GitHub\\APIExamples\\python\\')
print(sys.path)

from aretasapiclient.api_config import *
from aretasapiclient.sensor_data_query import *
from aretasapiclient.auth import *
from aretasapiclient.aretas_client import *

"""
Let's load up the API, get our client location view then find some active devices and subscribe by websocket

"""

config = APIConfig("config-test.ini")
auth = APIAuth(config)
client = APIClient(auth)

client_location_view = client.get_client_location_view(invalidate_cache=True)
