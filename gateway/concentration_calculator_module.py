import json
import numpy as np
from typing import Dict, Any, Union

class ConcentrationCalculatorModule:
    def __init__(self):
        # Initialize thresholds and parameters based on iFogSim implementation
        self.eeg_window_size = 100  # Number of EEG samples to analyze
        self.concentration_threshold = 0.7  # Threshold for high concentration
        self.sampling_rate = 250  # Hz, typical for EEG
        self.buffer = []

    def calculate_concentration(self, sensor_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate concentration level from EEG sensor data.
        
        Args:
            sensor_data: Raw EEG data from sensor, can be JSON string or dict
            
        Returns:
            Dict containing concentration level and metadata
        """
        try:
            # Parse input data if it's a string
            if isinstance(sensor_data, str):
                data = json.loads(sensor_data)
            else:
                data = sensor_data

            # Extract EEG values
            eeg_values = data.get('eeg_values', [])
            if not eeg_values:
                raise ValueError("No EEG values found in sensor data")

            # Add to buffer and maintain window size
            self.buffer.extend(eeg_values)
            if len(self.buffer) > self.eeg_window_size:
                self.buffer = self.buffer[-self.eeg_window_size:]

            # Calculate concentration metrics
            # Using signal power in alpha band (8-13 Hz) as concentration indicator
            # Higher alpha power typically indicates relaxed attention/concentration
            concentration_value = self._calculate_alpha_power(self.buffer)
            
            # Normalize concentration value to 0-1 range
            normalized_concentration = min(1.0, max(0.0, concentration_value))
            
            # Determine concentration level
            concentration_level = "HIGH" if normalized_concentration >= self.concentration_threshold else "LOW"
            
            result = {
                "concentration_level": concentration_level,
                "concentration_value": normalized_concentration,
                "timestamp": data.get('timestamp', None),
                "metadata": {
                    "window_size": self.eeg_window_size,
                    "threshold": self.concentration_threshold
                }
            }
            
            print(f"Concentration Calculator: Processed result = {result}")
            return result

        except Exception as e:
            print(f"Error calculating concentration: {str(e)}")
            return {
                "concentration_level": "ERROR",
                "error": str(e)
            }

    def _calculate_alpha_power(self, eeg_data: list) -> float:
        """Calculate the power in alpha frequency band (8-13 Hz).
        
        Args:
            eeg_data: List of EEG samples
            
        Returns:
            Normalized power value in alpha band
        """
        try:
            # Convert to numpy array for calculations
            signal = np.array(eeg_data)
            
            # Apply FFT to get frequency components
            fft_vals = np.abs(np.fft.rfft(signal))
            fft_freq = np.fft.rfftfreq(len(signal), 1.0/self.sampling_rate)
            
            # Calculate power in alpha band (8-13 Hz)
            alpha_mask = (fft_freq >= 8) & (fft_freq <= 13)
            alpha_power = np.mean(fft_vals[alpha_mask]**2)
            
            # Normalize by total power
            total_power = np.mean(fft_vals**2)
            normalized_power = alpha_power / total_power if total_power > 0 else 0
            
            return normalized_power
            
        except Exception as e:
            print(f"Error in alpha power calculation: {str(e)}")
            return 0.0

# Example Usage
if __name__ == "__main__":
    calculator = ConcentrationCalculatorModule()
    data1 = "processed_valid_eeg_some_data"
    calculator.calculate_concentration(data1)
    data2 = "processed_invalid_eeg_error_data" # Example of invalid data - though Client Module should ideally filter this out
    calculator.calculate_concentration(data2)