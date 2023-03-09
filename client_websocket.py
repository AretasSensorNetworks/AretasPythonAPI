from auth import APIAuth
import json
import time
import websocket
import collections
import threading
import logging


class SensorDataWebsocket:
    """
    A class for instantiating and
    """
    def __init__(self, api_auth: APIAuth,
                 target_location_id: str,
                 target_macs: list,
                 message_callback,
                 ws_trace_enable=False):

        self.api_auth = api_auth
        self.ws_thread = None
        self.ws_ping_thread = None
        self.ws = None
        self.message_callback = message_callback
        self._target_location_id = target_location_id
        self._target_macs = target_macs
        format_ = "%(asctime)s: %(message)s"
        logging.basicConfig(format=format_,
                            level=logging.INFO,
                            datefmt="%H:%M:%S")
        self._ws_trace_enable = ws_trace_enable

        self._ws_ping_thread_run = False;

    def ws_run(self, *args):
        # run it async so we don't block other processing
        self.ws.run_forever()
        logging.info("ws_run forever thread terminating")

    def ws_run_ping(self):
        # in order to keep the web socket from closing, we need to ping it
        while True:
            if not self._ws_ping_thread_run:
                return
            time.sleep(10)
            self.ws.send("PING")
        logging.info("ws_run_ping terminating")

    def start(self):
        # url = self.api_auth.api_config.get_api_url() + "sensordata/byrange"
        # open the websocket and watch for messages
        websocket.enableTrace(self._ws_trace_enable)
        self._ws_ping_thread_run = True
        self.ws = websocket.WebSocketApp(
            "ws://iot.aretas.ca/sensordataevents/" + self.api_auth.get_token(),
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.on_open = self.on_open
        x = threading.Thread(target=self.ws_run, args=())
        x.start()
        self.ws_thread = x

    def on_open(self, ws):
        """the aretas sensordataevents websocket-connection-example requires the first message
            to be the location entity ID and the list of
            entity (device) IDs you want to monitor
            end the request for the location ID and associated entity addresses"""

        mac_str = ",".join([str(i) for i in self._target_macs])
        req_str = "{0},{1}".format(self._target_location_id, mac_str)
        self.ws.send(req_str)

        x = threading.Thread(target=self.ws_run_ping, args=())
        x.start()
        # in case we ned to access the thread
        self.ws_ping_thread = x

    def on_error(self, ws, error):
        logging.error("WS Error: {}".format(error))

    def on_close(self, ws, close_status_code, close_msg):
        logging.info("Web socket closed")

    def on_message(self, ws, message):
        # print(message)
        data = json.loads(message)
        # print(type(data))
        # check if it is an array, list, etc.
        if isinstance(data, collections.abc.Sequence):
            for datum in data:
                if 'type' in datum:
                    if self._ws_trace_enable:
                        logging.info("Received sensor data message:")
                    self.message_callback(datum)

    def stop(self):
        self._ws_ping_thread_run = False
        self.ws_ping_thread.join()
        self.ws.close()


