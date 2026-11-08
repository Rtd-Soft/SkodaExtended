"""Picture of the car (render from the API)."""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import SkodaConfigEntry, SkodaCoordinator
from .entity import SkodaEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    if coordinator.data.response.vehicle.render_url:
        async_add_entities([SkodaRenderImage(hass, coordinator)])


class SkodaRenderImage(SkodaEntity, ImageEntity):
    """Render of the car as shown in the MyŠkoda app."""

    _attr_translation_key = "render"
    _attr_content_type = "image/png"

    def __init__(self, hass: HomeAssistant, coordinator: SkodaCoordinator) -> None:
        SkodaEntity.__init__(self, coordinator, "render")
        ImageEntity.__init__(self, hass)
        self._attr_image_url = self.vehicle.render_url
        self._attr_image_last_updated = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        url = self.vehicle.render_url
        if url and url != self._attr_image_url:
            self._attr_image_url = url
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()
