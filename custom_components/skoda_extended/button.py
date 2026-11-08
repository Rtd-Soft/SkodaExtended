"""Buttons: manual refresh and remote commands."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from skoda_public_api.api_layer.exceptions import (
    OpenApiError,
    OpenApiRateLimitError,
)
from skoda_public_api.api_layer.open_api_client import OpenAPIClient
from skoda_public_api.models.enums import VehicleCapability as Cap, VehicleOperationName as Op

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .const import CONF_AUX_DURATION, CONF_SPIN, DEFAULT_AUX_DURATION, DOMAIN
from .coordinator import SkodaConfigEntry, SkodaCoordinator
from .entity import SkodaEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# The car needs some time before its new state shows up in the API.
REFRESH_DELAY = 90  # seconds


@dataclass(frozen=True, kw_only=True)
class SkodaButtonDescription(ButtonEntityDescription):
    """Command button."""

    operation: Op | None = None
    capability: Cap | None = None
    press_fn: Callable[[SkodaCoordinator], Awaitable[object]]


def _client(c: SkodaCoordinator) -> OpenAPIClient:
    return c.client


async def _start_aux(c: SkodaCoordinator, mode: str) -> object:
    spin = c.config_entry.options.get(CONF_SPIN)
    if not spin:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="spin_required"
        )
    minutes = int(c.config_entry.options.get(CONF_AUX_DURATION, DEFAULT_AUX_DURATION))
    return await c.client.start_auxiliary_heating(
        c.vin, spin=spin, duration_in_seconds=minutes * 60, start_mode=mode
    )


BUTTONS: tuple[SkodaButtonDescription, ...] = (
    SkodaButtonDescription(
        key="start_air_conditioning",
        translation_key="start_air_conditioning",
        icon="mdi:air-conditioner",
        operation=Op.START_AIR_CONDITIONING,
        capability=Cap.AIR_CONDITIONING,
        press_fn=lambda c: c.client.start_air_conditioning(c.vin),
    ),
    SkodaButtonDescription(
        key="stop_air_conditioning",
        translation_key="stop_air_conditioning",
        icon="mdi:air-conditioner",
        operation=Op.STOP_AIR_CONDITIONING,
        capability=Cap.AIR_CONDITIONING,
        press_fn=lambda c: c.client.stop_air_conditioning(c.vin),
    ),
    SkodaButtonDescription(
        key="start_auxiliary_heating",
        translation_key="start_auxiliary_heating",
        icon="mdi:radiator",
        operation=Op.START_AUXILIARY_HEATING,
        capability=Cap.AUXILIARY_HEATING,
        press_fn=lambda c: _start_aux(c, "HEATING"),
    ),
    SkodaButtonDescription(
        key="start_auxiliary_ventilation",
        translation_key="start_auxiliary_ventilation",
        icon="mdi:fan",
        operation=Op.START_AUXILIARY_HEATING,
        capability=Cap.AUXILIARY_HEATING,
        press_fn=lambda c: _start_aux(c, "VENTILATION"),
    ),
    SkodaButtonDescription(
        key="stop_auxiliary_heating",
        translation_key="stop_auxiliary_heating",
        icon="mdi:radiator-off",
        operation=Op.STOP_AUXILIARY_HEATING,
        capability=Cap.AUXILIARY_HEATING,
        press_fn=lambda c: c.client.stop_auxiliary_heating(c.vin),
    ),
    SkodaButtonDescription(
        key="start_ventilation",
        translation_key="start_ventilation",
        icon="mdi:fan",
        operation=Op.START_ACTIVE_VENTILATION,
        capability=Cap.ACTIVE_VENTILATION,
        press_fn=lambda c: c.client.start_active_ventilation(c.vin),
    ),
    SkodaButtonDescription(
        key="stop_ventilation",
        translation_key="stop_ventilation",
        icon="mdi:fan-off",
        operation=Op.STOP_ACTIVE_VENTILATION,
        capability=Cap.ACTIVE_VENTILATION,
        press_fn=lambda c: c.client.stop_active_ventilation(c.vin),
    ),
    SkodaButtonDescription(
        key="start_charging",
        translation_key="start_charging",
        icon="mdi:ev-station",
        operation=Op.START_CHARGING,
        capability=Cap.CHARGING,
        press_fn=lambda c: c.client.start_charging(c.vin),
    ),
    SkodaButtonDescription(
        key="stop_charging",
        translation_key="stop_charging",
        icon="mdi:ev-station",
        operation=Op.STOP_CHARGING,
        capability=Cap.CHARGING,
        press_fn=lambda c: c.client.stop_charging(c.vin),
    ),
)


def _supported(desc: SkodaButtonDescription, coordinator: SkodaCoordinator) -> bool:
    data = coordinator.data
    if data.operations is not None:
        return desc.operation in data.operations
    # No operations list in this response: fall back to the capability.
    return desc.capability in data.capabilities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = [SkodaRefreshButton(coordinator)]
    entities += [
        SkodaCommandButton(coordinator, d) for d in BUTTONS if _supported(d, coordinator)
    ]
    async_add_entities(entities)


class SkodaRefreshButton(SkodaEntity, ButtonEntity):
    """Fetch new data now (costs one request of the hourly quota)."""

    _attr_translation_key = "refresh"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "refresh")

    async def async_press(self) -> None:
        await self.coordinator.async_refresh()


class SkodaCommandButton(SkodaEntity, ButtonEntity):
    """Send a remote command to the car."""

    entity_description: SkodaButtonDescription

    def __init__(self, coordinator: SkodaCoordinator, description: SkodaButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self.coordinator)
        except OpenApiRateLimitError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="rate_limited"
            ) from err
        except OpenApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        @callback
        def _refresh(_now) -> None:
            self.hass.async_create_task(self.coordinator.async_request_refresh())

        async_call_later(self.hass, REFRESH_DELAY, _refresh)
