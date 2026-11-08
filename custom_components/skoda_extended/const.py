"""Constants for the Škoda Extended integration."""

DOMAIN = "skoda_extended"

CONF_VIN = "vin"
CONF_SPIN = "spin"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_AUX_DURATION = "aux_heating_duration"

# The public API allows 20 requests per hour per VIN. Polling every 5 minutes
# uses 12 of them and leaves room for a manual refresh and a few commands.
DEFAULT_SCAN_INTERVAL = 5  # minutes
MIN_SCAN_INTERVAL = 4  # minutes -> 15 requests/hour
MAX_SCAN_INTERVAL = 60

DEFAULT_AUX_DURATION = 20  # minutes

API_KEYS_URL = "https://go.skoda.eu/api-keys"
