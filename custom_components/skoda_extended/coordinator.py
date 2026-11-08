"""Data update coordinator for Škoda Extended."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging

from skoda_public_api.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
    OpenApiRateLimitError,
)
from skoda_public_api.api_layer.open_api_client import OpenAPIClient
from skoda_public_api.models.enums import VehicleCapability, VehicleOperationName
from skoda_public_api.models.vehicle import VehicleResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class SkodaData:
    """Snapshot of one poll."""

    response: VehicleResponse
    capabilities: set[VehicleCapability] = field(default_factory=set)
    operations: set[VehicleOperationName] | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset: int | None = None
    api_key_expires_at: str | None = None


type SkodaConfigEntry = ConfigEntry[SkodaCoordinator]


class SkodaCoordinator(DataUpdateCoordinator[SkodaData]):
    """Polls the whole vehicle object in one request."""

    config_entry: SkodaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SkodaConfigEntry,
        client: OpenAPIClient,
        vin: str,
    ) -> None:
        minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{vin}",
            update_interval=timedelta(minutes=minutes),
        )
        self.client = client
        self.vin = vin

    async def _async_update_data(self) -> SkodaData:
        try:
            response = await self.client.get_vehicle(self.vin)
        except OpenApiAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                "API key is invalid or expired; create a new one in the MyŠkoda app"
            ) from err
        except OpenApiRateLimitError as err:
            raise UpdateFailed(f"Rate limit reached: {err}") from err
        except OpenApiError as err:
            raise UpdateFailed(f"Error talking to the Škoda API: {err}") from err

        for error in response.errors:
            _LOGGER.debug("Partial data for %s: %s", self.vin, error.type)

        # Keep capabilities seen earlier: a part that is temporarily missing
        # should not make its entities disappear.
        caps = response.supported_capabilities()
        if self.data is not None:
            caps |= self.data.capabilities

        return SkodaData(
            response=response,
            capabilities=caps,
            operations=response.supported_operations(),
            rate_limit_remaining=self.client.rate_limit_remaining,
            rate_limit_reset=self.client.rate_limit_reset,
            api_key_expires_at=self.client.api_key_expires_at,
        )
