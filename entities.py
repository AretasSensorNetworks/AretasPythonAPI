from dataclasses import dataclass
from typing import List, Optional
from pydantic import BaseModel


class AlertHistoryRecord(BaseModel):
    eventId: int
    mac: int
    timestamp: int
    rtnTimestamp: int
    sensorType: int
    sensorData: float
    alertId: str
    monitorLocation: Optional[str] = None
    monitorDescription: Optional[str] = None
    isNew: bool
    isDismissed: bool
    isResolved: bool


class Alert(BaseModel):
    name: Optional[str] = None
    id: str
    owner: Optional[str] = None
    description: Optional[str] = None
    sensorType: int
    sensorMacs: Optional[str] = None
    backToNormalCommand: Optional[str] = None
    thresholdBEndTime: Optional[float] = None
    thresholdBStartTime: Optional[float] = None
    alertEmails: Optional[str] = None
    durationTrigger: Optional[int] = None
    alertSMSes: Optional[str] = None
    alertTriggerTTL: Optional[int] = None
    alertFrequency: Optional[int] = None
    revision: Optional[str] = None
    maxNumAlerts: Optional[int] = None
    thresholdB: Optional[float] = None
    controlStrategy: Optional[bool] = None
    thresholdA: Optional[float] = None
    thresholdAType: Optional[bool] = None
    thresholdBType: Optional[bool] = None
    disabled: Optional[bool] = None
    exceededCommand: Optional[str] = None


@dataclass
class Status:
    mac: str
    status: str
    timestamp: str
    type: str

    @staticmethod
    def from_dict(data):
        return Status(
            mac=data.get('_mac', ''),
            status=data.get('_status', ''),
            timestamp=data.get('_timestamp', ''),
            type=data.get('_type', '')
        )


@dataclass
class AreaUsageHints:
    ceilingHeight: int
    floorArea: int
    hasOpeningWindows: int
    hasPeople: int
    occupantCountHint: int

    @staticmethod
    def from_dict(data):
        return AreaUsageHints(
            ceilingHeight=data.get('ceilingHeight', -1),
            floorArea=data.get('floorArea', -1),
            hasOpeningWindows=data.get('hasOpeningWindows', -1),
            hasPeople=data.get('hasPeople', -1),
            occupantCountHint=data.get('occupantCountHint', -1)
        )


@dataclass
class Sensor:
    areaType: int
    areaUsageHints: AreaUsageHints
    buildingMapId: Optional[str]
    description: str
    downInterval: int
    id: str
    imgMapX: int
    imgMapY: int
    isShared: bool
    isSharedPublic: bool
    lastReportTime: int
    lat: float
    lon: float
    mac: int
    notifyIfDown: bool
    owner: str
    ownerClientId: str
    status: Status

    @staticmethod
    def from_dict(data):
        return Sensor(
            areaType=data.get('areaType', 0),
            areaUsageHints=AreaUsageHints.from_dict(data.get('areaUsageHints', {})),
            buildingMapId=data.get('buildingMapId'),
            description=data.get('description', ''),
            downInterval=data.get('downInterval', 0),
            id=data.get('id', ''),
            imgMapX=data.get('imgMapX', 0),
            imgMapY=data.get('imgMapY', 0),
            isShared=data.get('isShared', False),
            isSharedPublic=data.get('isSharedPublic', False),
            lastReportTime=data.get('lastReportTime', 0),
            lat=data.get('lat', 0.0),
            lon=data.get('lon', 0.0),
            mac=data.get('mac', 0),
            notifyIfDown=data.get('notifyIfDown', False),
            owner=data.get('owner', ''),
            ownerClientId=data.get('ownerClientId', ''),
            status=Status.from_dict(data.get('status', {}))
        )


@dataclass
class Location:
    city: str
    country: str
    description: str
    id: str
    lat: float
    lon: float
    owner: str
    state: str
    streetAddress: str
    zipCode: str

    @staticmethod
    def from_dict(data):
        return Location(
            city=data.get('city', ''),
            country=data.get('country', ''),
            description=data.get('description', ''),
            id=data.get('id', ''),
            lat=data.get('lat', 0.0),
            lon=data.get('lon', 0.0),
            owner=data.get('owner', ''),
            state=data.get('state', ''),
            streetAddress=data.get('streetAddress', ''),
            zipCode=data.get('zipCode', '')
        )


@dataclass
class BuildingMap:
    actualDepth: int
    actualHeight: int
    actualWidth: int
    computedHeight: int
    computedWidth: int
    description: str
    id: str
    mimeType: str
    name: str
    offsetX: int
    offsetY: int
    offsetZ: int
    owner: str
    ownerClientId: str

    @staticmethod
    def from_dict(data):
        return BuildingMap(
            actualDepth=data.get('actualDepth', 0),
            actualHeight=data.get('actualHeight', 0),
            actualWidth=data.get('actualWidth', 0),
            computedHeight=data.get('computedHeight', 0),
            computedWidth=data.get('computedWidth', 0),
            description=data.get('description', ''),
            id=data.get('id', ''),
            mimeType=data.get('mimeType', ''),
            name=data.get('name', ''),
            offsetX=data.get('offsetX', 0),
            offsetY=data.get('offsetY', 0),
            offsetZ=data.get('offsetZ', 0),
            owner=data.get('owner', ''),
            ownerClientId=data.get('ownerClientId', '')
        )

    def to_dict(self) -> dict:
        """
        Converts the BuildingMap object to a dictionary.

        Returns:
            dict: A dictionary representation of the BuildingMap object.
        """
        return {
            "name": self.name,
            "id": self.id,
            "owner": self.owner,
            "mimeType": self.mimeType,
            "description": self.description,
            "ownerClientId": self.ownerClientId,
            "offsetZ": self.offsetZ,
            "offsetY": self.offsetY,
            "offsetX": self.offsetX,
            "computedWidth": self.computedWidth,
            "actualDepth": self.actualDepth,
            "computedHeight": self.computedHeight,
            "actualHeight": self.actualHeight,
            "actualWidth": self.actualWidth
        }


@dataclass
class LocationSensorView:
    buildingMapList: List[BuildingMap]
    lastSensorReportTime: int
    location: Location
    sensorList: List[Sensor]

    @staticmethod
    def from_dict(data):
        buildingMapList = [BuildingMap.from_dict(bm) for bm in data.get('buildingMapList', [])]
        location = Location.from_dict(data.get('location', {}))
        sensorList = [Sensor.from_dict(s) for s in data.get('sensorList', [])]
        return LocationSensorView(
            buildingMapList=buildingMapList,
            lastSensorReportTime=data.get('lastSensorReportTime', -1),
            location=location,
            sensorList=sensorList
        )


@dataclass
class ClientLocationView:
    allMacs: List[int]
    id: str
    locationSensorViews: List[LocationSensorView]

    @staticmethod
    def from_dict(data):
        locationSensorViews = [LocationSensorView.from_dict(lsv) for lsv in data.get('locationSensorViews', [])]
        return ClientLocationView(
            allMacs=data.get('allMacs', []),
            id=data.get('id', ''),
            locationSensorViews=locationSensorViews
        )


class WebServiceBoolean:
    """
    The contract for the WebServiceBoolean from the API
    """

    def __init__(self, boolean_response: bool = None, message: str = None):
        self.boolean_response = boolean_response
        self.message = message

    def __repr__(self):
        return "Response: {} Message: {}".format(self.get_boolean_response(), self.get_message())

    def set_boolean_response(self, boolean_response: bool):
        self.boolean_response = boolean_response

    def get_boolean_response(self) -> bool:
        return self.boolean_response

    def set_message(self, message: str):
        self.message = message

    def get_message(self) -> str:
        return self.message


@dataclass
class SensorBit:
    timestamp: int
    data: float


@dataclass
class SensorDataByType:
    sensor_type: int
    sensor_data: list[SensorBit]


class SensorDatum:
    """
    The contract for a sensor data point from the API
    """

    def __init__(self, mac: int = None, data_type: int = None, timestamp: int = None, data: float = None):
        self.__mac = mac
        self.__data_type = data_type
        self.__timestamp = timestamp
        self.__data = data

    def __repr__(self):
        return "MAC: {} Type:{} Timestamp:{} Data:{}".format(
            self.get_mac(),
            self.get_type(),
            self.get_timestamp(),
            self.get_data()
        )

    def set_mac(self, mac: int):
        self.__mac = mac

    def get_mac(self) -> int:
        return self.__mac

    def set_type(self, data_type: int):
        self.__data_type = data_type

    def get_type(self) -> int:
        return self.__data_type

    def set_timestamp(self, timestamp: int):
        self.__timestamp = timestamp

    def get_timestamp(self) -> int:
        return self.__timestamp

    def set_data(self, data: float):
        self.__data = data

    def get_data(self) -> float:
        return self.__data


@dataclass
class Point:
    """Represents a point with x, y and z coordinates."""
    x: float
    y: float
    z: float

    def to_dict(self) -> dict:
        """
        Converts the Point object to a dictionary.

        Returns:
            dict: A dictionary representation of the Point object.
        """
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Point':
        """
        Creates a Point object from a dictionary.

        Args:
            data (dict): A dictionary containing the Point data.

        Returns:
            Point: An instance of the Point class.
        """
        return cls(x=data.get("x", 0.0), y=data.get("y", 0.0), z=data.get("z", 0.0))


@dataclass
class BasicRectangle:
    """Represents a basic rectangle with x, y coordinates, width, and height."""
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict:
        """
        Converts the BasicRectangle object to a dictionary.

        Returns:
            dict: A dictionary representation of the BasicRectangle object.
        """
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BasicRectangle':
        """
        Creates a BasicRectangle object from a dictionary.

        Args:
            data (dict): A dictionary containing the BasicRectangle data.

        Returns:
            BasicRectangle: An instance of the BasicRectangle class.
        """
        return cls(
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            width=data.get("width", 0.0),
            height=data.get("height", 0.0)
        )


@dataclass
class LocationTag:
    """Represents a location tag based on the provided schema."""
    id: str
    description: Optional[str] = None
    tagId: Optional[int] = None
    rectangle: Optional[BasicRectangle] = None
    buildingMapId: Optional[str] = None
    associatedDeviceId: Optional[str] = None
    tagClassification: Optional[int] = None
    timeoutHint: Optional[int] = None

    def to_dict(self) -> dict:
        """
        Converts the LocationTag object to a dictionary.

        Returns:
            dict: A dictionary representation of the LocationTag object.
        """
        return {
            "id": self.id,
            "description": self.description,
            "tagId": self.tagId,
            "rectangle": self.rectangle.to_dict() if self.rectangle else None,
            "buildingMapId": self.buildingMapId,
            "associatedDeviceId": self.associatedDeviceId,
            "tagClassification": self.tagClassification,
            "timeoutHint": self.timeoutHint
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'LocationTag':
        """
        Creates a LocationTag object from a dictionary.

        Args:
            data (dict): A dictionary containing the LocationTag data.

        Returns:
            LocationTag: An instance of the LocationTag class.
        """
        return cls(
            id=data.get("id", ""),
            description=data.get("description"),
            tagId=data.get("tagId"),
            rectangle=BasicRectangle.from_dict(data["rectangle"]) if data.get("rectangle") else None,
            buildingMapId=data.get("buildingMapId"),
            associatedDeviceId=data.get("associatedDeviceId"),
            tagClassification=data.get("tagClassification"),
            timeoutHint=data.get("timeoutHint")
        )
