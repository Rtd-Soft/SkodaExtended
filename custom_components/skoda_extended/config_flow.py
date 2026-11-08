"""Config flow for Škoda Extended."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from skoda_public_api.api_layer.exceptions import (
    OpenApiAuthenticationError,
    OpenApiError,
    OpenApiForbiddenError,
    OpenApiRateLimitError,
    OpenApiVehicleNotFoundError,
)
from skoda_public_api.api_layer.open_api_client import OpenAPIClient
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    API_KEYS_URL,
    CONF_AUX_DURATION,
    CONF_SCAN_INTERVAL,
    CONF_SPIN,
    CONF_VIN,
    DEFAULT_AUX_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class SkodaExtendedConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _validate(self, vin: str, api_key: str) -> tuple[str | None, str | None]:
        """Return (error, vehicle name)."""
        client = OpenAPIClient(api_key=api_key, session=async_get_clientsession(self.hass))
        try:
            response = await client.get_vehicle(vin, include=None)
        except OpenApiAuthenticationError:
            return "invalid_auth", None
        except (OpenApiForbiddenError, OpenApiVehicleNotFoundError):
            return "vin_not_authorized", None
        except OpenApiRateLimitError:
            return "rate_limited", None
        except OpenApiError:
            _LOGGER.exception("Unexpected API error during setup")
            return "cannot_connect", None
        return None, response.vehicle.name

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            vin = user_input[CONF_VIN].strip().upper()
            await self.async_set_unique_id(vin)
            self._abort_if_unique_id_configured()
            if len(vin) != 17:
                errors[CONF_VIN] = "invalid_vin"
            else:
                error, name = await self._validate(vin, user_input[CONF_API_KEY].strip())
                if error:
                    errors["base"] = error
                else:
                    return self.async_create_entry(
                        title=name or f"Škoda {vin[-6:]}",
                        data={CONF_VIN: vin, CONF_API_KEY: user_input[CONF_API_KEY].strip()},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIN): str,
                    vol.Required(CONF_API_KEY): _PASSWORD,
                }
            ),
            errors=errors,
            description_placeholders={"url": API_KEYS_URL},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            key = user_input[CONF_API_KEY].strip()
            error, _ = await self._validate(entry.data[CONF_VIN], key)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: key}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): _PASSWORD}),
            errors=errors,
            description_placeholders={"url": API_KEYS_URL},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SkodaExtendedOptionsFlow()


class SkodaExtendedOptionsFlow(OptionsFlow):
    """Polling interval, S-PIN and auxiliary heating duration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if not user_input.get(CONF_SPIN):
                user_input.pop(CONF_SPIN, None)
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=1,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    CONF_SPIN,
                    description={"suggested_value": opts.get(CONF_SPIN)},
                ): _PASSWORD,
                vol.Required(
                    CONF_AUX_DURATION,
                    default=opts.get(CONF_AUX_DURATION, DEFAULT_AUX_DURATION),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=10, max=60, step=5,
                        unit_of_measurement="min",
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
