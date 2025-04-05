from prometheus_client import *

# --- Keep existing Mobile specific metrics ---
EEG_DATA_PROCESSED = Counter('eeg_data_processed_total', 'Total number of EEG data points processed by client module')
# Mobile perspective RTT Gauge
GATEWAY_REQUEST_LATENCY = Gauge('gateway_request_latency_seconds', 'Gateway request round trip time in seconds (mobile perspective)')
GATEWAY_REQUEST_FAILURES = Counter('gateway_request_failures_total', 'Total failed requests sent from mobile to gateway')
# EEG Signal quality metrics (only relevant for mobile)
EEG_QUALITY_SCORE = Gauge('eeg_quality_score', 'Current EEG signal quality score')
EEG_DISCARDED_TOTAL = Counter('eeg_discarded_total', 'Total number of discarded EEG data points by client module')
EEG_ALPHA_POWER = Gauge('eeg_alpha_power', 'Current alpha wave power in EEG signal (mobile calc)')
EEG_NOISE_LEVEL = Gauge('eeg_noise_level', 'Current noise level in EEG signal (mobile calc)')

# --- General Labeled Metrics (Can be defined here or in each service) ---
MODULE_EXECUTIONS = Counter(
    'module_executions_total',
    'Number of times a module successfully executed',
    ['tier', 'module']
)
MODULE_LATENCY = Histogram(
    'module_execution_latency_seconds',
    'Latency of module execution',
    ['tier', 'module']
)
MODULE_ERRORS = Counter(
    'module_errors_total',
    'Number of errors during module execution',
    ['tier', 'module']
)
PASSTHROUGH_COUNT = Counter(
    'passthrough_requests_total',
    'Number of requests passed through without processing',
    ['tier']
)