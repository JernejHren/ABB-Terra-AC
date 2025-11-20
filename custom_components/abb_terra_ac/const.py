"""Konstante za integracijo ABB Terra AC."""

DOMAIN = "abb_terra_ac"
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 15

# Platforme (odstranjena 'select' platforma)
PLATFORMS = ["sensor", "switch", "number"]

# Konfiguracijske vrednosti
CONF_HOST = "host"
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"

# Stanja polnilnice glede na IEC 61851-1 (preprosti ključi)
CHARGING_STATES = {
    0: "State A - Idle",
    1: "State B1 - EV Plug in, pending authorization",
    2: "State B2 - EV Plug in, charging complete",
    3: "State C1 - EV Ready for charge",
    4: "State C2 - Charging",
    5: "State D/F - Paused / Fault",
}

# Stanja zaklepanja kabla (dopolnjeno po priročniku)
SOCKET_LOCK_STATES = {
    0: "No cable plugged",
    1: "Cable connected, unlocked",
    17: "Cable connected, locked",
    257: "Cable & EV connected, unlocked",
    273: "Cable & EV connected, locked",
}

# Kode napak (dodano)
ERROR_CODES = {
    0: "No Error",
    2: "Residual Current Detected",
    4: "PE Missing or Swap Neutral/Phase",
    8: "Over Voltage",
    16: "Under Voltage",
    32: "Over Current",
    64: "Severe Over Current",
    128: "Over Temperature",
    1024: "Power Relay Fault",
    2048: "Internal Communication Failure",
    4096: "E-Lock Failure",
    8192: "Missing Phase",
    16384: "Modbus Communication Lost",
}
