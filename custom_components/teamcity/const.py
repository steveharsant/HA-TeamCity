"""Constants for the TeamCity integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "teamcity"

CONF_BUILD_TYPES: Final = "build_types"
CONF_ALLOW_NON_ADMIN_LOGS: Final = "allow_non_admin_logs"

DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=60)
ACTIVE_SCAN_INTERVAL: Final = timedelta(seconds=10)

CARD_FILENAME: Final = "teamcity-card.js"
CARD_URL_PATH: Final = f"/{DOMAIN}_static/{CARD_FILENAME}"
