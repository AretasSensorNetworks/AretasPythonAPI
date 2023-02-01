# Aretas API Client Libary

This is a (currently) "barebones" (compared to all the available endpoints) framework for intereacting with the Aretas REST API in python

All classes in the API take an instantiated APIAuth class

APIAuth needs an APIConfig object

APIConfig has one optional argument (path to a config file)

What's implemented so far:

- High speed cache fetch for latest device readings 
- Basic analytics queries for historical data
    - Interpolation
    - Data decimation
    - Outlier filtering
    - Some indexes
    
- Fetching client BO view (locations / devices / maps / etc.)
- Fetching Data Classifiers 
- Fetching labelled data (from classifiers)
- Sensor Type metadata mapping
- Ultra simple sensor data streaming (websockets) - all you do is provide a location and macs to watch and a callback
- Auth token mgmnt

You must also have at least the following barebones config file:

    [DEFAULT]
    API_URL = https://iot.aretas.ca/rest/

    API_USERNAME = username
    API_PASSWORD = password


Basic instantiation and usage of the API:

    import sys
    sys.path.append('X:\\path\\to\\working\\dir\\')
    print(sys.path)

    from aretasapiclient.api_config import *
    from aretasapiclient.sensor_data_query import *
    from aretasapiclient.auth import *
    from aretasapiclient.aretas_client import *
    
    # instantiate an APIConfig class (pass in an optional configuration file)
    config = APIConfig()
    # instantiate an APIAuth class (manages token authentication)
    auth = APIAuth(config)
    # lets view the client view for our account (shows all the locations, devices, building maps, etc)
    client = APIClient(auth)
    client_location_view = client.get_client_location_view()

    my_client_id = client_location_view['id']
    all_macs = client_location_view['allMacs']
    my_devices_and_locations = client_location_view['locationSensorViews']

    for obj in my_devices_and_locations:
        print(obj)
