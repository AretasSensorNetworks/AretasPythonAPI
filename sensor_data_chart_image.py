import logging
from typing import Optional
import requests

from auth import APIAuth


class SensorDataChartImage:
    """
    Client for interacting with the SensorDataService chart image endpoint.
    Retrieves PNG chart images for sensor data queries.
    """

    def __init__(self, api_auth: APIAuth):
        """
        Initializes the SensorDataChartImage with the provided API authentication.

        :param api_auth: APIAuth instance for authentication.
        """
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def get_chart_image(
        self,
        mac: int,
        begin: int,
        end: int,
        types: list[int] = [],
        width: int = 800,
        height: int = 600,
        limit: int = 2000000,
        downsample: bool = False,
        threshold: int = 100,
        moving_average: bool = False,
        window_size: int = 1,
        moving_average_type: int = 0,
        offset_data: bool = False,
        requested_indexes: list[int] = [],
        arr_ieq_assumptions: list[float] = [],
        iq_range: float = -1.0,
        interpolate_data: bool = False,
        interpolate_timestep: int = 30000,
        interpolate_type: int = 0
    ) -> Optional[bytes]:
        """
        Fetches a chart image (PNG) for the specified sensor data.
        Maps to the /sensordata/chartimage endpoint.
        """
        url = self.api_auth.api_config.get_api_url() + "sensordata/chartimage"
        params: dict = {
            "width": width,
            "height": height,
            "mac": mac,
            "begin": begin,
            "end": end,
            "limit": limit,
            "offsetData": offset_data
        }
        if types:
            params["type"] = types
        if downsample:
            params["downsample"] = downsample
            params["threshold"] = threshold
        if moving_average:
            params["movingAverage"] = moving_average
            params["windowSize"] = window_size
            params["movingAverageType"] = moving_average_type
        if iq_range > 0:
            params["iqRange"] = iq_range
        if requested_indexes:
            params["requestedIndexes"] = requested_indexes
            params["arrIEQAssumptions"] = arr_ieq_assumptions
        if interpolate_data:
            params["interpolateData"] = interpolate_data
            params["interpolateTimestep"] = interpolate_timestep
            params["interpolateType"] = interpolate_type

        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.content
        else:
            self.logger.warning(f"Failed to fetch chart image: {response.status_code}")
            return None