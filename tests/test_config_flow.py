"""Config and options flow."""

from unittest.mock import AsyncMock, patch

import pytest
from skoda_public_api.api_layer.exceptions import OpenApiAuthenticationError
from skoda_public_api.models.vehicle import VehicleResponse

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.skoda_extended.const import DOMAIN

from .test_integration import PETROL, VIN

FLOW = "custom_components.skoda_extended.config_flow.OpenAPIClient"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(FLOW) as cls:
        cls.return_value.get_vehicle = AsyncMock(side_effect=OpenApiAuthenticationError("x"))
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"vin": VIN.lower(), "api_key": "bad"}
        )
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(FLOW) as cls, patch(
        "custom_components.skoda_extended.async_setup_entry", return_value=True
    ):
        cls.return_value.get_vehicle = AsyncMock(
            return_value=VehicleResponse.model_validate(PETROL)
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"vin": VIN.lower(), "api_key": " good "}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Octavia"
    assert result["data"] == {"vin": VIN, "api_key": "good"}

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    with patch("custom_components.skoda_extended.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"scan_interval": 6, "spin": "", "aux_heating_duration": 30},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"scan_interval": 6, "aux_heating_duration": 30}
