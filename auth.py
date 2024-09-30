import logging
import requests
import requests.utils as r_utils
from api_config import APIConfig


class APIAuth:
    def __init__(self, config_obj: APIConfig, token: str = None):
        """
        Initialize the APIAuth object.

        :param config_obj: An instance of APIConfig containing API configuration.
        :param token: Optional; an existing API token to use. If provided, the class will not attempt to refresh the token.
        """
        self.API_TOKEN = token
        self.api_config = config_obj
        self.logger = logging.getLogger(__name__)
        self._token_provided = token is not None

    def test_token(self) -> bool:
        """
        Test if the current API token is valid.

        :return: True if the token is valid, False otherwise.
        """
        if self.API_TOKEN is None:
            return False
        api_response = requests.get(
            self.api_config.get_api_url() + "greetings/isloggedin",
            headers={"Authorization": "Bearer " + self.API_TOKEN}
        )

        if api_response.status_code in (401, 403):
            return False
        else:
            return True

    def refresh_token(self) -> str | None:
        """
        Refresh the access token by authenticating with the API using username and password.

        :return: The new API token as a string if successful, None otherwise.
        """
        # Build the authentication URI
        uri = "{0}authentication/g?username={1}&password={2}".format(
            self.api_config.get_api_url(),
            self.api_config.get_api_username(),
            self.api_config.get_api_password()
        )
        uri = r_utils.requote_uri(uri)
        api_response = requests.get(uri)

        if api_response.status_code in (401, 403):
            self.logger.error("Could not get an access token from the API. Response code was: {}"
                              .format(api_response.status_code))
            return None
        elif api_response.status_code >= 200:
            self.API_TOKEN = api_response.content.decode()
            return self.API_TOKEN
        else:
            return None

    def get_token(self, refresh_if_expired=False) -> str | None:
        """
        Get the access token for the API.

        If a token was provided during initialization, this method will return that token and will not attempt
        to refresh it.

        :param refresh_if_expired: Boolean indicating whether to check if the token has expired (makes an extra API call).
        :return: The API token as a string.
        """
        if self._token_provided:
            if self.API_TOKEN is None:
                self.logger.error("No API token available.")
                return None
            return self.API_TOKEN

        if refresh_if_expired and not self.test_token():
            return self.refresh_token()

        if self.API_TOKEN is None:
            # Try to get a new token
            return self.refresh_token()
        else:
            return self.API_TOKEN
