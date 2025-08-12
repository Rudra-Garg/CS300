import json
import time
import numpy as np
from typing import Dict, Any, Optional
from scipy import signal

# The core metrics like MODULE_EXECUTIONS, MODULE_LATENCY, etc., 
# are imported via the main service files (e.g., mobile.py)
# and are used when calling this module's methods.

class ClientModule:
    def __init__(self):
        """
        Initializes the ClientModule for pre-processing EEG signals.
        This module is responsible for cleaning the raw signal from the sensor/stream.
        """
        # CRITICAL: This sampling rate must match the dataset being used.
        # The EEG Eye State dataset is recorded at 128 Hz.
        self.sampling_rate = 128
        
        # --- Define Digital Filters ---
        # 1. Butterworth band-pass filter to keep frequencies between 1 Hz and 50 Hz.
        # This removes slow DC drifts and high-frequency noise.
        self.b_band, self.a_band = signal.butter(4, [1, 50], btype='band', fs=self.sampling_rate)
        
        # 2. Notch filter to remove 60 Hz power line interference.
        # Note: If the dataset was recorded outside the Americas, you might need 50 Hz.
        self.b_notch, self.a_notch = signal.iirnotch(60, 30, fs=self.sampling_rate)
        print("ClientModule Initialized: Ready to filter 128 Hz EEG data.")

    def _filter_signal(self, eeg_values: list) -> np.ndarray:
        """
        Applies band-pass and notch filters to the raw EEG signal.
        """
        # Filtering requires a minimum number of data points.
        if len(eeg_values) < 20: 
            return np.array(eeg_values)

        # Apply the band-pass filter
        band_passed_signal = signal.filtfilt(self.b_band, self.a_band, eeg_values)
        
        # Apply the notch filter to the result of the band-pass
        final_signal = signal.filtfilt(self.b_notch, self.a_notch, band_passed_signal)
        
        return final_signal

    def process_eeg(self, eeg_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Processes a chunk of raw EEG data by applying filters.
        
        Args:
            eeg_data: A dictionary containing the raw 'eeg_values' and other metadata.
            
        Returns:
            A dictionary with the filtered EEG values, or None if input is invalid.
        """
        try:
            eeg_values = eeg_data.get('eeg_values')
            if not isinstance(eeg_values, list) or not eeg_values:
                print("ClientModule Warning: Invalid or empty 'eeg_values' received.")
                return None

            # Apply the cleaning filters to the signal
            cleaned_eeg_values = self._filter_signal(eeg_values)
            
            # Return the original data structure but with the cleaned signal
            # This ensures compatibility with the next module in the pipeline.
            processed_data = {
                "eeg_values": cleaned_eeg_values.tolist(),
                "timestamp": eeg_data.get('timestamp', time.time()),
                "sampling_rate": self.sampling_rate,
                "request_id": eeg_data.get('request_id'),
                "creation_time": eeg_data.get('creation_time')
            }
            return processed_data

        except Exception as e:
            print(f"ClientModule Error during processing: {e}")
            return None
        