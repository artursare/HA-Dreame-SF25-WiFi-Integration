"""Config flow para Dreame SF25."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .api import DreameApiError, DreameAuthError, DreameSF25Client
from .const import (
    CONF_AUTO_COMPACT,
    CONF_AUTO_MODES,
    CONF_AUTO_STIR,
    CONF_COMPACT_DURATION,
    CONF_DID,
    CONF_REGION,
    CONF_SAFETY_STOP,
    CONF_STIR_DURATION,
    CONF_STIR_THRESHOLD,
    CONF_VIRTUAL_MODES,
    OPTION_DEFAULTS,
    DEFAULT_REGION,
    DOMAIN,
    REGIONS,
)

_LOGGER = logging.getLogger(__name__)


class DreameSF25ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flujo de configuracion (email + contrasena + region)."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        return DreameSF25OptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = DreameSF25Client(
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                user_input[CONF_REGION],
            )
            try:
                device = await self.hass.async_add_executor_job(client.resolve_device)
            except DreameAuthError:
                errors["base"] = "invalid_auth"
            except DreameApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error inesperado en config flow")
                errors["base"] = "unknown"
            else:
                did = str(device.get("did"))
                await self.async_set_unique_id(did)
                self._abort_if_unique_id_configured()
                name = device.get("customName") or device.get("deviceInfo", {}).get(
                    "displayName", "Dreame SF25"
                )
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_REGION: user_input[CONF_REGION],
                        CONF_DID: did,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_REGION, default=DEFAULT_REGION): vol.In(REGIONS),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class DreameSF25OptionsFlow(OptionsFlow):
    """Opt-in for actions initiated by the integration itself."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self._entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTO_MODES, default=options.get(CONF_AUTO_MODES, False)
                    ): bool,
                    vol.Required(
                        CONF_SAFETY_STOP, default=options.get(CONF_SAFETY_STOP, False)
                    ): bool,
                    vol.Required(
                        CONF_VIRTUAL_MODES,
                        default=options.get(CONF_VIRTUAL_MODES, False),
                    ): bool,
                    # Detalle dentro de auto_modes: solo cuentan cuando este
                    # ya esta activado, asi que el defecto seguro no cambia.
                    vol.Required(
                        CONF_AUTO_STIR, default=_cur(options, CONF_AUTO_STIR)
                    ): bool,
                    vol.Required(
                        CONF_STIR_THRESHOLD, default=_cur(options, CONF_STIR_THRESHOLD)
                    ): vol.All(int, vol.Range(min=1, max=99)),
                    vol.Required(
                        CONF_STIR_DURATION, default=_cur(options, CONF_STIR_DURATION)
                    ): vol.All(int, vol.Range(min=1, max=90)),
                    vol.Required(
                        CONF_AUTO_COMPACT, default=_cur(options, CONF_AUTO_COMPACT)
                    ): bool,
                    vol.Required(
                        CONF_COMPACT_DURATION,
                        default=_cur(options, CONF_COMPACT_DURATION),
                    ): vol.All(int, vol.Range(min=1, max=180)),
                }
            ),
        )


def _cur(options, key):
    """Valor actual de una opcion de detalle, con su defecto historico."""
    return options.get(key, OPTION_DEFAULTS[key])
