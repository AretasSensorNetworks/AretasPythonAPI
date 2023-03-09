from auth import APIAuth
import requests
import json


class DataClassifierCRUD:
    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth

    def list(self):
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        url = self.api_auth.api_config.get_api_url() + "dataclassifier/list"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            response_content = json.loads(response.content.decode())
            return response_content
        else:
            print("Bad response code: " + str(response.status_code))
            return None

    def create(self, data_classifier):
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        url = self.api_auth.api_config.get_api_url() + "dataclassifier/create"
        raise NotImplementedError('Not implemented yet')
        pass

    def delete(self, data_classifier):
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        url = self.api_auth.api_config.get_api_url() + "dataclassifier/delete"
        raise NotImplementedError('Not implemented yet')
        pass

    def edit(self, data_classifier):
        headers = {"Authorization": "Bearer " + self.api_auth.get_token()}
        url = self.api_auth.api_config.get_api_url() + "dataclassifier/edit"
        raise NotImplementedError('Not implemented yet')
        pass

