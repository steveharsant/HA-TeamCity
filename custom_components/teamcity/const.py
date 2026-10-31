"""Constants for the TeamCity integration."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "teamcity"

CONF_BUILD_TYPES: Final = "build_types"

DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=60)
