"""Constants for the Janitza integration."""

DOMAIN = "janitza"
ATTR_MANUFACTURER = "Janitza"

CONF_MODEL = "model"
MODEL_UMG96RM = "umg96rm"
MODEL_UMG508 = "umg508"
MODELS = (MODEL_UMG96RM, MODEL_UMG508)
# Entries created before the UMG 508 was supported carry no model: a UMG 96RM.
DEFAULT_MODEL = MODEL_UMG96RM

MODEL_NAMES = {
    MODEL_UMG96RM: "UMG 96RM",
    MODEL_UMG508: "UMG 508",
}

DEFAULT_BAUDRATE = 115200
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
SCAN_INTERVAL = 10
SETTINGS_SCAN_INTERVAL = 300

CONF_BAUDRATE = "baudrate"
CONF_UNIT_ID = "unit_id"

TYPE_SERIAL = "serial"
TYPE_TCP = "tcp"
