import json
import logging

import requests
from requests import PreparedRequest

from auth import APIAuth
from utils import Utils as AretasUtils, WebServiceBoolean


class DataClassifierRecord:
    """
    The contract for the DataClassifierRecord
    """

    def __init__(self, self_id: str = None,
                 data_classifier_id: str = None,
                 start_timestamp: int = None,
                 end_timestamp: int = None,
                 assoc_macs: list[int] = None,
                 target_types: list[int] = None,
                 regression_value: float = None):

        self.self_id = self_id
        self.data_classifier_id = data_classifier_id

        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp

        if assoc_macs is not None:
            self.assoc_macs = assoc_macs
        else:
            self.assoc_macs = []

        if target_types is not None:
            self.target_types = target_types
        else:
            self.target_types = []

        self.regression_value = regression_value

    def __repr__(self):
        return "Id:{} DataClassifierId:{} Start:{}ms End:{}ms Assoc macs:{} types:{} regression value:{}".format(
            self.get_self_id(),
            self.get_data_classifier_id(),
            self.get_start_timestamp(),
            self.get_end_timestamp(),
            self.get_assoc_macs(),
            self.get_target_types(),
            self.get_regression_value()
        )

    def set_self_id(self, self_id: str):
        """
        The ID set during creation is ignored
        The API will set the ID when the record is created and return it with subsequent queries
        """
        self.self_id = self_id

    def get_self_id(self) -> str:
        return self.self_id

    def set_data_classifier_id(self, data_classifier_id: str):
        self.data_classifier_id = data_classifier_id

    def get_data_classifier_id(self) -> str:
        return self.data_classifier_id

    def set_start_timestamp(self, start_timestamp: int):
        self.start_timestamp = start_timestamp

    def get_start_timestamp(self) -> int:
        return self.start_timestamp

    def set_end_timestamp(self, end_timestamp: int):
        self.end_timestamp = end_timestamp

    def get_end_timestamp(self) -> int:
        return self.end_timestamp

    def set_assoc_macs(self, assoc_macs: list[int]):
        self.assoc_macs = assoc_macs

    def get_assoc_macs(self) -> list[int]:
        return self.assoc_macs

    def set_target_types(self, target_types: list[int]):
        self.target_types = target_types

    def get_target_types(self) -> list[int]:
        return self.target_types

    def set_regression_value(self, regression_value: float):
        self.regression_value = regression_value

    def get_regression_value(self) -> float:
        return self.regression_value

    def to_dict_for_api(self) -> dict:
        """
        The webservice POJO field serializations / implementations are slightly different
        due to preference for camelcase in Java vars
        """
        ret = {
            "id": self.self_id,
            "dataClassifierId": self.data_classifier_id,
            "startTimestamp": self.start_timestamp,
            "endTimestamp": self.end_timestamp,
            "assocMacs": self.assoc_macs,
            "targetTypes": self.target_types,
            "regressionValue": self.regression_value
        }

        return ret


class DataClassifierRecordCRUD:

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def save(self, record: DataClassifierRecord) -> WebServiceBoolean | None:
        """
        Synonym for the REST API verb 'save'
        Create a new DataClassifierRecord
        """
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }
        base_url = self.api_auth.api_config.get_api_url() + "dataclassifierrecord/save"

        json_data = record.to_dict_for_api()
        del json_data['id']

        params = {}

        req = PreparedRequest()
        req.prepare_url(base_url, params)

        response = requests.post(req.url, headers=headers, json=json_data)

        if response.status_code == 200:
            response_content = json.loads(response.content.decode())
            return AretasUtils.unmarshall_webservice_bool(response_content)
        else:
            self.logger.warning("Bad response code: " + str(response.status_code))
            return None

    def remove(self, record: DataClassifierRecord) -> WebServiceBoolean | None:
        """
        Synonym for the REST API verb 'delete'.
        Delete an existing DataClassifierRecord
        """
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }
        base_url = self.api_auth.api_config.get_api_url() + "dataclassifierrecord/delete"

        json_data = record.to_dict_for_api()

        params = {}

        req = PreparedRequest()
        req.prepare_url(base_url, params)

        response = requests.post(req.url, headers=headers, json=json_data)

        if response.status_code == 200:
            response_content = json.loads(response.content.decode())
            return AretasUtils.unmarshall_webservice_bool(response_content)
        else:
            self.logger.warning("Bad response code: " + str(response.status_code))
            return None

    def purge(self, data_classifier_id: str) -> WebServiceBoolean | None:
        """
        Purge all the records relating to a particular classifier ID
        """
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }
        base_url = self.api_auth.api_config.get_api_url() + "dataclassifierrecord/purge"

        params = {
            "dataClassifierId": data_classifier_id
        }

        req = PreparedRequest()
        req.prepare_url(base_url, params)

        response = requests.get(req.url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content.decode())
            return AretasUtils.unmarshall_webservice_bool(response_content)
        else:
            self.logger.warning("Bad response code: " + str(response.status_code))
            return None

    def get_by_id(self, data_classifier_id: str) -> list[DataClassifierRecord] | None:
        """
        Synonym for the REST API endpoint 'get/byid'
        Get all the data_classifier_records for a particular ID
        """
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        base_url = self.api_auth.api_config.get_api_url() + "dataclassifierrecord/get/byid"

        params = {
            'dataClassifierId': data_classifier_id,
        }

        req = PreparedRequest()
        req.prepare_url(base_url, params)

        response = requests.get(req.url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content.decode())
            return [DataClassifierRecordCRUD.unmarshall_api_json(item) for item in response_content]
        else:
            self.logger.warning("Bad response code: " + str(response.status_code))
            return None

    def get_by_mac_timestamp(self,
                             macs: list[int],
                             start_time_ms: int,
                             end_time_ms: int,
                             record_limit: int = 200000) -> list[DataClassifierRecord]:
        """
        Synonym for the REST API endpoint 'get/bymactimestamp'
        Query for dataclassifier records belonging to certain macs over certain timeframes
        """
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        base_url = self.api_auth.api_config.get_api_url() + "dataclassifierrecord/get/bymactimestamp"

        params = {
            'macs': macs,
            "startTimeMs": start_time_ms,
            "endTimeMs": end_time_ms,
            "recordLimit": record_limit,
        }

        req = PreparedRequest()
        req.prepare_url(base_url, params)

        response = requests.get(req.url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content.decode())
            ret = [DataClassifierRecordCRUD.unmarshall_api_json(item) for item in response_content]
            return ret
        else:
            self.logger.warning("Bad response code: " + str(response.status_code))
            return None
        pass

    @staticmethod
    def unmarshall_api_json(api_dict: dict) -> DataClassifierRecord:
        """
        Unmarshall a DataClassifierRecord from the API

        The API fields are:
        "id": self.self_id,
        "dataClassifierId": self.data_classifier_id,
        "startTimestamp": self.start_timestamp,
        "endTimestamp": self.end_timestamp,
        "assocMacs": self.assoc_macs,
        "targetTypes": self.target_types,
        "regressionValue": self.regression_value
        """
        return DataClassifierRecord(
            self_id=api_dict['id'],
            data_classifier_id=api_dict['dataClassifierId'],
            start_timestamp=api_dict['startTimestamp'],
            end_timestamp=api_dict['endTimestamp'],
            assoc_macs=[int(i) for i in api_dict['assocMacs']],
            target_types=[int(i) for i in api_dict['targetTypes']],
            regression_value=float(api_dict['regressionValue'])
        )
