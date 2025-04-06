import time 
import json
from typing import Dict, Any
import socket 


class ConnectorModule:
    def __init__(self):
        self.location = socket.gethostname()
        print(f"Connector Module Initialized on {self.location}")

    def process_concentration_data(self, concentration_result: Dict[str, Any]) -> Dict[str, Any]:
        original_request_id = None
        original_creation_time = None
        try:
            print(f"Connector Module ({self.location}): Received: {json.dumps(concentration_result)[:150]}...")
            
            original_request_id = concentration_result.get('request_id')
            original_creation_time = concentration_result.get('creation_time')
            final_result = {
                "final_concentration_level": concentration_result.get("concentration_level", "UNKNOWN_FINAL"),
                "original_concentration_value": concentration_result.get("concentration_value"),
                "processed_timestamp": time.time(),
                "source": f"{self.location}_connector"
            }
            if original_request_id:
                final_result['request_id'] = original_request_id
            if original_creation_time:
                final_result['creation_time'] = original_creation_time
            print(f"Connector Module ({self.location}): Processed final result.")
            return final_result
        except Exception as e:
            print(f"Error in Connector Module ({self.location}): {str(e)}")
            error_result = { "error": str(e), "source": f"{self.location}_connector_error" }
            # Optionally add tracking fields to error result too?
            if original_request_id: error_result['request_id'] = original_request_id
            if original_creation_time: error_result['creation_time'] = original_creation_time
            return error_result
        