"""Sensors for Škoda Extended."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from skoda_public_api.models.enums import (
    AirConditioningState,
    AuxiliaryHeatingStartMode,
    AuxiliaryHeatingState,
    ChargeMode,
    ChargeType,
    ChargingState,
    DoorsState,
    MovementState,
    PlugConnectionState,
    TemperatureUnit,
    VehicleCapability as Cap,
    VentilationState,
)
from skoda_public_api.models.vehicle import VehicleObject

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfElectricCurrent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import SkodaConfigEntry, SkodaCoordinator, SkodaData
from .entity import SkodaEntity
from .helpers import enum_options, enum_state, get, timestamp

PARALLEL_UPDATES = 0

_COMBUSTION = {Cap.VEHICLE_TYPE_GASOLINE, Cap.VEHICLE_TYPE_DIESEL,
               Cap.VEHICLE_TYPE_HYBRID, Cap.VEHICLE_TYPE_CNG, Cap.VEHICLE_TYPE_LPG}


@dataclass(frozen=True, kw_only=True)
class SkodaSensorDescription(SensorEntityDescription):
    """Sensor description."""

    value_fn: Callable[[VehicleObject], StateType | datetime]
    exists_fn: Callable[[SkodaData], bool]
    attrs_fn: Callable[[VehicleObject], dict[str, Any]] | None = None
    unit_fn: Callable[[VehicleObject], str | None] | None = None


def _cap(*caps: Cap) -> Callable[[SkodaData], bool]:
    return lambda d: all(c in d.capabilities for c in caps)


def _present(*path: str) -> Callable[[SkodaData], bool]:
    return lambda d: get(d.response.vehicle, *path) is not None


def _fuel_engine(v: VehicleObject):
    """The engine that reports a fuel level (primary, else secondary)."""
    for name in ("primary_engine_range", "secondary_engine_range"):
        engine = get(v, "fuel_status", name)
        if engine is not None and engine.current_fuel_level_in_percent is not None:
            return engine
    return None


def _electric_engine(v: VehicleObject):
    for name in ("primary_engine_range", "secondary_engine_range"):
        engine = get(v, "fuel_status", name)
        if engine is not None and (engine.engine_type or "").upper() == "ELECTRIC":
            return engine
    return None


def _temp_unit(temp) -> str | None:
    if temp is None:
        return None
    if temp.unit == TemperatureUnit.FAHRENHEIT:
        return UnitOfTemperature.FAHRENHEIT
    return UnitOfTemperature.CELSIUS


def _last_captured(v: VehicleObject) -> datetime | None:
    stamps = [
        timestamp(get(v, *p))
        for p in (
            ("status", "car_captured_timestamp"),
            ("odometer", "car_captured_timestamp"),
            ("fuel_status", "car_captured_timestamp"),
            ("air_conditioning", "car_captured_timestamp"),
            ("auxiliary_heating", "car_captured_timestamp"),
            ("charging", "car_captured_timestamp"),
        )
    ]
    stamps = [s for s in stamps if s is not None]
    return max(stamps) if stamps else None


def _minutes(seconds: int | None) -> float | None:
    return None if seconds is None else round(seconds / 60, 1)


VEHICLE_SENSORS: tuple[SkodaSensorDescription, ...] = (
    # --- Odometer & range -------------------------------------------------
    SkodaSensorDescription(
        key="mileage",
        translation_key="mileage",
        icon="mdi:counter",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda v: get(v, "odometer", "mileage_in_km"),
        exists_fn=_cap(Cap.ODOMETER),
    ),
    SkodaSensorDescription(
        key="fuel_level",
        translation_key="fuel_level",
        icon="mdi:gas-station",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(_fuel_engine(v), "current_fuel_level_in_percent"),
        exists_fn=lambda d: Cap.FUEL_STATUS in d.capabilities
        and bool(d.capabilities & _COMBUSTION),
    ),
    SkodaSensorDescription(
        key="total_range",
        translation_key="total_range",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(v, "fuel_status", "total_range_in_km"),
        exists_fn=_cap(Cap.FUEL_STATUS),
    ),
    SkodaSensorDescription(
        key="combustion_range",
        translation_key="combustion_range",
        icon="mdi:gas-station-outline",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(_fuel_engine(v), "remaining_range_in_km"),
        exists_fn=lambda d: Cap.FUEL_STATUS in d.capabilities
        and bool(d.capabilities & _COMBUSTION),
    ),
    SkodaSensorDescription(
        key="electric_range",
        translation_key="electric_range",
        icon="mdi:ev-station",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(_electric_engine(v), "remaining_range_in_km"),
        exists_fn=_cap(Cap.VEHICLE_TYPE_ELECTRIC),
    ),
    SkodaSensorDescription(
        key="adblue_range",
        translation_key="adblue_range",
        icon="mdi:water",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(v, "fuel_status", "ad_blue_range"),
        exists_fn=_cap(Cap.AD_BLUE_RANGE),
    ),
    SkodaSensorDescription(
        key="car_type",
        translation_key="car_type",
        icon="mdi:car-info",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: (get(v, "fuel_status", "car_type") or "").lower() or None,
        exists_fn=_present("fuel_status", "car_type"),
    ),
    # --- Locks, doors, overall status -------------------------------------
    SkodaSensorDescription(
        key="lock_state",
        translation_key="lock_state",
        icon="mdi:car-key",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(DoorsState),
        value_fn=lambda v: enum_state(get(v, "status", "overall", "doors_locked")),
        exists_fn=_cap(Cap.STATUS),
    ),
    # --- Parking ------------------------------------------------------------
    SkodaSensorDescription(
        key="parking_address",
        translation_key="parking_address",
        icon="mdi:map-marker",
        value_fn=lambda v: get(v, "parking_position", "formatted_address"),
        exists_fn=_cap(Cap.PARKING_POSITION),
    ),
    SkodaSensorDescription(
        key="movement_state",
        translation_key="movement_state",
        icon="mdi:car-arrow-right",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(MovementState),
        value_fn=lambda v: enum_state(get(v, "parking_position", "state")),
        exists_fn=_cap(Cap.PARKING_POSITION),
    ),
    # --- Air conditioning ---------------------------------------------------
    SkodaSensorDescription(
        key="air_conditioning_state",
        translation_key="air_conditioning_state",
        icon="mdi:air-conditioner",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(AirConditioningState),
        value_fn=lambda v: enum_state(get(v, "air_conditioning", "state")),
        exists_fn=_cap(Cap.AIR_CONDITIONING),
    ),
    SkodaSensorDescription(
        key="air_conditioning_target_temperature",
        translation_key="air_conditioning_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(v, "air_conditioning", "target_temperature", "value"),
        unit_fn=lambda v: _temp_unit(get(v, "air_conditioning", "target_temperature")),
        exists_fn=_present("air_conditioning", "target_temperature"),
    ),
    SkodaSensorDescription(
        key="air_conditioning_target_reached_at",
        translation_key="air_conditioning_target_reached_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda v: timestamp(
            get(v, "air_conditioning", "estimated_reach_of_target_temperature_at")
        ),
        exists_fn=_cap(Cap.AIR_CONDITIONING),
    ),
    # --- Auxiliary heating --------------------------------------------------
    SkodaSensorDescription(
        key="auxiliary_heating_state",
        translation_key="auxiliary_heating_state",
        icon="mdi:radiator",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(AuxiliaryHeatingState),
        value_fn=lambda v: enum_state(get(v, "auxiliary_heating", "state")),
        exists_fn=_cap(Cap.AUXILIARY_HEATING),
    ),
    SkodaSensorDescription(
        key="auxiliary_heating_mode",
        translation_key="auxiliary_heating_mode",
        icon="mdi:radiator",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(AuxiliaryHeatingStartMode),
        value_fn=lambda v: enum_state(get(v, "auxiliary_heating", "start_mode")),
        exists_fn=_cap(Cap.AUXILIARY_HEATING),
    ),
    SkodaSensorDescription(
        key="auxiliary_heating_duration",
        translation_key="auxiliary_heating_duration",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda v: _minutes(get(v, "auxiliary_heating", "duration_in_seconds")),
        exists_fn=_cap(Cap.AUXILIARY_HEATING),
    ),
    SkodaSensorDescription(
        key="auxiliary_heating_target_temperature",
        translation_key="auxiliary_heating_target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(v, "auxiliary_heating", "target_temperature", "value"),
        unit_fn=lambda v: _temp_unit(get(v, "auxiliary_heating", "target_temperature")),
        exists_fn=_present("auxiliary_heating", "target_temperature"),
    ),
    SkodaSensorDescription(
        key="auxiliary_heating_target_reached_at",
        translation_key="auxiliary_heating_target_reached_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda v: timestamp(
            get(v, "auxiliary_heating", "estimated_reach_of_target_temperature_at")
        ),
        exists_fn=_cap(Cap.AUXILIARY_HEATING),
    ),
    # --- Active ventilation -------------------------------------------------
    SkodaSensorDescription(
        key="ventilation_state",
        translation_key="ventilation_state",
        icon="mdi:fan",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(VentilationState),
        value_fn=lambda v: enum_state(get(v, "active_ventilation", "state")),
        exists_fn=_cap(Cap.ACTIVE_VENTILATION),
    ),
    SkodaSensorDescription(
        key="ventilation_duration",
        translation_key="ventilation_duration",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda v: _minutes(get(v, "active_ventilation", "duration_in_seconds")),
        exists_fn=_cap(Cap.ACTIVE_VENTILATION),
    ),
    # --- Charging (PHEV / BEV) ---------------------------------------------
    SkodaSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(v, "charging", "status", "battery", "state_of_charge_in_percent")
        or get(_electric_engine(v), "current_soc_in_percent"),
        exists_fn=lambda d: Cap.CHARGING in d.capabilities
        or Cap.VEHICLE_TYPE_ELECTRIC in d.capabilities,
    ),
    SkodaSensorDescription(
        key="charging_state",
        translation_key="charging_state",
        icon="mdi:ev-plug-type2",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ChargingState),
        value_fn=lambda v: enum_state(get(v, "charging", "status", "state")),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaSensorDescription(
        key="charge_type",
        translation_key="charge_type",
        icon="mdi:current-ac",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ChargeType),
        value_fn=lambda v: enum_state(get(v, "charging", "status", "charge_type")),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaSensorDescription(
        key="charging_power",
        translation_key="charging_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(v, "charging", "status", "charge_power_in_kw"),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaSensorDescription(
        key="charging_rate",
        translation_key="charging_rate",
        icon="mdi:speedometer",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda v: get(v, "charging", "status", "charging_rate_in_kilometers_per_hour"),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaSensorDescription(
        key="fully_charged_at",
        translation_key="fully_charged_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda v: timestamp(get(v, "charging", "status", "fully_charged_at")),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaSensorDescription(
        key="charge_remaining_time",
        translation_key="charge_remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda v: get(
            v, "charging", "status", "remaining_time_to_fully_charged_in_minutes"
        ),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaSensorDescription(
        key="plug_state",
        translation_key="plug_state",
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(PlugConnectionState),
        value_fn=lambda v: enum_state(get(v, "charging", "status", "plug_connection_state")),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaSensorDescription(
        key="charge_limit",
        translation_key="charge_limit",
        icon="mdi:battery-charging-80",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda v: get(v, "charging", "settings", "target_state_of_charge_in_percent"),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaSensorDescription(
        key="charge_mode",
        translation_key="charge_mode",
        icon="mdi:cog",
        device_class=SensorDeviceClass.ENUM,
        options=enum_options(ChargeMode),
        value_fn=lambda v: enum_state(get(v, "charging", "settings", "preferred_charge_mode")),
        exists_fn=_cap(Cap.CHARGING),
    ),
    SkodaSensorDescription(
        key="max_charge_current",
        translation_key="max_charge_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: get(v, "charging", "settings", "max_charge_current_ac_ampere"),
        exists_fn=_present("charging", "settings", "max_charge_current_ac_ampere"),
    ),
    # --- Diagnostics --------------------------------------------------------
    SkodaSensorDescription(
        key="license_plate",
        translation_key="license_plate",
        icon="mdi:card-text-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda v: v.license_plate,
        exists_fn=_present("license_plate"),
    ),
    SkodaSensorDescription(
        key="last_captured",
        translation_key="last_captured",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_last_captured,
        exists_fn=lambda d: True,
        attrs_fn=lambda v: {"render_url": v.render_url} if v.render_url else {},
    ),
)


@dataclass(frozen=True, kw_only=True)
class SkodaApiSensorDescription(SensorEntityDescription):
    """Sensor that reads from the poll metadata rather than the vehicle."""

    value_fn: Callable[[SkodaData], StateType | datetime]


API_SENSORS: tuple[SkodaApiSensorDescription, ...] = (
    SkodaApiSensorDescription(
        key="rate_limit_remaining",
        translation_key="rate_limit_remaining",
        icon="mdi:speedometer-slow",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.rate_limit_remaining,
    ),
    SkodaApiSensorDescription(
        key="api_key_expires",
        translation_key="api_key_expires",
        icon="mdi:key-chain",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: timestamp(d.api_key_expires_at),
    ),
    SkodaApiSensorDescription(
        key="api_errors",
        translation_key="api_errors",
        icon="mdi:alert-circle-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: len(d.response.errors),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors the car supports."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        SkodaSensor(coordinator, d)
        for d in VEHICLE_SENSORS
        if d.exists_fn(coordinator.data)
    ]
    entities += [SkodaApiSensor(coordinator, d) for d in API_SENSORS]
    async_add_entities(entities)


class SkodaSensor(SkodaEntity, SensorEntity):
    """A vehicle value."""

    entity_description: SkodaSensorDescription

    def __init__(self, coordinator: SkodaCoordinator, description: SkodaSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.vehicle)

    @property
    def native_unit_of_measurement(self) -> str | None:
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.vehicle) or UnitOfTemperature.CELSIUS
        return super().native_unit_of_measurement

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.vehicle)


class SkodaApiSensor(SkodaEntity, SensorEntity):
    """API metadata (rate limit, key expiry)."""

    entity_description: SkodaApiSensorDescription

    def __init__(self, coordinator: SkodaCoordinator, description: SkodaApiSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "api_errors":
            return {
                "errors": [
                    str(getattr(e.type, "value", e.type)) for e in self.coordinator.data.response.errors
                ]
            }
        if self.entity_description.key == "rate_limit_remaining":
            return {"reset_in_seconds": self.coordinator.data.rate_limit_reset}
        return None
