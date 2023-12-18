import logging

from requests import PreparedRequest

from auth import APIAuth
import requests
import json

from utils import WebServiceBoolean
from utils import Utils as AretasUtils


class DataClassifier:
    """
    The contract for the DataClassifier
    """

    def __init__(self, self_id: str = None,
                 parent_id: str = None,
                 label: str = None,
                 description: str = None,
                 feature_int: int = -1,
                 regression_target_val: float = 0.00,
                 is_public: bool = False,
                 required_types: list[int] = None):

        self.self_id = self_id
        self.parent_id = parent_id
        self.label = label
        self.description = description
        self.feature_int = feature_int
        self.regression_target_val = regression_target_val
        self.is_public = is_public
        if required_types is not None:
            self.required_types = required_types
        else:
            self.required_types = []

    def set_self_id(self, self_id: str):
        self.self_id = self_id

    def get_self_id(self) -> str:
        return self.self_id

    def set_parent_id(self, parent_id: str):
        self.parent_id = parent_id

    def get_parent_id(self) -> str:
        return self.parent_id

    def set_label(self, label: str):
        self.label = label

    def get_label(self) -> str:
        return self.label

    def set_description(self, description):
        self.description = description

    def get_description(self) -> str:
        return self.description

    def set_feature_int(self, feature_int: int):
        self.feature_int = feature_int

    def get_feature_int(self) -> int:
        return self.feature_int

    def set_regression_target_val(self, regression_target_val: float):
        self.regression_target_val = regression_target_val

    def get_regression_target_val(self) -> float:
        return self.regression_target_val

    def set_is_public(self, is_public: bool):
        self.is_public = is_public

    def get_is_public(self) -> bool:
        return self.is_public

    def set_required_types(self, required_types: list[int]):
        self.required_types = required_types

    def get_required_types(self) -> list[int]:
        return self.required_types

    def to_dict_for_api(self):
        return {
            "id": self.self_id,
            "parentId": self.parent_id,
            "label": self.label,
            "description": self.description,
            "featureInt": self.feature_int,
            "regressionTargetVal": self.regression_target_val,
            "isPublic": self.is_public,
            "requiredTypes": self.required_types
        }


class DataClassifierCRUD:
    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def list(self) -> list[DataClassifier] | None:
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        url = self.api_auth.api_config.get_api_url() + "dataclassifier/list"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content.decode())
            ret = [DataClassifierCRUD.unmarshall_api_json(item) for item in response_content]
            return ret
        else:
            self.logger.warning("Bad response code: " + str(response.status_code))
            return None

    def create(self, data_classifier: DataClassifier) -> WebServiceBoolean | None:

        base_url = self.api_auth.api_config.get_api_url() + "dataclassifier/create"
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }

        json_data = data_classifier.to_dict_for_api()
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

    def delete(self, data_classifier: DataClassifier) -> WebServiceBoolean | None:

        base_url = self.api_auth.api_config.get_api_url() + "dataclassifier/delete"
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }

        json_data = data_classifier.to_dict_for_api()

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

    def edit(self, data_classifier: DataClassifier) -> WebServiceBoolean | None:

        base_url = self.api_auth.api_config.get_api_url() + "dataclassifier/edit"
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }

        json_data = data_classifier.to_dict_for_api()

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

    @staticmethod
    def unmarshall_api_json(api_json) -> DataClassifier | None:
        return DataClassifier(
            self_id=api_json["id"],
            parent_id=api_json['parentId'],
            label=api_json['label'],
            description=api_json['description'],
            feature_int=api_json['featureInt'],
            regression_target_val=api_json['regressionTargetVal'],
            required_types=[int(item) for item in api_json['requiredTypes']]
        )
