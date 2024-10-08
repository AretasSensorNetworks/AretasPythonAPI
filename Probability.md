# Probability Service API Documentation

Welcome to the Probability Service API documentation. This service provides endpoints for generating and querying histograms based on sensor data over time. It allows users to:

- Generate univariate histograms of sensor data.
- Calculate the probability and density of specific sensor values.
- Generate temporal univariate histograms to analyze how sensor data changes over time.
- Retrieve probability and density values at specific times.
- Visualize histograms as images.

## Table of Contents

- [Getting Started](#getting-started)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Get Univariate Histogram](#get-univariate-histogram)
  - [Get Univariate Histogram Density](#get-univariate-histogram-density)
  - [Get Univariate Histogram Probability](#get-univariate-histogram-probability)
  - [Get Temporal Univariate Histogram](#get-temporal-univariate-histogram)
  - [Get Temporal Univariate Histogram Density](#get-temporal-univariate-histogram-density)
  - [Get Temporal Univariate Histogram Probability](#get-temporal-univariate-histogram-probability)
  - [Get Temporal Univariate Histogram Image](#get-temporal-univariate-histogram-image)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Examples](#examples)

## Getting Started

To use this API, you need to have an account and valid authentication credentials. Ensure that you have the necessary permissions to access the MAC addresses (sensor devices) you intend to query.

## Authentication

All endpoints require authentication using security tokens. Include your authentication token in the `Authorization` header of your HTTP requests.

Example:

```
Authorization: Bearer YOUR_ACCESS_TOKEN
```

## Endpoints

### Get Univariate Histogram

**Endpoint:**

```
GET /probability/univariatehistogram
```

**Description:**

Generates a univariate histogram of sensor data values within a specified time range.

**Parameters:**

- **macs** (`List<Long>`, Required):  
  A list of MAC addresses (sensor device identifiers) for which you want to generate the histogram.

- **type** (`int`, Required):  
  The sensor type (e.g., temperature, humidity). Use the appropriate integer code representing the sensor type.

- **startTime** (`long`, Required):  
  The start time for the data query in UNIX epoch milliseconds.

- **endTime** (`long`, Required):  
  The end time for the data query in UNIX epoch milliseconds.

- **recordLimit** (`int`, Optional):  
  The maximum number of records to retrieve. Use `0` or omit for no limit.

- **nBins** (`int`, Required):  
  The number of bins to divide the data range into for the histogram.

**Response:**

Returns a `Histogram1DRecord` object containing histogram data.

**Usage:**

Use this endpoint to understand the distribution of sensor data values over a specified period.

---

### Get Univariate Histogram Density

**Endpoint:**

```
GET /probability/univariatehistodensity
```

**Description:**

Calculates the density values for specific sensor data values (`X`) within a specified time range.

**Parameters:**

- **macs** (`List<Long>`, Required):  
  A list of MAC addresses for which you want to calculate density.

- **type** (`int`, Required):  
  The sensor type.

- **X** (`List<Double>`, Required):  
  A list of sensor data values for which you want to calculate the density.

- **startTime** (`long`, Required):  
  The start time in UNIX epoch milliseconds.

- **endTime** (`long`, Required):  
  The end time in UNIX epoch milliseconds.

- **recordLimit** (`int`, Optional):  
  The maximum number of records to retrieve.

- **nBins** (`int`, Required):  
  The number of bins to use in the histogram.

**Response:**

Returns a list of density values corresponding to each `X` value provided.

**Usage:**

Use this endpoint to find out how dense (frequent) specific sensor readings are within a dataset.

---

### Get Univariate Histogram Probability

**Endpoint:**

```
GET /probability/univariatehistoprobability
```

**Description:**

Calculates the probability values for specific sensor data values (`X`) within a specified time range.

**Parameters:**

Same as **Get Univariate Histogram Density**.

**Response:**

Returns a list of probability values corresponding to each `X` value provided.

**Usage:**

Use this endpoint to determine the likelihood of specific sensor readings occurring within a dataset.

---

### Get Temporal Univariate Histogram

**Endpoint:**

```
GET /probability/temporalunivariatehisto
```

**Description:**

Generates a temporal univariate histogram, which represents the distribution of sensor data over time. This histogram helps visualize how sensor values change over different time intervals.

**Parameters:**

- **macs** (`List<Long>`, Required):  
  List of MAC addresses to include in the histogram.

- **type** (`int`, Required):  
  Sensor type.

- **startTime** (`long`, Required):  
  Start time in UNIX epoch milliseconds.

- **endTime** (`long`, Required):  
  End time in UNIX epoch milliseconds.

- **recordLimit** (`int`, Optional):  
  Maximum number of records to retrieve.

- **nBins** (`int`, Required):  
  Number of bins for sensor data values.

- **rangeType** (`int`, Optional, Default: `0`):  
  Specifies the time interval for the histogram:
  - `0`: Hour of Day (24-hour bins)
  - `1`: Hour of Week (168-hour bins)

**Response:**

Returns a `TemporalUnivariateHistogram` object containing the histogram matrix and statistical summaries.

**Usage:**

Use this endpoint to analyze patterns and trends in sensor data over time, such as daily or weekly cycles.

---

### Get Temporal Univariate Histogram Density

**Endpoint:**

```
GET /probability/temporalunivariatehistodensity
```

**Description:**

Calculates the density of specific sensor data values (`X`) at specific timestamps (`Y`).

**Parameters:**

- **macs** (`List<Long>`, Required):  
  List of MAC addresses.

- **type** (`int`, Required):  
  Sensor type.

- **X** (`List<Double>`, Required):  
  List of sensor data values.

- **Y** (`List<Long>`, Required):  
  List of timestamps (UNIX epoch milliseconds). Each timestamp corresponds to a data value in `X`.

- **startTime** (`long`, Required):  
  Start time for data retrieval.

- **endTime** (`long`, Required):  
  End time for data retrieval.

- **recordLimit** (`int`, Optional):  
  Maximum number of records to retrieve.

- **nBins** (`int`, Required):  
  Number of bins for sensor data values.

- **rangeType** (`int`, Optional, Default: `0`):  
  Time interval type:
  - `0`: Hour of Day
  - `1`: Hour of Week

**Response:**

Returns a list of density values corresponding to each (`X`, `Y`) pair.

**Usage:**

Use this endpoint to assess how concentrated sensor readings are at specific times.

---

### Get Temporal Univariate Histogram Probability

**Endpoint:**

```
GET /probability/temporalunivariatehistoprobability
```

**Description:**

Calculates the probability of specific sensor data values (`X`) occurring at specific timestamps (`Y`).

**Parameters:**

Same as **Get Temporal Univariate Histogram Density**.

**Response:**

Returns a list of probability values corresponding to each (`X`, `Y`) pair.

**Usage:**

Use this endpoint to determine the likelihood of specific sensor readings occurring at particular times.

---

### Get Temporal Univariate Histogram Image

**Endpoint:**

```
GET /probability/temporalunivariateimage
```

**Description:**

Generates a visual representation (PNG image) of the temporal univariate histogram.

**Parameters:**

- **macs** (`List<Long>`, Required):  
  List of MAC addresses.

- **type** (`int`, Required):  
  Sensor type.

- **startTime** (`long`, Required):  
  Start time.

- **endTime** (`long`, Required):  
  End time.

- **recordLimit** (`int`, Optional):  
  Maximum number of records.

- **nBins** (`int`, Required):  
  Number of bins for sensor data values.

- **rangeType** (`int`, Optional, Default: `0`):  
  Time interval type:
  - `0`: Hour of Day
  - `1`: Hour of Week

- **scaleFactor** (`int`, Optional, Default: `1`):  
  Factor to scale the image size.

- **paletteChoice** (`int`, Optional, Default: `1`):  
  Color palette choice for the image.

**Response:**

Returns a PNG image of the histogram.

**Usage:**

Use this endpoint to visualize the distribution of sensor data over time.

---

## Data Models

### Histogram1DRecord

Represents the data of a univariate histogram.

- **bins** (`List<Bin>`):  
  List of bins in the histogram.

- **statistics** (`SummaryStatsRecord`):  
  Statistical summary of the data.

### TemporalUnivariateHistogram

Represents the temporal univariate histogram.

- **matrix** (`Bin2D[][]`):  
  2D array of `Bin2D` objects representing the histogram matrix.

- **stats** (`SummaryStatsRecord[]`):  
  Array of statistical summaries for each time bin.

### Bin

Represents a single bin in a histogram.

- **min** (`double`):  
  Minimum value of the bin range.

- **max** (`double`):  
  Maximum value of the bin range.

- **count** (`int`):  
  Number of data points in the bin.

- **probability** (`double`):  
  Probability of data points falling into this bin.

- **density** (`double`):  
  Density of data points in this bin.

### Bin2D

Represents a single bin in a 2D histogram.

- **XMin** (`double`):  
  Minimum value of the time range.

- **XMax** (`double`):  
  Maximum value of the time range.

- **YMin** (`double`):  
  Minimum value of the data value range.

- **YMax** (`double`):  
  Maximum value of the data value range.

- **count** (`int`):  
  Number of data points in the bin.

- **probability** (`double`):  
  Probability of data points falling into this bin.

- **density** (`double`):  
  Density of data points in this bin.

### SummaryStatsRecord

Statistical summary of data.

- **mean** (`double`):  
  Mean of the data.

- **min** (`double`):  
  Minimum value.

- **max** (`double`):  
  Maximum value.

- **stdDev** (`double`):  
  Standard deviation.

- **skewness** (`double`):  
  Skewness of the data.

- **kurtosis** (`double`):  
  Kurtosis of the data.

## Error Handling

The API may return the following HTTP status codes:

- **200 OK**: Request was successful.
- **400 Bad Request**: Invalid request parameters.
- **401 Unauthorized**: Authentication failed or user does not own the specified MAC addresses.
- **500 Internal Server Error**: An unexpected error occurred on the server.

## Examples

### Example 1: Get Univariate Histogram

**Request:**

```
GET /probability/univariatehistogram?macs=12345&macs=67890&type=1&startTime=1633046400000&endTime=1633132800000&nBins=50
Authorization: Bearer YOUR_ACCESS_TOKEN
```

**Response:**

```json
{
  "bins": [
    {
      "min": 0.0,
      "max": 2.0,
      "count": 10,
      "probability": 0.02,
      "density": 0.005
    },
    ...
  ],
  "statistics": {
    "mean": 25.5,
    "min": 0.0,
    "max": 50.0,
    "stdDev": 14.43,
    "skewness": 0.0,
    "kurtosis": -1.2
  }
}
```

### Example 2: Get Temporal Univariate Histogram Density

**Request:**

```
GET /probability/temporalunivariatehistodensity?macs=12345&type=1&X=25.0&Y=1633089600000&X=30.0&Y=1633093200000&startTime=1633046400000&endTime=1633132800000&nBins=50&rangeType=0
Authorization: Bearer YOUR_ACCESS_TOKEN
```

**Response:**

```json
[0.003, 0.0045]
```

### Example 3: Get Temporal Univariate Histogram Image

**Request:**

```
GET /probability/temporalunivariateimage?macs=12345&type=1&startTime=1633046400000&endTime=1633132800000&nBins=50&rangeType=0&scaleFactor=2&paletteChoice=1
Authorization: Bearer YOUR_ACCESS_TOKEN
```

**Response:**

Returns a PNG image of the histogram.

---

## Notes

- **Time Parameters**: All time-related parameters should be provided in UNIX epoch milliseconds.
- **MAC Addresses**: Ensure you have permission to access the specified MAC addresses.
- **Data Privacy**: Be mindful of data privacy and compliance regulations when handling sensor data.
- **Authentication**: Always include a valid authentication token in your requests.

## Contact

For support or questions, please contact our support team at [team-aretas@aretas.ca](mailto:team-aretas@aretas.ca).

---

Thank you for using the Probability Service API!