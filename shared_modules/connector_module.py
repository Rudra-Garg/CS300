import time 
import json
from typing import Dict, Any
import socket 


class ConnectorModule:
    def __init__(self):
        self.location = socket.gethostname()
        print(f"Connector Module Initialized on {self.location}")

    def process_concentration_data(self, concentration_result: Dict[str, Any]) -> Dict[str, Any]:
        try:
            print(f"Connector Module ({self.location}): Received: {json.dumps(concentration_result)[:150]}...")

            final_result = {
                "final_concentration_level": concentration_result.get("concentration_level", "UNKNOWN_FINAL"),
                "original_concentration_value": concentration_result.get("concentration_value"),
                "processed_timestamp": time.time(),
                "source": f"{self.location}_connector"
            }
            print(f"Connector Module ({self.location}): Processed final result.")
            return final_result
        except Exception as e:
            print(f"Error in Connector Module ({self.location}): {str(e)}")
            return { "error": str(e), "source": f"{self.location}_connector_error" }
        