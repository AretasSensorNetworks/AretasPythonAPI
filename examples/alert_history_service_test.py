"""
Basic testing for the alert history service object

Tests querying alert history and dismissing alert history records
"""
from auth import *
from aretas_client import *
from alert_history_service import AlertHistoryService
from alert_service import AlertService
from entities import Alert

import os
import time
from datetime import datetime

# Configuration
TEST_DISMISS_FUNCTIONALITY = False  # Set to True to test alert dismissal

# Change to parent directory to find config
os.chdir('../')

# Initialize API components
config = APIConfig('config.ini')
auth = APIAuth(config)
client = APIClient(auth)

client_location_view: ClientLocationView = client.get_client_location_view()
my_client_id = client_location_view.id

alert_service = AlertService(auth)
alert_history_service = AlertHistoryService(auth)

print("=== Alert History Service Test ===\n")

# Test 1: Get alerts to obtain alert IDs
print("1. Getting alerts to obtain alert IDs...")
alerts = alert_service.list()

if alerts is not None and len(alerts) > 0:
    print(f"Found {len(alerts)} alerts")
    
    # Extract alert IDs
    alert_ids = [alert.id for alert in alerts if alert.id]
    print(f"  Extracted {len(alert_ids)} alert IDs")
    
    # Test 2: Query alert history using alert IDs
    print("\n2. Testing alert history list...")
    alert_history_records = alert_history_service.list_alert_history(alert_ids, show_dismissed=True)
    
    if alert_history_records is not None:
        print(f"Found {len(alert_history_records)} alert history records")
        
        for i, record in enumerate(alert_history_records):
            # Convert timestamp to readable format
            timestamp_str = datetime.fromtimestamp(record.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  Record {i+1}: MAC {record.mac}, Type {record.sensorType}, Alert ID {record.alertId}")
            print(f"    Timestamp: {timestamp_str}, Data: {record.sensorData}")
            print(f"    Dismissed: {record.isDismissed}, Resolved: {record.isResolved}, New: {record.isNew}")
            
            if i >= 4:  # Limit output to first 5 records
                if len(alert_history_records) > 5:
                    print(f"    ... and {len(alert_history_records) - 5} more records")
                break
    else:
        print("  No alert history records found or error occurred")
    
    print()
    
    # Test 3: Get enriched alert history with sensor details
    print("3. Testing enriched alert history query...")
    enriched_records = alert_history_service.get_alert_history_with_details(alert_ids, client_location_view, show_dismissed=True)
    
    if enriched_records:
        print(f"Found {len(enriched_records)} enriched alert history records")
        
        for i, enriched_record in enumerate(enriched_records):
            record = enriched_record['alert_history']
            sensor = enriched_record['sensor']
            
            timestamp_str = datetime.fromtimestamp(record.timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')
            
            print(f"  Enriched Record {i+1}:")
            print(f"    Device: {sensor.description} (MAC: {sensor.mac})")
            print(f"    Alert ID: {record.alertId}, Data: {record.sensorData}")
            print(f"    Timestamp: {timestamp_str}")
            print(f"    Analytics window: {enriched_record['analytics_start_time']} to {enriched_record['analytics_end_time']}")
            
            if i >= 2:  # Limit output to first 3 enriched records
                if len(enriched_records) > 3:
                    print(f"    ... and {len(enriched_records) - 3} more enriched records")
                break
    else:
        print("  No enriched alert history records found")
    
    print()
else:
    print("  No alerts found - cannot test alert history without alert IDs")
    alert_history_records = None
    print()

# Test 4: Test dismiss functionality (only if enabled and we have records)
if TEST_DISMISS_FUNCTIONALITY and alert_history_records and len(alert_history_records) > 0:
    print("4. Testing alert history dismiss...")
    
    # Find a non-dismissed alert to dismiss
    dismissable_record = None
    for record in alert_history_records:
        if not record.isDismissed:
            dismissable_record = record
            break
    
    if dismissable_record:
        print(f"  Attempting to dismiss alert: MAC {dismissable_record.mac}, Type {dismissable_record.sensorType}, Alert ID {dismissable_record.alertId}")
        
        dismiss_result = alert_history_service.dismiss_alert_history_object(
            dismissable_record.mac, 
            dismissable_record.sensorType, 
            dismissable_record.alertId
        )
        
        if dismiss_result:
            print("  ✓ Alert successfully dismissed")
            
            # Query again to verify dismissal
            print("  Verifying dismissal...")
            updated_records = alert_history_service.list_alert_history(alert_ids, show_dismissed=True)
            
            if updated_records:
                # Check if the record is now dismissed
                now_dismissed = False
                for record in updated_records:
                    if (record.mac == dismissable_record.mac and 
                        record.sensorType == dismissable_record.sensorType and 
                        record.alertId == dismissable_record.alertId and 
                        record.isDismissed):
                        now_dismissed = True
                        break
                
                if now_dismissed:
                    print("  ✓ Alert confirmed as dismissed")
                else:
                    print("  ⚠ Alert may not be dismissed yet (cache delay possible)")
            else:
                print("  Could not verify dismissal due to query error")
        else:
            print("  ✗ Failed to dismiss alert")
    else:
        print("  No non-dismissed alerts found to test dismissal")
elif not TEST_DISMISS_FUNCTIONALITY:
    print("4. Skipping dismiss test - TEST_DISMISS_FUNCTIONALITY is disabled")
else:
    print("4. Skipping dismiss test - no alert history records available")

print()

# Test 5: Test error handling with invalid parameters
print("5. Testing error handling...")
invalid_dismiss_result = alert_history_service.dismiss_alert_history_object(
    999999999,  # Invalid MAC
    999,        # Invalid type  
    "invalid-alert-id"
)

if not invalid_dismiss_result:
    print("  ✓ Error handling working correctly - invalid dismiss returned False")
else:
    print("  ⚠ Unexpected success with invalid parameters")

print("\n=== Alert History Service Test Complete ===")