import logging
from auth import APIAuth
import requests
from requests.models import PreparedRequest
import json
from typing import List, Optional

from entities import Alert, WebServiceBoolean
from utils import Utils


class AlertService:
    """
    Use this class for managing alerts via the API (CRUD operations)
    Implements the same functionality as com.pyropath.air.server.webservice.AlertService
    """

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def refresh_token(self):
        """Refresh the API token"""
        self.api_auth.refresh_token()

    def list(self) -> Optional[List[Alert]]:
        """
        List all alerts for the authenticated user
        
        :return: List of Alert objects or None if request fails
        """
        url = self.api_auth.api_config.get_api_url() + "alert/list"
        
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token())
        }
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            alerts = []
            json_response = json.loads(response.content.decode())
            
            for alert_data in json_response:
                alert = Alert(**alert_data)
                alerts.append(alert)
            
            return alerts
        elif response.status_code == 401:
            self.logger.warning("Unauthorized - refreshing token and retrying")
            self.refresh_token()
            headers["Authorization"] = "Bearer {}".format(self.api_auth.get_token())
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                alerts = []
                json_response = json.loads(response.content.decode())
                
                for alert_data in json_response:
                    alert = Alert(**alert_data)
                    alerts.append(alert)
                
                return alerts
            else:
                self.logger.error("Failed to list alerts after token refresh: {}".format(response.status_code))
                return None
        else:
            self.logger.error("Failed to list alerts: {}".format(response.status_code))
            return None

    def save(self, alert: Alert) -> WebServiceBoolean:
        """
        Create/save a new alert
        
        :param alert: Alert object to save
        :return: WebServiceBoolean indicating success/failure
        """
        url = self.api_auth.api_config.get_api_url() + "alert/save"
        
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }
        
        # Convert Alert object to dict for JSON serialization
        alert_dict = alert.model_dump(exclude_none=True)
        
        response = requests.post(url, headers=headers, json=alert_dict)
        
        if response.status_code == 200:
            json_response = json.loads(response.content.decode())
            return Utils.unmarshall_webservice_bool(json_response)
        elif response.status_code == 401:
            self.logger.warning("Unauthorized - refreshing token and retrying")
            self.refresh_token()
            headers["Authorization"] = "Bearer {}".format(self.api_auth.get_token())
            response = requests.post(url, headers=headers, json=alert_dict)
            
            if response.status_code == 200:
                json_response = json.loads(response.content.decode())
                return Utils.unmarshall_webservice_bool(json_response)
            else:
                self.logger.error("Failed to save alert after token refresh: {}".format(response.status_code))
                return WebServiceBoolean(False, "Failed to save alert after token refresh")
        else:
            self.logger.error("Failed to save alert: {}".format(response.status_code))
            return WebServiceBoolean(False, "Failed to save alert")

    def update(self, alert: Alert) -> WebServiceBoolean:
        """
        Update an existing alert
        
        :param alert: Alert object to update
        :return: WebServiceBoolean indicating success/failure
        """
        url = self.api_auth.api_config.get_api_url() + "alert/update"
        
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }
        
        # Convert Alert object to dict for JSON serialization
        alert_dict = alert.model_dump(exclude_none=True)
        
        response = requests.post(url, headers=headers, json=alert_dict)
        
        if response.status_code == 200:
            json_response = json.loads(response.content.decode())
            return Utils.unmarshall_webservice_bool(json_response)
        elif response.status_code == 401:
            self.logger.warning("Unauthorized - refreshing token and retrying")
            self.refresh_token()
            headers["Authorization"] = "Bearer {}".format(self.api_auth.get_token())
            response = requests.post(url, headers=headers, json=alert_dict)
            
            if response.status_code == 200:
                json_response = json.loads(response.content.decode())
                return Utils.unmarshall_webservice_bool(json_response)
            else:
                self.logger.error("Failed to update alert after token refresh: {}".format(response.status_code))
                return WebServiceBoolean(False, "Failed to update alert after token refresh")
        else:
            self.logger.error("Failed to update alert: {}".format(response.status_code))
            return WebServiceBoolean(False, "Failed to update alert")

    def remove(self, alert: Alert) -> WebServiceBoolean:
        """
        Remove/delete an alert
        
        :param alert: Alert object to remove
        :return: WebServiceBoolean indicating success/failure
        """
        url = self.api_auth.api_config.get_api_url() + "alert/remove"
        
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }
        
        # Convert Alert object to dict for JSON serialization
        alert_dict = alert.model_dump(exclude_none=True)
        
        response = requests.post(url, headers=headers, json=alert_dict)
        
        if response.status_code == 200:
            json_response = json.loads(response.content.decode())
            return Utils.unmarshall_webservice_bool(json_response)
        elif response.status_code == 401:
            self.logger.warning("Unauthorized - refreshing token and retrying")
            self.refresh_token()
            headers["Authorization"] = "Bearer {}".format(self.api_auth.get_token())
            response = requests.post(url, headers=headers, json=alert_dict)
            
            if response.status_code == 200:
                json_response = json.loads(response.content.decode())
                return Utils.unmarshall_webservice_bool(json_response)
            else:
                self.logger.error("Failed to remove alert after token refresh: {}".format(response.status_code))
                return WebServiceBoolean(False, "Failed to remove alert after token refresh")
        else:
            self.logger.error("Failed to remove alert: {}".format(response.status_code))
            return WebServiceBoolean(False, "Failed to remove alert")

    def print_config(self):
        """Print the API configuration URL"""
        print(self.api_auth.api_config.get_api_url())