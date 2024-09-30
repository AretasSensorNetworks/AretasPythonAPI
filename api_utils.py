import logging
import requests
import pandas as pd
import plotly.graph_objects as go
from auth import APIAuth
from entities import Alert, AlertHistoryRecord


class APIUtils:
    """
    This is a utility class for various API methods that don't have their own entire classes yet
    """

    def __init__(self, api_auth: APIAuth):
        """
        Initializes the APIUtils with the provided API authentication.

        Args:
            api_auth (APIAuth): An instance of APIAuth containing authentication details.
        """
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def fetch_alert_history_record(self, eventId: int) -> AlertHistoryRecord:

        self.logger.info(f"Fetching AlertHistoryRecord for {eventId}")

        url = f"{self.api_auth.api_config.get_api_url()}alertlog/getbyeventid?eventId={eventId}"
        headers = {'Authorization': f"Bearer {self.api_auth.get_token()}"}

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            # Parse the JSON response into an AlertHistoryRecord model
            return AlertHistoryRecord(**response.json())
        else:
            response.raise_for_status()

    def fetch_alerts(self) -> list[Alert]:
        self.logger.info(f"Fetching alerts")

        url = f"{self.api_auth.api_config.get_api_url()}alert/list"
        headers = {'Authorization': f"Bearer {self.api_auth.get_token()}"}

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            # Parse the JSON response into a list of Alert models
            return [Alert(**alert) for alert in response.json()]
        else:
            response.raise_for_status()

    def fetch_alert(self, alert_id: str) -> Alert | None:

        alerts = self.fetch_alerts()

        for alert in alerts:
            if alert.id == alert_id:
                return alert

        return None

    def fetch_image_plotly(self, mac, start_timestamp, end_timestamp, sensortypes: list):

        self.logger.info(
            f"Fetching sensor data for: mac={mac}, start={start_timestamp}, end={end_timestamp}, sensortypes={sensortypes}")

        url = f"{self.api_auth.api_config.get_api_url()}sensordata/byrange"
        headers = {
            "Authorization": f"Bearer {self.api_auth.get_token()}"
        }
        params = {
            "mac": mac,
            "begin": start_timestamp,
            "end": end_timestamp,
            "type": sensortypes,
            "limit": 2000000,
            "downsample": False,
            "threshold": 100,
            "movingAverage": False,
            "windowSize": 1,
            "movingAverageType": 0,
            "offsetData": False,
            "requestedIndexes": [0],
            "arrIEQAssumptions": [0],
            "iqRange": -1,
            "interpolateData": False,
            "interpolateTimestep": 30000,
            "interpolateType": 0
        }

        # Fetch the sensor data from the API
        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            response.raise_for_status()

        # Parse the sensor data
        sensor_data = response.json()

        # Separate the data by type
        data_by_type = {}
        for datum in sensor_data:
            sensor_type = datum['type']
            if sensor_type not in data_by_type:
                data_by_type[sensor_type] = {"timestamps": [], "values": []}

            data_by_type[sensor_type]["timestamps"].append(datum["timestamp"])
            data_by_type[sensor_type]["values"].append(datum["data"])

        # Create a Plotly line chart
        fig = go.Figure()

        for sensor_type, data in data_by_type.items():
            # Convert timestamps from Unix epoch to datetime
            data_frame = pd.DataFrame({
                "timestamp": pd.to_datetime(data["timestamps"], unit='ms'),
                "value": data["values"]
            })

            fig.add_trace(go.Scatter(
                x=data_frame["timestamp"],
                y=data_frame["value"],
                mode='lines',
                name=f'Sensor Type {sensor_type}'
            ))

        # Customize layout
        fig.update_layout(
            title=f"Sensor Data for MAC: {mac}",
            xaxis_title="Time",
            yaxis_title="Sensor Value",
            template="plotly",
            width=800,  # Set your desired width
            height=600,  # Set your desired height
        )

        # Export the plot as a PNG image
        image_bytes = fig.to_image(format="png")

        return image_bytes

    def fetch_chart_image(self, mac, start_timestamp, end_timestamp, sensortype, auth_token):

        self.logger.info(
            f"Fetching chart image for: {mac} start:{start_timestamp} end:{end_timestamp} sensortype:{sensortype}")

        url = f"{self.api_auth.api_config.get_api_url()}sensordata/chartimage"
        headers = {
            "Authorization": f"Bearer {self.api_auth.get_token()}"
        }
        params = {
            "mac": mac,
            "begin": start_timestamp,
            "end": end_timestamp,
            "type": [sensortype],
            "width": 640,  # default value
            "height": 480,  # default value
            "limit": 2000000,
            "downsample": False,
            "threshold": 100,
            "movingAverage": False,
            "windowSize": 1,
            "movingAverageType": 0,
            "offsetData": False,
            "requestedIndexes": [0],  # default value
            "arrIEQAssumptions": [0],  # default value
            "iqRange": -1,
            "interpolateData": False,
            "interpolateTimestep": 30000,
            "interpolateType": 0
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return response.content  # Returns the image data in PNG format
        else:
            response.raise_for_status()
