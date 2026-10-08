import logging
from typing import List, Optional

from auth import APIAuth
from entities import AlertLogRecord
from rest_helper import authed_request


class AlertLogService:
    """
    Read / purge the persistent alert event log (the alertlog/* endpoints).

    Every alert incident the platform opens is written here as an AlertLogRecord and
    closed in place when the return-to-normal reading arrives. This is the durable
    counterpart of AlertHistoryService, which reads the short-lived recent-history cache.

    All time windows are epoch milliseconds (UTC) and are applied to the record's
    timestamp (the reading that opened the incident).
    """

    def __init__(self, api_auth: APIAuth):
        self.api_auth = api_auth
        self.logger = logging.getLogger(__name__)

    def _parse_list(self, response, what: str) -> Optional[List[AlertLogRecord]]:
        if response.status_code != 200:
            self.logger.error("Failed to {}: HTTP {} {}".format(what, response.status_code, response.text[:200]))
            return None
        records = []
        for record_data in response.json():
            try:
                records.append(AlertLogRecord(**record_data))
            except Exception as e:
                self.logger.debug("Error parsing alert log record: {}".format(e))
        return records

    def list_by_alert_id(self, alert_id: str, start: int, end: int, limit: int = 1000) -> Optional[List[AlertLogRecord]]:
        """
        List the alert log records for one alert within a time window (ascending by timestamp)

        :param alert_id: the alert ID (must belong to the authenticated account)
        :param start: window start, epoch ms (must be > 0)
        :param end: window end, epoch ms (must be > 0)
        :param limit: maximum number of records; the API returns NOTHING when this is omitted, so it is always sent
        :return: List of AlertLogRecord or None if the request fails
        """
        params = {'alertId': alert_id, 'start': int(start), 'end': int(end), 'limit': int(limit)}
        response = authed_request(self.api_auth, "GET", "alertlog/listbyid", params=params)
        return self._parse_list(response, "list alert log by alert id")

    def list_by_mac(self, mac: int, start: int, end: int, limit: int = 1000) -> Optional[List[AlertLogRecord]]:
        """
        List the alert log records for one device MAC within a time window (newest first)

        :param mac: the device MAC (must belong to the authenticated account)
        :param start: window start, epoch ms
        :param end: window end, epoch ms
        :param limit: maximum number of records
        :return: List of AlertLogRecord or None if the request fails
        """
        params = {'mac': int(mac), 'start': int(start), 'end': int(end), 'limit': int(limit)}
        response = authed_request(self.api_auth, "GET", "alertlog/listbymac", params=params)
        return self._parse_list(response, "list alert log by mac")

    def list_account_history(self, start: int, end: int) -> Optional[List[AlertLogRecord]]:
        """
        List every alert log record in the account within a time window (newest first).
        The window may span at most 8 days.

        :param start: window start, epoch ms
        :param end: window end, epoch ms
        :return: List of AlertLogRecord or None if the request fails
        """
        params = {'start': int(start), 'end': int(end)}
        response = authed_request(self.api_auth, "GET", "alertlog/consolidatedhistory", params=params)
        return self._parse_list(response, "list account alert history")

    def get_by_event_id(self, event_id: int) -> Optional[AlertLogRecord]:
        """
        Fetch a single alert log record by its event ID

        :param event_id: the record's eventId
        :return: AlertLogRecord or None if not found / request fails
        """
        response = authed_request(self.api_auth, "GET", "alertlog/getbyeventid", params={'eventId': int(event_id)})
        if response.status_code != 200 or not response.content:
            self.logger.error("Failed to fetch alert log record {}: HTTP {}".format(event_id, response.status_code))
            return None
        try:
            return AlertLogRecord(**response.json())
        except Exception as e:
            self.logger.error("Error parsing alert log record {}: {}".format(event_id, e))
            return None

    def purge(self, alert_id: str, age_ms: int = 0) -> Optional[int]:
        """
        Delete alert log records for one alert

        :param alert_id: the alert ID (must belong to the authenticated account)
        :param age_ms: only purge records older than this many milliseconds; 0 (default) purges ALL records for the alert
        :return: the number of records removed, or None if the request fails
        """
        params = {'alertId': alert_id, 'age': int(age_ms)}
        response = authed_request(self.api_auth, "GET", "alertlog/purgealerthistory", params=params)
        if response.status_code != 200:
            self.logger.error("Failed to purge alert log for {}: HTTP {} {}".format(
                alert_id, response.status_code, response.text[:200]))
            return None
        try:
            return int(response.text.strip())
        except ValueError:
            self.logger.error("Unexpected purge response: {}".format(response.text[:200]))
            return None

    def print_config(self):
        """Print the API configuration URL"""
        print(self.api_auth.api_config.get_api_url())
