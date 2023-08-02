from auth import APIAuth
import requests
from requests.models import PreparedRequest
import json


class Probability:
    """
    Use this class for querying probability endpoints (univariate histograms, probabilities, etc)
    There are many additional options for these queries, so see the function docs
    """

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
