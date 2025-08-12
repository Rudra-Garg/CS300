import json
import numpy as np
from typing import Dict, Any, Union

class ConcentrationCalculatorModule:
    def __init__(self):
        self.eeg_window_size = 128  # Use a 1-second window
        self.sampling_rate = 128    # CRITICAL: Update to match dataset
        self.buffer = []

    def _extract_band_powers(self, eeg_data: list) -> dict:
        signal_array = np.array(eeg_data)
        fft_vals = np.abs(np.fft.rfft(signal_array))
        fft_freq = np.fft.rfftfreq(len(signal_array), 1.0/self.sampling_rate)

        def get_power(low, high):
            mask = (fft_freq >= low) & (fft_freq <= high)
            return np.mean(fft_vals[mask]**2)

        total_power = np.mean(fft_vals**2)
        if total_power == 0: return {}
        
        return {
            "alpha": get_power(8, 13) / total_power,
            "beta": get_power(13, 30) / total_power,
        }

    def calculate_concentration(self, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            eeg_values = sensor_data.get('eeg_values', [])
            if not eeg_values: raise ValueError("No EEG values found")

            self.buffer.extend(eeg_values)
            if len(self.buffer) > self.eeg_window_size:
                self.buffer = self.buffer[-self.eeg_window_size:]

            if len(self.buffer) < self.eeg_window_size:
                return {"error": "Buffering data", "concentration_level": "BUFFERING"}

            band_powers = self._extract_band_powers(self.buffer)
            if not band_powers or band_powers.get("beta", 0) == 0:
                return {"error": "Calculation error", "concentration_level": "ERROR"}

            # Use Alpha / Beta ratio as a proxy for relaxed concentration
            alpha_beta_ratio = band_powers["alpha"] / band_powers["beta"]
            concentration_value = min(1.0, alpha_beta_ratio / 2.0) # Normalize roughly
            concentration_level = "HIGH" if concentration_value > 0.6 else "LOW"

            sensor_data["concentration_level"] = concentration_level
            sensor_data["concentration_value"] = concentration_value
            sensor_data["metadata"] = {"alpha_beta_ratio": alpha_beta_ratio}
            return sensor_data

        except Exception as e:
            return {"error": str(e), "concentration_level": "ERROR"}