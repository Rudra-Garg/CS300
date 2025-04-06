import json
import time
import numpy as np
from typing import Dict, Any, Union, Optional
from .metrics import *


class ClientModule:
    def __init__(self):
        # Initialize parameters based on iFogSim implementation
        self.buffer_size = 100  # Match concentration calculator's window size
        self.sampling_rate = 250  # Hz, matching concentration calculator
        self.buffer = []
        self.last_send_time = 0
        self.send_interval = 0.1  # 100ms interval between sends
        self.error_threshold = 0.5  # 50% threshold for signal quality

    def process_eeg(self, eeg_data: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Process incoming EEG data and prepare it for transmission.
        
        Args:
            eeg_data: Raw EEG data from sensor, can be JSON string or dict
            
        Returns:
            Processed EEG data ready for transmission, or None if data is invalid
        """
        original_request_id = None
        original_creation_time = None
        try:
            # Parse input data if it's a string
            if isinstance(eeg_data, str):
                try:
                    data = json.loads(eeg_data)
                except json.JSONDecodeError:
                    # Handle non-JSON string input (for backward compatibility)
                    data = {"eeg_values": [float(eeg_data)], "timestamp": time.time()}
            else:
                data = eeg_data

            # Extract or create EEG values
            eeg_values = data.get('eeg_values', [])
            if not eeg_values:
                print("Client Module: No EEG values found in data")
                return None
            
            original_request_id = data.get('request_id')
            original_creation_time = data.get('creation_time')
            # Quality check on EEG values
            quality_score = self._calculate_quality_score(eeg_values)
            EEG_QUALITY_SCORE.set(quality_score)
            
            if not self._check_signal_quality(eeg_values):
                print(f"Client Module: Discarding low quality EEG data (score: {quality_score:.2f})")
                EEG_DISCARDED_TOTAL.inc()
                return None

            # Calculate and record alpha power
            alpha_power = self._calculate_alpha_power(eeg_values)
            EEG_ALPHA_POWER.set(alpha_power)
            
            # Calculate and record noise level
            noise_level = self._calculate_noise_level(eeg_values)
            EEG_NOISE_LEVEL.set(noise_level)

            # Add to buffer and maintain size
            self.buffer.extend(eeg_values)
            if len(self.buffer) > self.buffer_size:
                self.buffer = self.buffer[-self.buffer_size:]

            # Rate limiting for data transmission
            current_time = time.time()
            if current_time - self.last_send_time < self.send_interval:
                return None

            self.last_send_time = current_time

            # Prepare data for transmission
            processed_data = {
                "eeg_values": self.buffer.copy(),
                "timestamp": data.get('timestamp', current_time),
                "sampling_rate": self.sampling_rate,
                "metadata": {
                    "buffer_size": self.buffer_size,
                    "quality_score": self._calculate_quality_score(eeg_values)
                }
            }
            if original_request_id:
                processed_data['request_id'] = original_request_id
            if original_creation_time:
                processed_data['creation_time'] = original_creation_time
            print(f"Client Module: Sending processed data to Gateway")
            return processed_data

        except Exception as e:
            print(f"Client Module Error: {str(e)}")
            return None

    def _check_signal_quality(self, eeg_values: list) -> bool:
        """Check if the EEG signal quality is acceptable.
        
        Args:
            eeg_values: List of EEG samples to check
            
        Returns:
            True if signal quality is acceptable, False otherwise
        """
        quality_score = self._calculate_quality_score(eeg_values)
        return quality_score >= (1 - self.error_threshold)

    def _calculate_quality_score(self, eeg_values: list) -> float:
        """Calculate a quality score for the EEG signal.
        
        Args:
            eeg_values: List of EEG samples
            
        Returns:
            Quality score between 0 and 1
        """
        if not eeg_values:
            return 0.0

        try:
            # Simple quality metrics:
            # 1. Check for NaN or infinity values
            valid_values = [v for v in eeg_values if isinstance(v, (int, float)) 
                        and not isinstance(v, bool) and -1e6 <= v <= 1e6]
            
            if not valid_values:
                return 0.0

            # 2. Calculate signal-to-noise ratio (simplified)
            mean_signal = sum(valid_values) / len(valid_values)
            variance = sum((x - mean_signal) ** 2 for x in valid_values) / len(valid_values)
            print(f"Calculated variance: {variance}") # DEBUG
            quality_score = 1.0 / (1.0 + variance) if variance > 0 else 1.0
            print(f"Calculated quality score (before clamp): {quality_score}") # DEBUG
            final_score = min(1.0, max(0.0, quality_score))
            print(f"Final quality score: {final_score}") # DEBUG
            return final_score

        except Exception as e:
            print(f"Error calculating quality score: {str(e)}")
            return 0.0

    def update_concentration_display(self, concentration_data: Dict[str, Any]) -> None:
        """Update the display with concentration information.
        
        Args:
            concentration_data: Dictionary containing concentration level and metadata
        """
        try:
            level = concentration_data.get('concentration_level', 'UNKNOWN')
            value = concentration_data.get('concentration_value', 0.0)
            timestamp = concentration_data.get('timestamp', time.time())
            
            print(f"Client Module: Concentration Update at {timestamp}")
            print(f"Level: {level}, Value: {value:.2f}")
            
            if 'metadata' in concentration_data:
                print(f"Additional Info: {concentration_data['metadata']}")
                
        except Exception as e:
            print(f"Error updating concentration display: {str(e)}")

    def _calculate_alpha_power(self, eeg_values: list) -> float:
        """Calculate power in alpha frequency band (8-13 Hz)"""
        if not eeg_values:
            return 0.0
        # Simple approximation of alpha power
        return np.mean(np.abs(eeg_values))

    def _calculate_noise_level(self, eeg_values: list) -> float:
        """Calculate approximate noise level in the signal"""
        if not eeg_values:
            return 0.0
        return np.std(eeg_values) / np.mean(np.abs(eeg_values)) if np.mean(np.abs(eeg_values)) > 0 else 0.0

# Example usage
if __name__ == "__main__":
    client = ClientModule()
    
    # Test with various input types
    test_data = [
        {"eeg_values": [0.5, 0.6, 0.7], "timestamp": time.time()},
        "0.8",  # Simple string value
        "{\"eeg_values\": [0.9, 1.0, 1.1]}",  # JSON string
        {"eeg_values": [], "timestamp": time.time()},  # Empty values
        "invalid_data"  # Should be handled gracefully
    ]
    
    for data in test_data:
        result = client.process_eeg(data)
        if result:
            print(f"Processed result: {result}\n")
        else:
            print(f"Data processing failed for input: {data}\n")
            