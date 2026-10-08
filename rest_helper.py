import logging
from typing import Optional

import requests

from auth import APIAuth
from entities import WebServiceBoolean
from utils import Utils

logger = logging.getLogger(__name__)


def authed_request(api_auth: APIAuth, method: str, path: str, params: Optional[dict] = None,
                   json_body=None, timeout: int = 30) -> requests.Response:
    """
    Perform an authenticated request against the API, refreshing the token and
    retrying once if the first attempt is rejected with a 401

    :param api_auth: APIAuth instance providing the bearer token
    :param method: HTTP method ("GET" or "POST")
    :param path: path relative to the configured API URL, e.g. "alert/list"
    :param params: optional query parameters
    :param json_body: optional JSON-serializable request body
    :param timeout: request timeout in seconds
    :return: the requests.Response of the final attempt
    """
    url = api_auth.api_config.get_api_url() + path

    def _do(token: str) -> requests.Response:
        headers = {"Authorization": "Bearer {}".format(token)}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        return requests.request(method, url, headers=headers, params=params, json=json_body, timeout=timeout)

    response = _do(api_auth.get_token() or "")

    if response.status_code == 401:
        logger.warning("Unauthorized on {} - refreshing token and retrying".format(path))
        api_auth.refresh_token()
        response = _do(api_auth.get_token() or "")

    return response


def ws_bool_from_response(response: requests.Response, failure_message: str) -> WebServiceBoolean:
    """
    Convert a response carrying a {booleanResponse, message} body into a WebServiceBoolean.
    Non-200 responses become a failed WebServiceBoolean carrying the status code and body.

    :param response: the HTTP response
    :param failure_message: message prefix used when the response is not 200
    :return: WebServiceBoolean
    """
    if response.status_code == 200:
        return Utils.unmarshall_webservice_bool(response.json())

    logger.error("{}: HTTP {} {}".format(failure_message, response.status_code, response.text[:200]))
    return WebServiceBoolean(False, "{} (HTTP {}): {}".format(failure_message, response.status_code,
                                                               response.text[:200]))
