import logging
from typing import Optional, List
import requests
from pydantic import BaseModel
from auth import APIAuth  # Assuming you have an APIAuth class for authentication

from pydantic import BaseModel, Field
from typing import List


class Bin1D(BaseModel):
    """Represents a single bin in a 1D histogram."""
    binSize: float
    min: float
    max: float
    count: int
    probability: float
    density: float
    index: int
    sum: float


class SummaryStatsRecord(BaseModel):
    """Statistical summary of data."""
    mean: float
    min: float
    max: float
    stdDev: float
    skewness: float
    kurtosis: float
    minTime: float
    maxTime: float


class Histogram1DRecord(BaseModel):
    """Represents the data of a univariate histogram."""
    XIncr: float
    XMax: float
    XMin: float
    bins: List[Bin1D] = Field(alias='frequencyBins')
    statistics: SummaryStatsRecord = Field(alias='summaryStats')


class Bin2D(BaseModel):
    """Represents a single bin in a 2D histogram."""
    xBinSize: float
    yBinSize: float
    xMin: float
    xMax: float
    yMin: float
    yMax: float
    count: int
    probability: float
    density: float


class TemporalUnivariateHistogram(BaseModel):
    """Represents the temporal univariate histogram."""
    matrix: List[List[Bin2D]]
    stats: List[SummaryStatsRecord]


class ProbabilityServiceAPIClient:
    """Methods for interacting with the Probability Service API."""

    def __init__(self, api_auth: APIAuth):
        """
        Initializes the ProbabilityServiceAPIClient with the provided API authentication.

        Args:
            api_auth (APIAuth): An instance of APIAuth containing authentication details.
        """
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def get_univariate_histogram(
            self,
            macs: List[int],
            sensor_type: int,
            start_time: int,
            end_time: int,
            record_limit: int,
            n_bins: int,
    ) -> Optional[Histogram1DRecord]:
        """
        Generates a univariate histogram of sensor data values within a specified time range.

        Args:
            macs (List[int]): A list of MAC addresses (sensor device identifiers).
            sensor_type (int): The sensor type code.
            start_time (int): The start time in UNIX epoch milliseconds.
            end_time (int): The end time in UNIX epoch milliseconds.
            record_limit (int): The maximum number of records to retrieve.
            n_bins (int): The number of bins to divide the data range into.

        Returns:
            Optional[Histogram1DRecord]: The histogram data or None if the request failed.
        """
        url = self.api_auth.api_config.get_api_url() + "probability/univariatehistogram"
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        params = {
            "type": sensor_type,
            "startTime": start_time,
            "endTime": end_time,
            "recordLimit": record_limit,
            "nBins": n_bins,
        }
        # Add macs as multiple query parameters
        for mac in macs:
            params.setdefault("macs", []).append(mac)

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            print(data)
            histogram = Histogram1DRecord.parse_obj(data)
            return histogram
        else:
            self.logger.warning(
                "Failed to get univariate histogram: " + str(response.status_code)
            )
            return None

    def get_univariate_histogram_density(
            self,
            macs: List[int],
            sensor_type: int,
            X: List[float],
            start_time: int,
            end_time: int,
            record_limit: int,
            n_bins: int,
    ) -> Optional[List[float]]:
        """
        Calculates the density values for specific sensor data values within a specified time range.

        Args:
            macs (List[int]): A list of MAC addresses.
            sensor_type (int): The sensor type code.
            X (List[float]): A list of sensor data values.
            start_time (int): The start time in UNIX epoch milliseconds.
            end_time (int): The end time in UNIX epoch milliseconds.
            record_limit (int): The maximum number of records to retrieve.
            n_bins (int): The number of bins to use in the histogram.

        Returns:
            Optional[List[float]]: A list of density values or None if the request failed.
        """
        url = self.api_auth.api_config.get_api_url() + "probability/univariatehistodensity"
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        params = {
            "type": sensor_type,
            "X": X,
            "startTime": start_time,
            "endTime": end_time,
            "recordLimit": record_limit,
            "nBins": n_bins,
        }
        for mac in macs:
            params.setdefault("macs", []).append(mac)

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            return data  # Should be a list of floats
        else:
            self.logger.warning(
                "Failed to get univariate histogram density: " + str(response.status_code)
            )
            return None

    def get_univariate_histogram_probability(
            self,
            macs: List[int],
            sensor_type: int,
            X: List[float],
            start_time: int,
            end_time: int,
            record_limit: int,
            n_bins: int,
    ) -> Optional[List[float]]:
        """
        Calculates the probability values for specific sensor data values within a specified time range.

        Args:
            macs (List[int]): A list of MAC addresses.
            sensor_type (int): The sensor type code.
            X (List[float]): A list of sensor data values.
            start_time (int): The start time in UNIX epoch milliseconds.
            end_time (int): The end time in UNIX epoch milliseconds.
            record_limit (int): The maximum number of records to retrieve.
            n_bins (int): The number of bins to use in the histogram.

        Returns:
            Optional[List[float]]: A list of probability values or None if the request failed.
        """
        url = self.api_auth.api_config.get_api_url() + "probability/univariatehistoprobability"
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        params = {
            "type": sensor_type,
            "X": X,
            "startTime": start_time,
            "endTime": end_time,
            "recordLimit": record_limit,
            "nBins": n_bins,
        }
        for mac in macs:
            params.setdefault("macs", []).append(mac)

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            return data  # Should be a list of floats
        else:
            self.logger.warning(
                "Failed to get univariate histogram probability: "
                + str(response.status_code)
            )
            return None

    def get_temporal_univariate_histogram(
            self,
            macs: List[int],
            sensor_type: int,
            start_time: int,
            end_time: int,
            record_limit: int,
            n_bins: int,
            range_type: int = 0,
    ) -> Optional[TemporalUnivariateHistogram]:
        """
        Generates a temporal univariate histogram.

        Args:
            macs (List[int]): A list of MAC addresses.
            sensor_type (int): The sensor type code.
            start_time (int): The start time in UNIX epoch milliseconds.
            end_time (int): The end time in UNIX epoch milliseconds.
            record_limit (int): The maximum number of records to retrieve.
            n_bins (int): The number of bins for sensor data values.
            range_type (int): Time interval type (0 for hour of day, 1 for hour of week).

        Returns:
            Optional[TemporalUnivariateHistogram]: The histogram data or None if the request failed.
        """
        url = self.api_auth.api_config.get_api_url() + "probability/temporalunivariatehisto"
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        params = {
            "type": sensor_type,
            "startTime": start_time,
            "endTime": end_time,
            "recordLimit": record_limit,
            "nBins": n_bins,
            "rangeType": range_type,
        }
        for mac in macs:
            params.setdefault("macs", []).append(mac)

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            histogram = TemporalUnivariateHistogram.parse_obj(data)
            return histogram
        else:
            self.logger.warning(
                "Failed to get temporal univariate histogram: " + str(response.status_code)
            )
            return None

    def get_temporal_univariate_histogram_density(
            self,
            macs: List[int],
            sensor_type: int,
            X: List[float],
            Y: List[int],
            start_time: int,
            end_time: int,
            record_limit: int,
            n_bins: int,
            range_type: int = 0,
    ) -> Optional[List[float]]:
        """
        Calculates the density of specific sensor data values at specific timestamps.

        Args:
            macs (List[int]): A list of MAC addresses.
            sensor_type (int): The sensor type code.
            X (List[float]): A list of sensor data values.
            Y (List[int]): A list of timestamps corresponding to the data values in X.
            start_time (int): The start time in UNIX epoch milliseconds.
            end_time (int): The end time in UNIX epoch milliseconds.
            record_limit (int): The maximum number of records to retrieve.
            n_bins (int): The number of bins for sensor data values.
            range_type (int): Time interval type (0 for hour of day, 1 for hour of week).

        Returns:
            Optional[List[float]]: A list of density values or None if the request failed.
        """
        if len(X) != len(Y):
            raise ValueError("X and Y must be of the same length")

        url = (
                self.api_auth.api_config.get_api_url()
                + "probability/temporalunivariatehistodensity"
        )
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        params = {
            "type": sensor_type,
            "X": X,
            "Y": Y,
            "startTime": start_time,
            "endTime": end_time,
            "recordLimit": record_limit,
            "nBins": n_bins,
            "rangeType": range_type,
        }
        for mac in macs:
            params.setdefault("macs", []).append(mac)

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            return data  # Should be a list of floats
        else:
            self.logger.warning(
                "Failed to get temporal univariate histogram density: "
                + str(response.status_code)
            )
            return None

    def get_temporal_univariate_histogram_probability(
            self,
            macs: List[int],
            sensor_type: int,
            X: List[float],
            Y: List[int],
            start_time: int,
            end_time: int,
            record_limit: int,
            n_bins: int,
            range_type: int = 0,
    ) -> Optional[List[float]]:
        """
        Calculates the probability of specific sensor data values occurring at specific timestamps.

        Args:
            macs (List[int]): A list of MAC addresses.
            sensor_type (int): The sensor type code.
            X (List[float]): A list of sensor data values.
            Y (List[int]): A list of timestamps corresponding to the data values in X.
            start_time (int): The start time in UNIX epoch milliseconds.
            end_time (int): The end time in UNIX epoch milliseconds.
            record_limit (int): The maximum number of records to retrieve.
            n_bins (int): The number of bins for sensor data values.
            range_type (int): Time interval type (0 for hour of day, 1 for hour of week).

        Returns:
            Optional[List[float]]: A list of probability values or None if the request failed.
        """
        if len(X) != len(Y):
            raise ValueError("X and Y must be of the same length")

        url = (
                self.api_auth.api_config.get_api_url()
                + "probability/temporalunivariatehistoprobability"
        )
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        params = {
            "type": sensor_type,
            "X": X,
            "Y": Y,
            "startTime": start_time,
            "endTime": end_time,
            "recordLimit": record_limit,
            "nBins": n_bins,
            "rangeType": range_type,
        }
        for mac in macs:
            params.setdefault("macs", []).append(mac)

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            return data  # Should be a list of floats
        else:
            self.logger.warning(
                "Failed to get temporal univariate histogram probability: "
                + str(response.status_code)
            )
            return None

    def get_temporal_univariate_histogram_image(
            self,
            macs: List[int],
            sensor_type: int,
            start_time: int,
            end_time: int,
            record_limit: int,
            n_bins: int,
            range_type: int = 0,
            scale_factor: int = 1,
            palette_choice: int = 1,
    ) -> Optional[bytes]:
        """
        Retrieves a PNG image of the temporal univariate histogram.

        Args:
            macs (List[int]): A list of MAC addresses.
            sensor_type (int): The sensor type code.
            start_time (int): The start time in UNIX epoch milliseconds.
            end_time (int): The end time in UNIX epoch milliseconds.
            record_limit (int): The maximum number of records to retrieve.
            n_bins (int): The number of bins for sensor data values.
            range_type (int): Time interval type (0 for hour of day, 1 for hour of week).
            scale_factor (int): Factor to scale the image size.
            palette_choice (int): Color palette choice for the image.

        Returns:
            Optional[bytes]: The image data as bytes, or None if the request failed.
        """
        url = (
                self.api_auth.api_config.get_api_url()
                + "probability/temporalunivariateimage"
        )
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        params = {
            "type": sensor_type,
            "startTime": start_time,
            "endTime": end_time,
            "recordLimit": record_limit,
            "nBins": n_bins,
            "rangeType": range_type,
            "scaleFactor": scale_factor,
            "paletteChoice": palette_choice,
        }
        for mac in macs:
            params.setdefault("macs", []).append(mac)

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            return response.content
        else:
            self.logger.warning(
                "Failed to get temporal univariate histogram image: "
                + str(response.status_code)
            )
            return None
