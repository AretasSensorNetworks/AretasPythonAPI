import requests
from .api_config import APIConfig


class APIAuth:

    def __init__(self, config_obj: APIConfig):

        self.API_TOKEN = None
        self.api_config = config_obj
        pass

    def test_token(self):
        """test if the token is valid"""
        api_response = requests.get(self.api_config.get_api_url() + "greetings/isloggedin",
                                    headers={"Authorization": "Bearer " + self.API_TOKEN})

        if api_response.status_code == 401 or 403:
            return False
        else:
            return True

    def refresh_token(self):
        """refresh the access token"""
        # basic function to get an access token
        api_response = requests.get(
            self.api_config.get_api_url() + "authentication/g?username=" + self.api_config.get_api_username() + "&password=" + self.api_config.get_api_password())

        if api_response.status_code >= 200:
            self.API_TOKEN = api_response.content.decode()

            return self.API_TOKEN
        else:
            return None

    def get_token(self, refresh_if_expired=False):
        """get the access token for the API
        :param refresh_if_expired: check if the token has expired (makes at least one extra call to the API)
        :return:
        """
        if refresh_if_expired and self.test_token() is False:
            return self.refresh_token()

        if self.API_TOKEN is None:
            # try and get one
            return self.refresh_token()
        else:
            return self.API_TOKEN


