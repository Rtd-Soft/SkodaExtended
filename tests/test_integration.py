"""Load the integration against a mocked petrol-car response."""

from unittest.mock import AsyncMock, patch

import pytest
from skoda_public_api.models.vehicle import VehicleResponse

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.skoda_extended.const import CONF_SPIN, CONF_VIN, DOMAIN

VIN = "TMBJB9NY5RF999999"

PETROL = {
    "vehicle": {
        "vin": VIN,
        "name": "Octavia",
        "licensePlate": "AB-123-C",
        "renderUrl": "https://example.invalid/car.png",
        "odometer": {"mileageInKm": 48231, "carCapturedTimestamp": "2026-11-08T13:40:00Z"},
        "status": {
            "overall": {"doorsLocked": "YES", "locked": "YES", "doors": "CLOSED",
                        "windows": "CLOSED", "lights": "OFF", "reliableLockStatus": "LOCKED"},
            "detail": {"sunroof": "UNSUPPORTED", "trunk": "CLOSED", "bonnet": "CLOSED"},
            "carCapturedTimestamp": "2026-11-08T13:41:00Z",
        },
        "parkingPosition": {"state": "PARKED",
                            "gpsCoordinates": {"latitude": 51.88, "longitude": 4.49},
                            "formattedAddress": "Charloisse Hoofd, Rotterdam"},
        "auxiliaryHeating": {"state": "OFF", "startMode": "HEATING", "durationInSeconds": 1200,
                             "targetTemperature": {"value": 21.5, "unit": "CELSIUS"}},
        "airConditioning": {"state": "OFF",
                            "windowHeating": {"enabled": True, "front": "OFF", "rear": "OFF"}},
        "fuelStatus": {"carType": "GASOLINE", "totalRangeInKm": 612,
                       "primaryEngineRange": {"engineType": "GASOLINE",
                                              "currentFuelLevelInPercent": 64,
                                              "remainingRangeInKm": 612},
                       "carCapturedTimestamp": "2026-11-08T13:41:00Z"},
        "operations": [{"name": "startAuxiliaryHeating"}, {"name": "stopAuxiliaryHeating"}],
    },
    "errors": [
        {"type": "CHARGING_UNSUPPORTED"},
        {"type": "CHARGING_PROFILES_UNSUPPORTED"},
        {"type": "ACTIVE_VENTILATION_UNSUPPORTED"},
    ],
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def client():
    resp = VehicleResponse.model_validate(PETROL)
    with patch(
        "custom_components.skoda_extended.OpenAPIClient", autospec=True
    ) as cls:
        inst = cls.return_value
        inst.get_vehicle = AsyncMock(return_value=resp)
        inst.start_auxiliary_heating = AsyncMock()
        inst.rate_limit_remaining = 17
        inst.rate_limit_reset = 1800
        inst.api_key_expires_at = "2027-05-01T00:00:00Z"
        yield inst


async def test_petrol_car(hass: HomeAssistant, client) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=VIN, title="Octavia",
        data={CONF_VIN: VIN, "api_key": "x"}, options={CONF_SPIN: "1234"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    reg = er.async_get(hass)
    ents = sorted(
        (e.entity_id, hass.states.get(e.entity_id).state if hass.states.get(e.entity_id) else "disabled")
        for e in er.async_entries_for_config_entry(reg, entry.entry_id)
    )
    for eid, state in ents:
        print(f"{eid:60} {state}")

    s = lambda eid: hass.states.get(eid).state
    assert s("sensor.octavia_mileage") == "48231"
    assert s("sensor.octavia_fuel_level") == "64"
    assert s("sensor.octavia_lock_status") == "yes"
    assert s("binary_sensor.octavia_lock") == "off"  # locked
    assert s("sensor.octavia_auxiliary_heating") == "off"
    assert s("device_tracker.octavia_position") == "not_home" or s("device_tracker.octavia_position") == "home"
    assert hass.states.get("sensor.octavia_charging_state") is None  # petrol: no charging
    assert hass.states.get("binary_sensor.octavia_sunroof") is None
    assert hass.states.get("button.octavia_start_auxiliary_heating") is not None
    assert hass.states.get("button.octavia_start_climate_control") is None
    assert hass.states.get("image.octavia_picture") is not None

    await hass.services.async_call(
        "button", "press", {"entity_id": "button.octavia_start_auxiliary_heating"}, blocking=True
    )
    client.start_auxiliary_heating.assert_awaited_once()
    kwargs = client.start_auxiliary_heating.call_args.kwargs
    assert kwargs["spin"] == "1234" and kwargs["duration_in_seconds"] == 1200

    assert await hass.config_entries.async_unload(entry.entry_id)
