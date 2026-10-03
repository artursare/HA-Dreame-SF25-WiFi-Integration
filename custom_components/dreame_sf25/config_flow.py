"""Config flow para Dreame SF25."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .api import DreameApiError, DreameAuthError, DreameSF25Client
from homeassistant.core import callback

from .const import (
    CONF_DID,
    CONF_REGION,
    DEFAULT_REGION,
    DOMAIN,
    OPTION_DEFAULTS,
    OPT_COMPACT_DURATION,
    OPT_COMPACT_ENABLED,
    OPT_COMPACT_THRESHOLD,
    OPT_STIR_DURATION,
    OPT_STIR_ENABLED,
    OPT_STIR_THRESHOLD,
    REGIONS,
)

_LOGGER = logging.getLogger(__name__)


class DreameSF25ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Flujo de configuracion (email + contrasena + region)."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> DreameSF25OptionsFlow:
        """Flujo de opciones: disparos automaticos de Remover y Compactar."""
        return DreameSF25OptionsFlow()

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
    """Ajusta los disparos automaticos sin tocar const.py.

    Hasta ahora Remover y Compactar no se podian desactivar ni ajustar: el
    umbral era la constante LID_COUNT_THRESHOLD y las duraciones vivian en
    VIRTUAL_DURATIONS, asi que cualquier cambio se perdia en la siguiente
    actualizacion de HACS. Los valores por defecto son los historicos, de modo
    que no tocar nada deja el comportamiento igual que antes.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options

        def cur(key: str) -> Any:
            return opts.get(key, OPTION_DEFAULTS[key])

        schema = vol.Schema(
            {
                vol.Required(OPT_STIR_ENABLED, default=cur(OPT_STIR_ENABLED)): bool,
                vol.Required(
                    OPT_STIR_THRESHOLD, default=cur(OPT_STIR_THRESHOLD)
                ): vol.All(int, vol.Range(min=1, max=99)),
                vol.Required(
                    OPT_STIR_DURATION, default=cur(OPT_STIR_DURATION)
                ): vol.All(int, vol.Range(min=1, max=90)),
                vol.Required(OPT_COMPACT_ENABLED, default=cur(OPT_COMPACT_ENABLED)): bool,
                vol.Required(
                    OPT_COMPACT_THRESHOLD, default=cur(OPT_COMPACT_THRESHOLD)
                ): vol.All(int, vol.Range(min=1, max=99)),
                vol.Required(
                    OPT_COMPACT_DURATION, default=cur(OPT_COMPACT_DURATION)
                ): vol.All(int, vol.Range(min=1, max=180)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
