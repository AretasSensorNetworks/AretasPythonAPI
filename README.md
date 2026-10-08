# Aretas API Client Library

A Python client library for interacting with the Aretas IoT REST API. The library covers device and location management, historical data queries, real-time streaming, analytics, alerts, building maps, and several ancillary services (geocoding, timezone lookup, IP utilities, probability distributions).

---

## Table of Contents

1. [Configuration](#configuration)
2. [Authentication](#authentication--apiconfig--apiauth)
3. [Client Location View](#client-location-view--apiclient)
4. [High-Speed Cache](#high-speed-cache--apicache)
5. [Historical Sensor Data Query](#historical-sensor-data-query--sensordataquery)
6. [Sensor Data Ingest](#sensor-data-ingest--sensordataingest)
7. [Sensor Data Chart Images](#sensor-data-chart-images--sensordatachartimage)
8. [Sensor Type Metadata](#sensor-type-metadata--apisensortypeinfo)
9. [Real-time WebSocket Streaming](#real-time-websocket-streaming--sensordatawebsocket)
10. [Building Maps](#building-maps--buildingmapapiclient)
11. [Data Classifiers](#data-classifiers--dataclassifier--dataclassifiercrud)
12. [Data Classifier Records](#data-classifier-records--dataclassifierrecord--dataclassifierrecordcrud)
13. [Labelled Data Query](#labelled-data-query--labelleddataquery)
14. [Alert Management](#alert-management--alertservice)
15. [Alert History](#alert-history--alerthistoryservice)
16. [Alert Log](#alert-log--alertlogservice)
17. [Site Locations](#site-locations--sitelocationservice)
18. [Devices](#devices--deviceservice)
19. [Alert Tester](#alert-tester--alert_testerpy)
20. [Probability & Statistics](#probability--statistics--probabilityserviceapiclient)
21. [Geocoding](#geocoding--geocodingapiclient)
22. [IP Utilities](#ip-utilities--iputilapiclient)
23. [Timezone Lookup](#timezone-lookup--timezoneapiclient)
24. [Utilities](#utilities--utils)
25. [Entities / Data Models](#entities--data-models)

---

## Configuration

All modules require an `APIConfig` object which reads credentials from an INI file.

By default `APIConfig()` looks for `config.cfg` in the current working directory. Pass an explicit path when needed:

```python
config = APIConfig()                        # looks for ./config.cfg
config = APIConfig('path/to/config.ini')    # explicit path
```

A minimal `config.ini`:

```ini
[ARETAS]
API_URL = https://iot.aretas.ca/rest/
API_USERNAME = your_username
API_PASSWORD = your_password
```

`APIConfig` also exposes `get_value(key)` to read arbitrary keys from the `[ARETAS]` section, which is useful if you store additional application settings in the same file.

---

## Authentication — `api_config.py` / `auth.py`

**Classes:** `APIConfig`, `APIAuth`

`APIAuth` manages token acquisition and refresh. Every other service class accepts an `APIAuth` instance in its constructor.

```python
from api_config import APIConfig
from auth import APIAuth

config = APIConfig('config.ini')
auth = APIAuth(config)

# Verify the current token
is_valid = auth.test_token()          # -> bool

# Retrieve the token string
token = auth.get_token()              # -> str | None

# Force a fresh token
token = auth.refresh_token()          # -> str | None

# Retrieve token, refreshing automatically if expired
token = auth.get_token(refresh_if_expired=True)
```

Token management notes:
- If a token string is passed at construction time (`APIAuth(config, token="...")`) the object will not auto-refresh — you control the lifecycle manually.
- Many service classes internally call `refresh_token()` and retry once on receiving a 401 response, so you rarely need to manage tokens explicitly in application code.

---

## Client Location View — `aretas_client.py`

**Class:** `APIClient`

Provides a hierarchical view of all objects associated with your account: locations, devices (sensors), and building maps.

```python
from aretas_client import APIClient
from entities import ClientLocationView, LocationSensorView, Sensor

client = APIClient(auth)

# Full hierarchy: locations → devices → building maps
clv: ClientLocationView = client.get_client_location_view()

# Top-level fields
my_client_id = clv.id          # your account UUID
all_macs     = clv.allMacs     # flat list of every device MAC

# Locations that have reported data recently
active_locs = client.get_active_locations()   # -> List[LocationSensorView]

# Devices that have reported within the last N hours (default 24)
active_devices = client.get_active_devices()                # default 24 h
active_devices = client.get_active_devices(duration=48)     # custom window

# Lookup helpers
loc  = client.get_location_by_id("location-uuid")           # -> LocationSensorView | None
dev  = client.get_device_by_id("device-uuid")               # -> Sensor | None
dev  = client.get_sensor_by_mac(123456789)                  # -> Sensor | None

# Force a fresh fetch (bypasses the internal cache)
clv = client.get_client_location_view(invalidate_cache=True)
```

The result is cached after the first call. Subsequent calls return the cached copy unless `invalidate_cache=True` is passed.

→ See [`examples/test-aretas-api.py`](examples/test-aretas-api.py) and [`examples/test_invalidate_cache.py`](examples/test_invalidate_cache.py)

---

## High-Speed Cache — `api_cache.py`

**Class:** `APICache`

Fetches the **most recent reading** for each sensor type on one or more devices directly from an in-memory cache on the server. This is significantly faster than a full historical query and is the recommended way to display a live dashboard.

```python
from api_cache import APICache

cache = APICache(auth)

# Pass a list of MAC addresses
latest = cache.get_latest_data([111111111, 222222222])
# Returns a list of dicts: [{'mac': int, 'type': int, 'data': float, 'timestamp': int}, ...]

# Build a per-device, per-type map
sensor_data_map = {}
for datum in latest:
    mac  = datum['mac']
    stype = datum['type']
    sensor_data_map.setdefault(mac, {})[stype] = {
        'data': datum['data'],
        'timestamp': datum['timestamp']
    }
```

→ See [`examples/test-aretas-api.py`](examples/test-aretas-api.py)

---

## Historical Sensor Data Query — `sensor_data_query.py`

**Class:** `SensorDataQuery`

Queries time-series sensor data for a device with a rich set of server-side processing options. All timestamps are Unix epoch **milliseconds**.

```python
from sensor_data_query import SensorDataQuery
from utils import Utils as AUtils

sdq = SensorDataQuery(auth)

now   = AUtils.now_ms()
begin = now - 24 * 60 * 60 * 1000   # 24 hours ago

# Minimal query — all sensor types for the last 24 hours
data = sdq.get_data(mac=123456789, begin=begin, end=now)

# Filter to specific sensor types
data = sdq.get_data(mac=123456789, begin=begin, end=now, types=[246, 248])

# With server-side processing options
data = sdq.get_data(
    mac=123456789,
    begin=begin,
    end=now,
    down_sample=True,          # decimate the data
    threshold=1000,            # target number of points after decimation
    moving_average=True,       # apply moving average smoothing
    window_size=5,             # moving average window
    iq_range=True,             # remove outliers using IQR filter
    interpolate_data=True,     # fill gaps by interpolation
    interpolate_timestep=60000 # interpolation step in ms (60 s here)
)

# Returns List[SensorDatum]; reshape by type for easier access
by_type = SensorDataQuery.reshape_by_type(data)
# by_type is dict[int, SensorDataByType] keyed on sensor type integer
```

Key query parameters:

| Parameter | Description |
|---|---|
| `types` | List of sensor type integers to include (empty = all) |
| `limit` | Maximum number of records to return |
| `down_sample` | Enable server-side decimation |
| `threshold` | Target record count after decimation |
| `moving_average` | Apply a moving average |
| `window_size` | Moving average window (number of samples) |
| `iq_range` | Remove outliers via interquartile range filter |
| `interpolate_data` | Fill gaps with interpolated values |
| `interpolate_timestep` | Step size in ms for interpolation |
| `requested_indexes` | Request IEQ composite indexes |
| `offset_data` | Shift data values by a fixed offset |

→ See [`examples/test-sensor-data-query.py`](examples/test-sensor-data-query.py) and [`examples/date-conv-query-example.py`](examples/date-conv-query-example.py)

---

## Sensor Data Ingest — `sensor_data_ingest.py`

**Class:** `SensorDataIngest`

Posts one or more sensor readings to the API. Each datum is a plain dict with the keys `mac`, `type`, `data`, and `timestamp` (ms). If `timestamp` is omitted it is filled in automatically.

```python
from sensor_data_ingest import SensorDataIngest
from utils import Utils

ingest = SensorDataIngest(auth)

# Single datum
datum = {'mac': 123456789, 'type': 181, 'data': 450.0, 'timestamp': Utils.now_ms()}
success = ingest.send_datum(datum, overwritetimestamp=False)          # -> bool

# Same call, but keep the API's reply so rejections can be told apart
# ("not authorized" = unknown MAC, "data exceeds allowed range!" = out-of-range value, ...)
result = ingest.send_datum_ws(datum, overwritetimestamp=False)        # -> WebServiceBoolean
print(result.get_boolean_response(), result.get_message())

# With automatic token refresh and retry
success = ingest.send_datum_auth_check(datum, overwritetimestamp=False, n_retries=3)

# Batch send
dataset = [
    {'mac': 123456789, 'type': 181, 'data': 450.0, 'timestamp': Utils.now_ms()},
    {'mac': 123456789, 'type': 246, 'data': 22.5,  'timestamp': Utils.now_ms()},
]
success = ingest.send_data(dataset, auth_check=True)   # auth_check retries on 401
```

Use `auth_check=True` / `send_datum_auth_check` in long-running services where the token may expire between calls.

→ See [`examples/test_send_data_batch.py`](examples/test_send_data_batch.py)

---

## Sensor Data Chart Images — `sensor_data_chart_image.py`

**Class:** `SensorDataChartImage`

Fetches a pre-rendered PNG chart image from the API for a given device, time range, and set of sensor types. Accepts the same query parameters as `SensorDataQuery.get_data()` plus `width` and `height`.

```python
from sensor_data_chart_image import SensorDataChartImage
from utils import Utils as AUtils

sdci = SensorDataChartImage(auth)

image_bytes = sdci.get_chart_image(
    mac=123456789,
    begin=AUtils.now_ms() - 2 * 60 * 60 * 1000,   # last 2 hours
    end=AUtils.now_ms(),
    types=[181, 246],   # CO2 + temperature
    width=1024,
    height=768
)

if image_bytes:
    with open('chart.png', 'wb') as f:
        f.write(image_bytes)
```

Returns `None` on error. The default dimensions are 800 × 600.

→ See [`examples/test-sensor-data-chart-image.py`](examples/test-sensor-data-chart-image.py)

---

## Sensor Type Metadata — `sensor_type_info.py`

**Class:** `APISensorTypeInfo`

Fetches the catalogue of sensor type definitions from the API (labels, units, color hints, recommended bands, citations, etc.) and provides lookup helpers. Metadata is fetched automatically on construction.

```python
from sensor_type_info import APISensorTypeInfo

sti = APISensorTypeInfo(auth)

# Full metadata dict for a single type (raw JSON from API)
meta = sti.get_sensor_type_metadata(246)   # -> dict
# e.g. {'label': 'CO2', 'units': 'ppm', 'color': '#...', ...}

# Human-readable "Label units" strings for a list of types
labels = sti.get_labels([181, 246, 248])
# -> ["Carbon Dioxide ppm", "Temperature °C", "Relative Humidity %"]

# Refresh the cache
sti.refresh_sensor_type_into()
```

An example of the metadata structure for CO2 is available in [`sample_metadata/co2_example_type.json`](sample_metadata/co2_example_type.json).

---

## Real-time WebSocket Streaming — `client_websocket.py`

**Class:** `SensorDataWebsocket`

Streams live sensor readings from the API via WebSocket. You supply a list of device MACs to watch and a callback that is called for every inbound message. The connection runs in a background thread and sends automatic keep-alive pings every 10 seconds.

```python
from client_websocket import SensorDataWebsocket
import time

def on_sensor_data(message):
    """Called for every inbound sensor datum."""
    print(message)   # message is a parsed dict

# Provide a location ID and the MACs you want to subscribe to
stream = SensorDataWebsocket(
    api_auth=auth,
    target_location_id="location-uuid",
    target_macs=[111111111, 222222222],
    message_callback=on_sensor_data,
    ws_trace_enable=False   # set True to log raw WS frames
)

stream.start()
time.sleep(30)   # collect data for 30 seconds
stream.stop()
```

→ See [`examples/test-api-websocket.py`](examples/test-api-websocket.py) for a basic streaming example and [`examples/test-api-websocket-classifier.py`](examples/test-api-websocket-classifier.py) for a more advanced workflow that combines streaming with a multivariate classifier.

---

## Building Maps — `building_maps.py`

**Class:** `BuildingMapAPIClient`

Manages floor-plan / building-map images associated with a location, and can overlay device position markers on top of a map image.

```python
from building_maps import BuildingMapAPIClient
from entities import Point

bm = BuildingMapAPIClient(auth)

# List all building maps for a location
maps = bm.list_building_maps_by_location("location-uuid")   # -> List[BuildingMap] | None

# Fetch raw PNG bytes for a map
image_bytes = bm.get_map_image("location-uuid", "map-uuid")   # -> bytes | None

# Fetch a map with device positions overlaid
points = [
    Point(x=100, y=150, z=0),
    Point(x=300, y=350, z=0),
]
image_bytes = bm.get_map_image_with_points("location-uuid", "map-uuid", points)

# CRUD operations
from entities import BuildingMap
new_map = BuildingMap(...)
bm.create_building_map(new_map)    # -> bool
bm.update_building_map(new_map)    # -> bool
bm.delete_building_map("map-uuid") # -> bool
```

→ See [`examples/test-building-maps.py`](examples/test-building-maps.py)

---

## Data Classifiers — `data_classifier.py`

**Classes:** `DataClassifier`, `DataClassifierCRUD`

A *data classifier* defines the feature set for a machine-learning model: which sensor types are required, a human label, and an optional regression target value. CRUD operations are exposed through `DataClassifierCRUD`.

```python
from data_classifier import DataClassifier, DataClassifierCRUD

crud = DataClassifierCRUD(auth)

# List all classifiers
classifiers = crud.list()   # -> List[DataClassifier]
for dc in classifiers:
    print(dc.get_label(), dc.get_description(), dc.get_self_id())

# Create a new classifier
dc = DataClassifier()
dc.set_label("Occupied")
dc.set_description("Room occupancy model")
dc.set_required_types([181, 246, 248])    # CO2, Temperature, Relative Humidity
result = crud.create(dc)   # -> WebServiceBoolean

# Update / delete
crud.edit(dc)
crud.delete(dc)
```

Classifiers are identified by UUID strings. The `required_types` list defines which sensor types the associated labeled data must include.

→ See [`examples/test-data-classifier-record.py`](examples/test-data-classifier-record.py)

---

## Data Classifier Records — `data_classifier_record.py`

**Classes:** `DataClassifierRecord`, `DataClassifierRecordCRUD`

A *classifier record* labels a time window on one or more devices — essentially marking "this period was occupied" or assigning a regression value. Records are used to build training datasets.

```python
from data_classifier_record import DataClassifierRecord, DataClassifierRecordCRUD
from utils import Utils as AUtils

crud = DataClassifierRecordCRUD(auth)

# Create a labeled time window
record = DataClassifierRecord()
record.set_data_classifier_id("classifier-uuid")
record.set_start_timestamp(AUtils.now_ms() - 3600000)   # 1 hour ago
record.set_end_timestamp(AUtils.now_ms())
record.set_assoc_macs([111111111, 222222222])
result = crud.save(record)   # -> WebServiceBoolean

# Retrieve all records for a classifier
records = crud.get_by_id("classifier-uuid")   # -> List[DataClassifierRecord]

# Query by MACs and a time window
records = crud.get_by_mac_timestamp(
    macs=[111111111],
    start_time_ms=AUtils.now_ms() - 7 * 24 * 3600 * 1000,
    end_time_ms=AUtils.now_ms()
)

# Delete one record or all records for a classifier
crud.remove(record)
crud.purge("classifier-uuid")
```

→ See [`examples/test-data-classifier-record.py`](examples/test-data-classifier-record.py) and [`examples/data-classifier-record-query.py`](examples/data-classifier-record-query.py)

---

## Labelled Data Query — `labelled_data_query.py`

**Class:** `LabelledDataQuery`

Fetches the aggregated, time-aligned sensor data for all records belonging to a classifier. The output is in a column-oriented format suitable for building pandas DataFrames and feeding into ML pipelines.

```python
from labelled_data_query import LabelledDataQuery
from sensor_type_info import APISensorTypeInfo
import pandas as pd

ldq = LabelledDataQuery(auth)
sti = APISensorTypeInfo(auth)

# Returns a list of {'key': timestamp_ms, 'value': {type_str: float, ...}}
dataset = ldq.get_labelled_data("classifier-uuid")

# Extract column labels using sensor type metadata
first_keys = list(dataset[0]['value'].keys())
columns = sti.get_labels(first_keys)   # e.g. ['CO2 ppm', 'Temperature C', ...]
columns.insert(0, 'timestamp')

# Reshape to rows and load into a DataFrame
rows = ldq.reshape_dataset(dataset, first_keys)
df = pd.DataFrame(rows, columns=columns)
```

The `max_time_align_diff` parameter (default 30 s) controls how far apart two readings may be before they are considered misaligned and dropped.

→ See [`examples/test-labeled-data-api.py`](examples/test-labeled-data-api.py)

---

## Alert Management — `alert_service.py`

**Class:** `AlertService`

Full CRUD for alert definitions. An `Alert` specifies a sensor type, MAC address(es), threshold value, notification emails, and delivery settings.

```python
from alert_service import AlertService
from entities import Alert

svc = AlertService(auth)

# List all alerts
alerts = svc.list()   # -> List[Alert] | None

# Create an alert
alert = Alert(
    id="",                              # auto-assigned by API
    owner=my_client_id,                 # your account UUID
    name="High CO2",
    description="Alert when CO2 exceeds 1000 ppm",
    sensorType=181,                     # CO2 (ppm)
    sensorMacs="123456789",
    thresholdA=1000.0,
    thresholdAType=True,                # True = ceiling (trigger above threshold)
    alertEmails="ops@example.com",
    disabled=False,
    alertFrequency=60,                  # minutes between repeated alerts
    maxNumAlerts=5,
    durationTrigger=300000,             # ms the condition must persist before triggering
    alertTriggerTTL=3600                # seconds before the trigger resets
)
result = svc.save(alert)   # -> WebServiceBoolean

# Update
alert.thresholdA = 1200.0
svc.update(alert)

# Delete
svc.remove(alert)
```

All mutating methods retry once automatically on a 401 response.

→ See [`examples/alert_service_test.py`](examples/alert_service_test.py)

---

## Alert History — `alert_history_service.py`

**Class:** `AlertHistoryService`

Queries the recent alert event log (backed by a Redis cache on the server) and supports dismissing/acknowledging individual events.

```python
from alert_history_service import AlertHistoryService
from alert_service import AlertService

alert_svc   = AlertService(auth)
history_svc = AlertHistoryService(auth)

# Get all alert IDs to query against
alert_ids = [a.id for a in alert_svc.list()]

# Fetch recent alert events (include already-dismissed ones)
records = history_svc.list_alert_history(alert_ids, show_dismissed=True)
# -> List[AlertHistoryRecord]

for r in records:
    print(r.mac, r.sensorType, r.sensorData, r.timestamp, r.isDismissed)

# Enriched query — includes the full Sensor object and analytics time windows
enriched = history_svc.get_alert_history_with_details(
    alert_ids,
    client_location_view,
    show_dismissed=False
)
for e in enriched:
    print(e['sensor'].description, e['alert_history'].sensorData)
    print(e['analytics_start_time'], e['analytics_end_time'])

# Dismiss (acknowledge) an event
history_svc.dismiss_alert_history_object(
    mac=r.mac,
    sensor_type=r.sensorType,
    alert_id=r.alertId
)   # -> bool
```

→ See [`examples/alert_history_service_test.py`](examples/alert_history_service_test.py)

---

## Alert Log — `alert_log_service.py`

**Class:** `AlertLogService`

Reads and purges the **persistent** alert event log. Every incident the alert engine opens is written here as an `AlertLogRecord` and closed in place when the return-to-normal reading arrives — this is the durable record behind the alert-log pages, whereas `AlertHistoryService` reads the short-lived recent-history cache. Windows are epoch ms and apply to the record's `timestamp` (the reading that opened the incident).

```python
from alert_log_service import AlertLogService

alog = AlertLogService(auth)

# Incidents for one alert in a window (ascending). `limit` is always sent — the API returns
# nothing when it is omitted.
records = alog.list_by_alert_id(alert_id, start_ms, end_ms, limit=1000)   # -> List[AlertLogRecord] | None
for r in records:
    print(r.eventId, r.mac, r.type, r.data, r.timestamp, r.isActive, r.rtnTimestamp)

# Incidents for one device (newest first)
records = alog.list_by_mac(mac=123456789, start=start_ms, end=end_ms)

# Everything in the account for a window of at most 8 days (newest first)
records = alog.list_account_history(start_ms, end_ms)

# One record by event id
rec = alog.get_by_event_id(event_id)                                      # -> AlertLogRecord | None

# Delete an alert's records: age_ms=0 purges them all, otherwise only those older than age_ms
removed = alog.purge(alert_id, age_ms=0)                                  # -> int | None
```

`AlertLogRecord` fields: `eventId`, `mac`, `timestamp`, `rtnTimestamp` (0 while the incident is open), `type`, `data`, `alertId`, `isActive`.

→ Used by [`alert_tester.py`](alert_tester.py)

---

## Site Locations — `site_location_service.py`

**Class:** `SiteLocationService`

Create, list, update and delete site locations (buildings / sites). A device's `owner` is the id of its site location. The API does not return the id of a newly created location, so `create()` is normally followed by `find_by_description()`.

```python
from site_location_service import SiteLocationService

sites = SiteLocationService(auth)

body = SiteLocationService.build(owner=my_client_id, description="Head Office",
                                 lat=49.28, lon=-123.12, timezone="America/Vancouver")
sites.create(body)                                        # -> WebServiceBoolean
location = sites.find_by_description(my_client_id, "Head Office")   # -> dict | None

locations = sites.list(my_client_id)                      # -> List[dict] | None

location['description'] = "Head Office (2nd floor)"
sites.update(location)                                    # -> WebServiceBoolean

# WARNING: deleting a location also deletes every device and building map it contains
sites.delete(location)                                    # -> WebServiceBoolean
```

The `timezone` (an IANA id) is what the alert engine uses to evaluate time-windowed (threshold B) alert rules for devices at that location.

---

## Devices — `device_service.py`

**Class:** `DeviceService`

Create, list, update and remove devices (the API calls them *sensor locations*). MACs are decimal integers and unique platform-wide: creating a device with a MAC that already exists fails with the API's duplicate-MAC message. The API does not return the id of a newly created device, so `create()` is normally followed by `find_by_mac()`.

```python
from device_service import DeviceService

devices = DeviceService(auth)

body = DeviceService.build(owner=location['id'], mac=123456789, description="Boardroom",
                           lat=location['lat'], lon=location['lon'],
                           notify_if_down=True, down_interval_ms=2 * 3600 * 1000)
result = devices.create(body)                             # -> WebServiceBoolean
device = devices.find_by_mac(location['id'], 123456789)   # -> dict | None

all_devices = devices.list(location['id'])                # -> List[dict] | None

device['description'] = "Boardroom (east)"
devices.update(device)                                    # -> WebServiceBoolean

devices.remove(device)                                    # -> WebServiceBoolean
```

A newly created MAC is accepted by the data ingest only after the platform's periodic refresh of its known-device list (typically within a few minutes) — until then `ingest/…` replies `not authorized`. `SensorDataIngest.send_datum_ws` exposes that reply.

---

## Alert Tester — `alert_tester.py`

An end-to-end check that the alerting pipeline works, from a device's reading to an alert incident record. It creates a throwaway site location and a simulated device (random fake MAC), creates a ceiling-threshold alert on it with notifications disabled, behaves like a device for a few minutes — normal readings at a device-like cadence, then readings above the threshold, then normal again — and verifies that an incident was opened (persistent alert log + recent-history cache) and then resolved. Whether it passes, fails or is interrupted, it removes the alert, its log records, the device and the location it created.

```bash
python alert_tester.py --config config.ini
python alert_tester.py --config config.ini --type 181 --normal 450 --threshold 1000 --exceed 1500
python alert_tester.py --config config.ini --interval 90 --normal-count 2
python alert_tester.py --config config.ini --duration-trigger 120000     # 2-minute hold time
python alert_tester.py --config config.ini --location-id <existing-location-id>
python alert_tester.py --config config.ini --email you@example.com      # also send ONE real notification
python alert_tester.py --config config.ini --report report-alert-test.json
```

| Option | Default | Meaning |
|---|---|---|
| `--type` | 181 (CO2 ppm) | sensor type to alert on; values are checked against the type's ingest range before anything is created |
| `--normal` / `--threshold` / `--exceed` | 450 / 1000 / 1500 | reading levels; must satisfy normal ≤ threshold < exceed |
| `--interval` | 60 s | seconds between readings (a real device's cadence) |
| `--normal-count` / `--exceed-count` | 3 / 2 | readings per phase; the exceeding count is raised automatically to cover the hold time |
| `--duration-trigger` | 0 | alert hold time in ms; the report flags an incident that opens sooner than the hold allows |
| `--location-id` | create a throwaway one | put the simulated device in an existing location (that location is never deleted) |
| `--email` | off | send one real notification; by default `maxNumAlerts=0` records the incident without notifying anyone |
| `--auth-wait` / `--cache-wait` | 420 s / 75 s | how long to wait for the ingest to accept the new MAC / for the alert engine to load the new alert |
| `--fire-timeout` / `--rtn-timeout` | 180 s / 180 s | how long to wait for the incident to open / to resolve |
| `--keep-history` | off | leave the alert's log records in place |
| `--report` | none | write the full JSON report (readings sent, records seen, cleanup results) |

Exit codes: `0` the alert fired and returned to normal, `1` it did not fire or did not resolve, `2` setup problem (credentials, out-of-range values, a create call failed). A run takes roughly 6–12 minutes, most of it waiting for the platform's periodic device-list refresh and for readings paced at `--interval`.

---

## Probability & Statistics — `probability.py`

**Class:** `ProbabilityServiceAPIClient`

Builds statistical distributions over historical sensor data. Supports univariate histograms (full time range) and temporal histograms (bucketed by hour-of-day or hour-of-week). Probability and density values can be queried for arbitrary input points.

```python
from probability import ProbabilityServiceAPIClient
from utils import Utils as AUtils

prob = ProbabilityServiceAPIClient(auth)

now   = AUtils.now_ms()
begin = now - 30 * 24 * 3600 * 1000   # last 30 days

# Build a 50-bin histogram over CO2 readings for one or more devices
histogram = prob.get_univariate_histogram(
    macs=[123456789],
    sensor_type=246,
    start_time=begin,
    end_time=now,
    n_bins=50
)

# histogram.bins is a list of Bin1D objects with .min, .max, .probability
# histogram.summaryStats contains mean, stdDev, skewness, kurtosis, etc.
for b in histogram.bins:
    print(f"{b.min:.1f} – {b.max:.1f}: {b.probability:.4f}")

# Calculate the probability for specific observed values
values = [400.0, 800.0, 1200.0]
for value in values:
    for b in histogram.bins:
        if b.min <= value < b.max:
            print(f"P({value}) ≈ {b.probability:.4f}")
            break

# Temporal histogram: distribution bucketed by hour-of-day (range_type=0)
# or hour-of-week (range_type=1)
temporal = prob.get_temporal_univariate_histogram(
    macs=[123456789],
    sensor_type=246,
    start_time=begin,
    end_time=now,
    range_type=0
)

# Render histogram as a PNG heatmap image
image_bytes = prob.get_temporal_univariate_histogram_image(
    macs=[123456789],
    sensor_type=246,
    start_time=begin,
    end_time=now,
    scale_factor=2,
    palette_choice=1
)
```

→ See [`examples/test-probability-service.py`](examples/test-probability-service.py)

---

## Geocoding — `geocodingclient.py`

**Class:** `GeocodingAPIClient`

Converts a free-text address or location string to a (latitude, longitude) coordinate pair.

```python
from geocodingclient import GeocodingAPIClient

geo = GeocodingAPIClient(auth)

coords = geo.get_client_location("1600 Amphitheatre Parkway, Mountain View, CA")
# -> (37.42263, -122.08467)  or None on failure

if coords:
    lat, lng = coords
    print(f"Lat: {lat}, Lng: {lng}")
```

→ See [`examples/test-geocodingapi.py`](examples/test-geocodingapi.py)

---

## IP Utilities — `iputils_client.py`

**Class:** `IpUtilAPIClient`

Resolves the caller's public IP address and derives an approximate geographic location from it.

```python
from iputils_client import IpUtilAPIClient

ipu = IpUtilAPIClient(auth)

public_ip = ipu.get_client_ip()         # -> '203.0.113.42'  or None
coords    = ipu.get_client_location()   # -> (lat, lng)       or None
```

Note: IP geolocation is approximate and may not reflect the precise physical location of the client.

→ See [`examples/test-iputils_client.py`](examples/test-iputils_client.py)

---

## Timezone Lookup — `tzapiclient.py`

**Class:** `TimeZoneAPIClient`

Returns the IANA timezone identifier for a given latitude/longitude pair.

```python
from tzapiclient import TimeZoneAPIClient

tz = TimeZoneAPIClient(auth)

timezone_id = tz.get_timezone_id(37.7749, -122.4194)
# -> 'America/Los_Angeles'  or None

if timezone_id:
    import zoneinfo
    zone = zoneinfo.ZoneInfo(timezone_id)
```

→ See [`examples/test-tzapiclient.py`](examples/test-tzapiclient.py)

---

## Utilities — `utils.py`

**Class:** `Utils` (all static methods)

General-purpose helpers used throughout the library and in application code.

```python
from utils import Utils

# Current time in Unix epoch milliseconds
now_ms = Utils.now_ms()

# Convert a human-readable date string to milliseconds (local timezone)
ts_ms = Utils.fn_date_conv("04/10/2026 14:30:00")   # MM/DD/YYYY HH:MM:SS

# Convert milliseconds back to a readable string (UTC)
readable = Utils.convert_ts(ts_ms)   # -> "10-04-2026 14:30:00"

# Check if all required sensor types are present in a datum dict
data = {246: {'data': 450.0, 'timestamp': now_ms}, 248: None}
Utils.is_full(data)               # False — 248 is None
Utils.is_aligned(data, max_timestamp_diff=30000)    # checks timestamps are within 30 s
Utils.is_full_and_aligned(data)   # both checks combined

# Build a pandas DataFrame row from a SensorDatum
df = Utils.get_datum_df(sensor_datum_dict, sensor_type_info)
```

`fn_date_conv` uses the **local** system timezone; keep this in mind if your application runs in a different timezone than your data.

---

## Entities / Data Models

**Module:** `entities.py`

All API responses are deserialized into typed dataclasses and Pydantic models. The main hierarchy is:

```
ClientLocationView
├── id: str                          — account UUID
├── allMacs: List[int]               — flat list of all device MACs
└── locationSensorViews: List[LocationSensorView]
    ├── location: Location
    │   ├── id, description
    │   ├── address, city, state, country, zipCode
    │   └── lat, lon
    ├── sensorList: List[Sensor]
    │   ├── mac                      — device identifier (integer)
    │   ├── description
    │   ├── lat, lon
    │   ├── lastReportTime           — ms epoch
    │   ├── status: Status
    │   └── areaUsageHints: AreaUsageHints
    └── buildingMapList: List[BuildingMap]
        ├── id, name
        ├── actualWidth / actualHeight / actualDepth
        └── computedWidth / computedHeight / offsetX / offsetY / offsetZ
```

Other notable models:

| Class | Description |
|---|---|
| `SensorDatum` | Single sensor reading (`mac`, `type`, `data`, `timestamp`) |
| `SensorDataByType` | Collection of `SensorDatum` objects for one sensor type |
| `SensorBit` | Minimal sensor reading used in some cache responses |
| `Alert` | Pydantic model for alert definitions (see [Alert Management](#alert-management--alertservice)) |
| `AlertHistoryRecord` | Pydantic model for alert events |
| `AlertLogRecord` | Pydantic model for persistent alert log incidents (see [Alert Log](#alert-log--alertlogservice)) |
| `Point` | 3-D coordinate (`x`, `y`, `z`) used for building map overlays |
| `BasicRectangle` | Axis-aligned bounding box |
| `LocationTag` | Tag attached to a location |
| `WebServiceBoolean` | Standard API response wrapper (`boolean_response: bool`, `message: str`) |

Most dataclasses support `from_dict(d)` factory methods and `to_dict()` serialization.

## BLE Tag Simulator — `aretas_ble_sim`

A hardware-free simulator for the Aretas BLE tag / asset-tracking / Assist Button
subsystem. It models a virtual building (rooms, walls, floors, receiver
placements), scripted tag actors (walking personnel, parked assets, button
presses), and an indoor RF propagation model, then emits **real wire payloads**
exactly as receiver hardware would — sighting batches and prioritized tag
events.

```bash
# generate a sample building (JSON + floor-plan PNGs)
python -m aretas_ble_sim.building_gen --out-dir aretas_ble_sim/samples

# free-run a scenario and record a deterministic "golden trace"
python -m aretas_ble_sim.run_sim --scenario aretas_ble_sim/samples/walkthrough.scenario.yaml

# provision everything the scenario needs (location + receiver devices + tags,
# idempotent), then drive the live MQTT ingest in real time
python -m aretas_ble_sim.provision --scenario ... --config config.cfg
python -m aretas_ble_sim.run_sim --scenario ... --transport mqtt --config config.cfg

# CI assertion mode: score what the platform saw, JSON report + exit code
python -m aretas_ble_sim.run_sim --scenario ... --transport mqtt --score report.json
```

Highlights:

- **Deterministic**: same scenario + seed + epoch produce byte-identical
  traces (`trace.jsonl` + ground-truth `truth.jsonl` + `manifest.json`) —
  usable as regression fixtures for localization code.
- **Faithful edge behavior**: per-tag advertising cadences and trigger-burst
  semantics of real beacon models (Blue Charm BC011, RuuviTag RAWv2),
  receiver-side rate capping, batching, burst-to-event collapse, and
  journal/retransmit-until-acked event delivery.
- **Physical RF model**: log-distance path loss, per-wall/per-slab
  attenuation, per-advertising-channel stationary fading, per-receiver bias,
  reception-probability vs RSSI, and tag barometry for floor detection.
- Tests: `pytest aretas_ble_sim/tests`.

See `aretas_ble_sim/__init__.py` and the sample scenario YAMLs for details.
