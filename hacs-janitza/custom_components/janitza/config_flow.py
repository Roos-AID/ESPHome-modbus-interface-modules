"""Config flow for Janitza power analysers."""

import logging
from typing import TYPE_CHECKING, Any, override

import probatio
from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import ConfigEntryState, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SerialPortSelector,
    TextSelector,
)
from modbus_connection import ModbusError

from .const import (
    CONF_BAUDRATE,
    CONF_MODEL,
    CONF_UNIT_ID,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MODEL_NAMES,
    MODEL_UMG96RM,
    MODEL_UMG508,
    TYPE_SERIAL,
    TYPE_TCP,
)
from .helpers import create_modbus_params, link_identifier, model_of
from .janitza_modbus import JanitzaDevice, JanitzaMeter, Umg508

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

STEP_USER = "user"
STEP_CONNECTION = "connection"
STEP_UMG96RM = "umg_96rm"
STEP_UMG508 = "umg_508"
STEP_RECONFIGURE_SERIAL = "reconfigure_serial"
STEP_RECONFIGURE_TCP = "reconfigure_tcp"

UNIT_ID_SELECTOR = probatio.All(
    NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=247)),
    probatio.Coerce(int),
)

STEP_TCP_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_HOST): TextSelector(),
        probatio.Required(CONF_PORT, default=DEFAULT_PORT): probatio.All(
            NumberSelector(
                NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1, max=65535)
            ),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
    }
)

STEP_SERIAL_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_DEVICE): SerialPortSelector(),
        probatio.Required(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): probatio.All(
            NumberSelector(NumberSelectorConfig(mode=NumberSelectorMode.BOX, min=1)),
            probatio.Coerce(int),
        ),
        probatio.Required(CONF_UNIT_ID, default=DEFAULT_UNIT_ID): UNIT_ID_SELECTOR,
    }
)


async def _async_probe(hass: HomeAssistant, data: Mapping[str, Any]) -> JanitzaDevice:
    """Connect to the meter and identify it, or raise."""
    params = create_modbus_params(data)
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT_ID]) as unit:
        if model_of(data) == MODEL_UMG508:
            return await Umg508.async_detect(unit)
        return await JanitzaMeter.async_detect(unit)


class JanitzaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a Janitza config flow."""

    VERSION = 1

    _model: str = MODEL_UMG96RM

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user pick which meter model is being set up."""
        return self.async_show_menu(
            step_id=STEP_USER, menu_options=[STEP_UMG96RM, STEP_UMG508]
        )

    async def async_step_umg_96rm(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - the step signature
    ) -> ConfigFlowResult:
        """Handle a UMG 96RM."""
        self._model = MODEL_UMG96RM
        return await self.async_step_connection()

    async def async_step_umg_508(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - the step signature
    ) -> ConfigFlowResult:
        """Handle a UMG 508."""
        self._model = MODEL_UMG508
        return await self.async_step_connection()

    async def async_step_connection(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - the step signature
    ) -> ConfigFlowResult:
        """Let the user pick how the meter is reached."""
        return self.async_show_menu(
            step_id=STEP_CONNECTION, menu_options=[TYPE_TCP, TYPE_SERIAL]
        )

    async def async_step_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a meter reached over the network."""
        return await self._async_step_link(TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input)

    async def async_step_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a meter reached over a serial port."""
        return await self._async_step_link(
            TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_link(
        self,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the meter behind them."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {CONF_TYPE: connection_type, CONF_MODEL: self._model, **user_input}
            device, errors, description_placeholders = await self._async_validate(data)
            if device is not None:
                # A meter that reports a serial number is known by it; one that
                # does not is known by where it is reached.
                unique_id = (
                    device.serial_number
                    if device.has_serial_number
                    else link_identifier(data)
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=MODEL_NAMES[self._model], data=data
                )

        return self.async_show_form(
            step_id=connection_type,
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002 - the step signature
    ) -> ConfigFlowResult:
        """Handle updating an existing entry's connection details."""
        entry = self._get_reconfigure_entry()
        if entry.data[CONF_TYPE] == TYPE_SERIAL:
            return await self.async_step_reconfigure_serial()
        return await self.async_step_reconfigure_tcp()

    async def async_step_reconfigure_tcp(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle updating a meter reached over the network."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_TCP, TYPE_TCP, STEP_TCP_DATA_SCHEMA, user_input
        )

    async def async_step_reconfigure_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle updating a meter reached over a serial port."""
        return await self._async_step_reconfigure_link(
            STEP_RECONFIGURE_SERIAL, TYPE_SERIAL, STEP_SERIAL_DATA_SCHEMA, user_input
        )

    async def _async_step_reconfigure_link(
        self,
        step_id: str,
        connection_type: str,
        schema: probatio.Schema,
        user_input: dict[str, Any] | None,
    ) -> ConfigFlowResult:
        """Ask for the link settings, then probe the entry's own meter."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            data = {
                CONF_TYPE: connection_type,
                CONF_MODEL: model_of(entry.data),
                **user_input,
            }

            relinking = False
            if entry.state in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY):
                current = create_modbus_params(entry.data)
                new = create_modbus_params(data)
                if new.endpoint == current.endpoint and new != current:
                    relinking = await self.hass.config_entries.async_unload(
                        entry.entry_id
                    )

            device, errors, description_placeholders = await self._async_validate(data)
            # A meter with no serial number of its own cannot be told from
            # another by probing it, so a new link is taken at its word.
            probed: str | None = None
            if device is not None:
                probed = (
                    device.serial_number
                    if device.has_serial_number
                    else entry.unique_id
                )

            if relinking and probed != entry.unique_id:
                await self.hass.config_entries.async_setup(entry.entry_id)

            if device is not None:
                await self.async_set_unique_id(probed)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                schema, user_input or entry.data
            ),
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def _async_validate(
        self, data: dict[str, Any]
    ) -> tuple[JanitzaDevice | None, dict[str, str], dict[str, str]]:
        """Probe the meter, returning it or the errors to show instead."""
        try:
            device = await _async_probe(self.hass, data)
        except (ModbusError, HomeAssistantError) as err:
            return None, {"base": "cannot_connect"}, {"error": str(err)}

        if device.unrecognized:
            error = (
                "unrecognized_umg508"
                if model_of(data) == MODEL_UMG508
                else "unrecognized_meter"
            )
            return None, {"base": error}, {}

        return device, {}, {}
