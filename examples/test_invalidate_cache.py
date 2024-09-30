from auth import *
from aretas_client import *

"""
Test cache invalidation

This purges a client's cached clientlocationview

"""

config = APIConfig()
auth = APIAuth(config)
client = APIClient(auth)

client_location_view: ClientLocationView = client.get_client_location_view(invalidate_cache=True)
