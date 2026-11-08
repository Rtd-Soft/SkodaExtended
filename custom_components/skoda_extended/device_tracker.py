"""Parking position as a device tracker."""

from __future__ import annotations

from skoda_public_api.models.enums import VehicleCapability

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SkodaConfigEntry, SkodaCoordinator
from .entity import SkodaEntity
from .helpers import enum_state, get

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if VehicleCapability.PARKING_POSITION in coordinator.data.capabilities:
        async_add_entities([SkodaTracker(coordinator)])


class SkodaTracker(SkodaEntity, TrackerEntity):
    """Where the car is parked. While driving the API gives no coordinates."""

    _attr_translation_key = "position"
    _attr_icon = "mdi:car"

    def __init__(self, coordinator: SkodaCoordinator) -> None:
        super().__init__(coordinator, "position")
        self._last_lat: float | None = None
        self._last_lon: float | None = None

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    def _coords(self):
        return get(self.vehicle, "parking_position", "gps_coordinates")

    @property
    def latitude(self) -> float | None:
        coords = self._coords()
        if coords is not None:
            self._last_lat = coords.latitude
        return self._last_lat

    @property
    def longitude(self) -> float | None:
        coords = self._coords()
        if coords is not None:
            self._last_lon = coords.longitude
        return self._last_lon

    @property
    def location_accuracy(self) -> float:
        return 0

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "address": get(self.vehicle, "parking_position", "formatted_address"),
            "movement": enum_state(get(self.vehicle, "parking_position", "state")),
        }
