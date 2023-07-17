from api_config import APIConfig
from aretas_client import APIClient
from auth import APIAuth
from sensor_data_ingest import SensorDataIngest
from utils import Utils

if __name__ == "__main__":

    config = APIConfig('./config.ini')
    auth = APIAuth(config)
    client = APIClient(auth)

    api_send = SensorDataIngest(auth)

    dataset = list()
    for i in range(5):
        now_ms = Utils.now_ms()
        dataset.append(
            {
                "mac": 888,
                'type': i,
                'data': 0.00,
                'timestamp': now_ms
            }
        )

    # enable auth_check for long-running services that don't reinitialize the auth object and get a valid token
    api_send.send_data(dataset, auth_check=False)
