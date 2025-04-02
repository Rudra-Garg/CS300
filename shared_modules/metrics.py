from prometheus_client import Counter, Gauge

# Prometheus metrics
EEG_DATA_PROCESSED = Counter('eeg_data_processed_total', 'Total number of EEG data points processed')
GATEWAY_REQUEST_LATENCY = Gauge('gateway_request_latency_seconds', 'Gateway request latency in seconds')
GATEWAY_REQUEST_FAILURES = Counter('gateway_request_failures_total', 'Total number of failed gateway requests')
EEG_QUALITY_SCORE = Gauge('eeg_quality_score', 'Current EEG signal quality score')
EEG_DISCARDED_TOTAL = Counter('eeg_discarded_total', 'Total number of discarded EEG data points')
EEG_ALPHA_POWER = Gauge('eeg_alpha_power', 'Current alpha wave power in EEG signal')
EEG_NOISE_LEVEL = Gauge('eeg_noise_level', 'Current noise level in EEG signal')