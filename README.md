# Aretas API Client Libary

This is a (currently) "barebones" (compared to all the available endpoints) framework for interacting with the Aretas REST API in python

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
- Basic data posting to the API

### Config ###

You will normally need a file called ``config.ini`` somewhere in your working directory path

The root config object ``config = APIConfig()`` will look for config.ini in the local path
If it doesn't exist there, you can supply a path ``config = APIConfig('path/to/file/config.ini')``

There are many ways to manage the API token that we don't cover here. 
What IS provided is an automatic way to acquire a token and use it in the various modules. I
f the token expires, YMMV depending on how the class implements token refresh and 401 handling.

There is an example in ``sensor_data_ingest.py`` that demonstrates how to refresh or reaquire a token automatically after expiry in the method called ``send_datum_auth_check``

A barebones config file should contain:

    [DEFAULT]
    API_URL = https://iot.aretas.ca/rest/

    API_USERNAME = username
    API_PASSWORD = password


Basic instantiation and usage of the API:

    # if you have the module installed somewhere weird, you can use this to add it to the path
    # import sys
    # sys.path.append('X:\\path\\to\\working\\dir\\')
    # print(sys.path)

    from api_config import *
    from sensor_data_query import *
    from auth import *
    from aretas_client import *
    
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
