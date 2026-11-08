"""Binary sensors for Škoda Extended."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from skoda_public_api.models.enums import VehicleCapability as Cap
from skoda_public_api.models.vehicle import VehicleObject

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaCoordinator, SkodaData
from .entity import SkodaEntity
from .helpers import get, is_on

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SkodaBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description."""

    value_fn: Callable[[VehicleObject], bool | None]
    exists_fn: Callable[[SkodaData], bool]


def _cap(*caps: Cap) -> Callable[[SkodaData], bool]:
    return lambda d: all(c in d.capabilities for c in caps)


def _present(*path: str) -> Callable[[SkodaData], bool]:
    return lambda d: get(d.response.vehicle, *path) is not None


def _bool(value: bool | None) -> bool | None:
    return value


def _unlocked(v: VehicleObject) -> bool | None:
    # LOCK device class: on = unlocked. Prefer the "reliable" lock state.
    reliable = get(v, "status", "overall", "reliable_lock_status")
    state = is_on(reliable, "UNLOCKED")
    if state is not None:
        return state
    locked = is_on(get(v, "status", "overall", "locked"), "YES")
    return None if locked is None else not locked


BINARY_SENSORS: tuple[SkodaBinaryDescription, ...] = (
    SkodaBinaryDescription(
        key="lock",
        translation_key="lock",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=_unlocked,
        exists_fn=_cap(Cap.STATUS),
    ),
    SkodaBinaryDescription(
        key="doors",
        translation_key="doors",
        device_class=BinarySensorDeviceClass.DOOR,
        value_fn=lambda v: is_on(get(v, "status", "overall", "doors"), "OPEN"),
        exists_fn=_cap(Cap.STATUS),
    ),
    SkodaBinaryDescription(
        key="windows",
        translation_key="windows",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda v: is_on(get(v, "status", "overall", "windows"), "OPEN"),
        exists_fn=_cap(Cap.STATUS),
    ),
    SkodaBinaryDescription(
        key="trunk",
        translation_key="trunk",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=lambda v: is_on(get(v, "status", "detail", "trunk"), "OPEN"),
        exists_fn=_cap(Cap.STATUS),
    ),
    SkodaBinaryDescription(
        key="bonnet",
        translation_key="bonnet",
        device_class=BinarySensorDeviceClass.OPENING,
        value_fn=lambda v: is_on(get(v, "status", "detail", "bonnet"), "OPEN"),
        exists_fn=_cap(Cap.STATUS),
    ),
    SkodaBinaryDescription(
        key="sunroof",
        translation_key="sunroof",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda v: is_on(get(v, "status", "detail", "sunroof"), "OPEN"),
        exists_fn=_cap(Cap.SUNROOF),
    ),
    SkodaBinaryDescription(
        key="lights",
        translation_key="lights",
        device_class=BinarySensorDeviceClass.LIGHT,
        value_fn=lambda v: is_on(get(v, "status", "overall", "lights"), "ON"),
        exists_fn=_cap(Cap.STATUS),
    ),
    SkodaBinaryDescription(
        key="parked",
        translation_key="parked",
        icon="mdi:parking",
        value_fn=lambda v: is_on(get(v, "parking_position", "state"), "PARKED"),
        exists_fn=_cap(Cap.PARKING_POSITION),
    ),
    SkodaBinaryDescription(
        key="window_heating_front",
        translation_key="window_heating_front",
        icon="mdi:car-defrost-front",
        value_fn=lambda v: is_on(get(v, "air_conditioning", "window_heating", "front"), "ON"),
        exists_fn=_present("air_conditioning", "window_heating", "front"),
    ),
    SkodaBinaryDescription(
        key="window_heating_rear",
        translation_key="window_heating_rear",
        icon="mdi:car-defrost-rear",
        value_fn=lambda v: is_on(get(v, "air_conditioning", "window_heating", "rear"), "ON"),
        exists_fn=_present("air_conditioning", "window_heating", "rear"),
    ),
    SkodaBinaryDescription(
        key="window_heating_enabled",
        translation_key="window_heating_enabled",
        icon="mdi:car-defrost-front",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: get(v, "air_conditioning", "window_heating", "enabled"),
        exists_fn=_present("air_conditioning", "window_heating", "enabled"),
    ),
    SkodaBinaryDescription(
        key="air_conditioning_at_unlock",
        translation_key="air_conditioning_at_unlock",
        icon="mdi:car-key",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: get(v, "air_conditioning", "air_conditioning_at_unlock"),
        exists_fn=_present("air_conditioning", "air_conditioning_at_unlock"),
    ),
    SkodaBinaryDescription(
        key="air_conditioning_without_external_power",
        translation_key="air_conditioning_without_external_power",
        icon="mdi:power-plug-off",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: get(v, "air_conditioning", "air_conditioning_without_external_power"),
        exists_fn=_present("air_conditioning", "air_conditioning_without_external_power"),
    ),
    SkodaBinaryDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda v: is_on(get(v, "charging", "status", "state"), "CHARGING"),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaBinaryDescription(
        key="plug_connected",
        translation_key="plug_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value_fn=lambda v: is_on(
            get(v, "charging", "status", "plug_connection_state"), "CONNECTED"
        ),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaBinaryDescription(
        key="at_saved_location",
        translation_key="at_saved_location",
        icon="mdi:home-map-marker",
        value_fn=lambda v: get(v, "charging", "is_vehicle_in_saved_location"),
        exists_fn=_cap(Cap.CHARGING),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        SkodaBinarySensor(coordinator, d)
        for d in BINARY_SENSORS
        if d.exists_fn(coordinator.data)
    )


class SkodaBinarySensor(SkodaEntity, BinarySensorEntity):
    """A vehicle on/off value."""

    entity_description: SkodaBinaryDescription

    def __init__(self, coordinator: SkodaCoordinator, description: SkodaBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.vehicle)
