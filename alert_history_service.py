import logging
from auth import APIAuth
import requests
from requests.models import PreparedRequest
import json
from typing import List, Optional

from entities import AlertHistoryRecord


class AlertHistoryService:
    """
    Use this class for managing alert history via the API
    Provides functionality to query recent alert history from Redis cache and dismiss alerts
    """

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def refresh_token(self):
        """Refresh the API token"""
        self.api_auth.refresh_token()

    def list_alert_history(self, alert_ids: List[str], show_dismissed: bool = False) -> Optional[List[AlertHistoryRecord]]:
        """
        List alert history by providing a list of alert IDs
        
        :param alert_ids: List of alert IDs to query for
        :param show_dismissed: Whether to include dismissed alerts (default: False)
        :return: List of AlertHistoryRecord objects or None if request fails
        """
        url = self.api_auth.api_config.get_api_url() + "alerthistory/list"
        
        params = {}
        if show_dismissed:
            params['showDismissed'] = 'true'
        
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token()),
            "Content-Type": "application/json"
        }
        
        req = PreparedRequest()
        req.prepare_url(url, params)
        
        response = requests.post(req.url, headers=headers, json=alert_ids)
        
        if response.status_code == 200:
            alert_history_records = []
            json_response = json.loads(response.content.decode())
            
            for record_data in json_response:
                try:
                    # Create AlertHistoryRecord from the response data
                    alert_history_record = AlertHistoryRecord(**record_data)
                    alert_history_records.append(alert_history_record)
                except Exception as e:
                    # Log parsing errors but continue processing other records
                    self.logger.debug(f"Error parsing alert history record: {e}")
                    continue
            
            return alert_history_records
        elif response.status_code == 401:
            self.logger.warning("Unauthorized - refreshing token and retrying")
            self.refresh_token()
            headers["Authorization"] = "Bearer {}".format(self.api_auth.get_token())
            response = requests.post(req.url, headers=headers, json=alert_ids)
            
            if response.status_code == 200:
                alert_history_records = []
                json_response = json.loads(response.content.decode())
                
                for record_data in json_response:
                    try:
                        alert_history_record = AlertHistoryRecord(**record_data)
                        alert_history_records.append(alert_history_record)
                    except Exception as e:
                        self.logger.debug(f"Error parsing alert history record: {e}")
                        continue
                
                return alert_history_records
            else:
                self.logger.error("Failed to list alert history after token refresh: {}".format(response.status_code))
                return None
        else:
            self.logger.error("Failed to list alert history: {}".format(response.status_code))
            return None

    def dismiss_alert_history_object(self, mac: int, sensor_type: int, alert_id: str) -> bool:
        """
        Dismiss an alert history object in the backend ("mark it read")
        
        :param mac: MAC address of the sensor
        :param sensor_type: Type of the sensor
        :param alert_id: ID of the alert
        :return: True if successful, False otherwise
        """
        url = self.api_auth.api_config.get_api_url() + "alerthistory/dismiss"
        
        params = {
            'mac': mac,
            'type': sensor_type,
            'alertId': alert_id
        }
        
        headers = {
            "Authorization": "Bearer {}".format(self.api_auth.get_token())
        }
        
        req = PreparedRequest()
        req.prepare_url(url, params)
        
        self.logger.info(f"Dismissing AlertHistory for mac:{mac} type:{sensor_type} alertId:{alert_id}")
        
        response = requests.get(req.url, headers=headers)
        
        if response.status_code == 200:
            self.logger.info(f"Dismissed AlertHistoryObject mac:{mac} type:{sensor_type} alertId:{alert_id}")
            return True
        elif response.status_code == 401:
            self.logger.warning("Unauthorized - refreshing token and retrying")
            self.refresh_token()
            headers["Authorization"] = "Bearer {}".format(self.api_auth.get_token())
            response = requests.get(req.url, headers=headers)
            
            if response.status_code == 200:
                self.logger.info(f"Dismissed AlertHistoryObject mac:{mac} type:{sensor_type} alertId:{alert_id}")
                return True
            else:
                self.logger.error(f"Failed to dismiss alert history after token refresh: {response.status_code}")
                return False
        else:
            self.logger.error(f"Could not dismiss alertHistoryObject! Status code: {response.status_code}")
            return False

    def get_alert_history_with_details(self, alert_ids: List[str], client_location_view, show_dismissed: bool = False) -> List[dict]:
        """
        Query alert history and enrich it with sensor and sensor type information
        This provides similar functionality to the JavaScript onQueryAlertHistoryOK method
        
        :param alert_ids: List of alert IDs to query for
        :param client_location_view: ClientLocationView object containing sensor information
        :param show_dismissed: Whether to include dismissed alerts (default: False)
        :return: List of enriched alert history records with sensor details
        """
        alert_history_records = self.list_alert_history(alert_ids, show_dismissed)
        
        if not alert_history_records:
            return []
        
        enriched_records = []
        
        # Create a lookup map for sensors by MAC
        sensor_map = {}
        for location_view in client_location_view.locationSensorViews:
            for sensor in location_view.sensorList:
                sensor_map[sensor.mac] = sensor
        
        for record in alert_history_records:
            try:
                # Find the sensor for this record
                sensor = sensor_map.get(record.mac)
                
                if sensor:
                    enriched_record = {
                        'alert_history': record,
                        'sensor': sensor,
                        'formatted_timestamp': record.timestamp,  # You could format this with datetime if needed
                        'analytics_start_time': record.timestamp - (30 * 60 * 1000),  # 30 minutes before
                        'analytics_end_time': record.timestamp + (30 * 60 * 1000),   # 30 minutes after
                        'dismiss_params': {
                            'mac': record.mac,
                            'type': record.sensorType,
                            'alert_id': record.alertId
                        }
                    }
                    enriched_records.append(enriched_record)
                else:
                    self.logger.debug(f"Sensor with MAC {record.mac} not found in client location view")
                    
            except Exception as e:
                # Log errors but continue processing (similar to JavaScript try/catch behavior)
                self.logger.debug(f"Error processing alert history record: {e}")
                continue
        
        return enriched_records

    def print_config(self):
        """Print the API configuration URL"""
        print(self.api_auth.api_config.get_api_url())