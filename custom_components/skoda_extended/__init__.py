"""Škoda Extended: all data from the MyŠkoda public API in Home Assistant."""

from __future__ import annotations

from skoda_public_api.api_layer.open_api_client import OpenAPIClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_VIN
from .coordinator import SkodaConfigEntry, SkodaCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.IMAGE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: SkodaConfigEntry) -> bool:
    """Set up a vehicle from a config entry."""
    client = OpenAPIClient(
        api_key=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )
    coordinator = SkodaCoordinator(hass, entry, client, entry.data[CONF_VIN])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: SkodaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SkodaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
