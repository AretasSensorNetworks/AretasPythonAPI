from api_config import APIConfig
from aretas_client import APIClient
from auth import APIAuth
import csv
import os
from datetime import datetime, timezone

os.chdir("../")

'''
Export script:
Connects to a customer's account using credentials in config.ini and exports
all distinct MAC addresses (with sensor id, description, owner, location, etc.)
to a single CSV file.

Run from inside the examples/ folder (the script does an os.chdir("../") to find config.ini).
'''


def main():
    # 1. Authenticate
    config = APIConfig('config.ini')
    auth = APIAuth(config)
    client = APIClient(auth)

    # 2. Pull the full client/location view
    client_location_view = client.get_client_location_view()
    if client_location_view is None:
        print("ERROR: Could not retrieve client location view. Check credentials/network.")
        return

    client_id = client_location_view.id
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # 3. Collect distinct MACs by walking each LocationSensorView
    distinct_macs = set()
    mac_detail_rows = []

    for lsv in client_location_view.locationSensorViews:
        loc = lsv.location
        if not lsv.sensorList:
            continue

        for sensor in lsv.sensorList:
            if sensor.mac in distinct_macs:
                continue
            distinct_macs.add(sensor.mac)

            mac_detail_rows.append({
                "mac": sensor.mac,
                "sensor_id": sensor.id,
                "description": sensor.description,
                "owner": sensor.owner,
                "owner_client_id": sensor.ownerClientId,
                "location_id": loc.id,
                "location_description": loc.description,
                "lat": sensor.lat,
                "lon": sensor.lon,
                "last_report_time": sensor.lastReportTime,
                "area_type": sensor.areaType,
                "building_map_id": sensor.buildingMapId,
                "is_shared": sensor.isShared,
                "is_shared_public": sensor.isSharedPublic,
            })

    # 4. Catch any account-level MACs not attached to a LocationSensorView
    api_all_macs = set(client_location_view.allMacs or [])
    orphan_macs = api_all_macs - distinct_macs
    for mac in orphan_macs:
        distinct_macs.add(mac)
        mac_detail_rows.append({
            "mac": mac,
            "sensor_id": "",
            "description": "(not attached to a LocationSensorView)",
            "owner": "",
            "owner_client_id": "",
            "location_id": "",
            "location_description": "",
            "lat": "",
            "lon": "",
            "last_report_time": "",
            "area_type": "",
            "building_map_id": "",
            "is_shared": "",
            "is_shared_public": "",
        })

    # 5. Sort for stable output
    mac_detail_rows.sort(key=lambda r: (str(r["location_description"]), str(r["mac"])))

    # 6. Write the single CSV
    macs_filename = f"macs_{client_id}_{timestamp}.csv"

    if mac_detail_rows:
        with open(macs_filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(mac_detail_rows[0].keys()))
            writer.writeheader()
            writer.writerows(mac_detail_rows)

    # 7. Summary to stdout
    print(f"Exported {len(distinct_macs)} distinct MAC addresses to {macs_filename}")


if __name__ == "__main__":
    main()
