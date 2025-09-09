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

# Stanja zaklepanja kabla
SOCKET_LOCK_STATES = {
    17: "Cable unlocked",
    273: "Cable locked",
}