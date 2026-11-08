"""Base entity for Škoda Extended."""

from __future__ import annotations

from skoda_public_api.models.vehicle import VehicleObject

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SkodaCoordinator


class SkodaEntity(CoordinatorEntity[SkodaCoordinator]):
    """Common device info and unique id handling."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SkodaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        vin = coordinator.vin
        vehicle = coordinator.data.response.vehicle
        self._attr_unique_id = f"{vin}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vin)},
            manufacturer="Škoda",
            name=vehicle.name or f"Škoda {vin[-6:]}",
            serial_number=vin,
        )

    @property
    def vehicle(self) -> VehicleObject:
        """Current vehicle object."""
        return self.coordinator.data.response.vehicle
