"""ABB Terra AC charger integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from datetime import timedelta

from homeassistant.components.modbus import async_get_unit
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusTcpParams,
    ModbusTimeoutError,
)

from .api import AbbTerraAcData, AbbTerraAcDevice
from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNIT_ID,
    DOMAIN,
    MODBUS_READ_TIMEOUT,
    PLATFORMS,
    build_unique_id,
)
from .session_state import LastCommand, SessionState, derive_session_state

_LOGGER = logging.getLogger(__name__)

# Consecutive failed polls (timeout or lost link) tolerated before entities go
# unavailable.
TOLERATED_FAILED_POLLS = 1

_ISSUE_ID_INVALID_FALLBACK_LIMIT = "invalid_fallback_limit"
_ISSUE_ID_INVALID_CURRENT_LIMIT = "invalid_current_limit"
_ISSUE_ID_SCAN_INTERVAL = "scan_interval_exceeds_timeout"


@dataclass
class AbbTerraAcRuntimeData:
    """Runtime objects stored on the config entry."""

    coordinator: AbbTerraAcDataUpdateCoordinator
    device: AbbTerraAcDevice


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ABB Terra AC from a config entry.

    The Modbus connection is owned and shared by the ``modbus`` integration.
    Asking for a unit performs no I/O and the hold on the connection is
    released automatically when this entry unloads.
    """
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
    )
    unit.require_timeout(MODBUS_READ_TIMEOUT)
    device = AbbTerraAcDevice(unit)
    coordinator = AbbTerraAcDataUpdateCoordinator(hass, device, entry)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = AbbTerraAcRuntimeData(coordinator=coordinator, device=device)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_reload_options))

    return True


async def _async_reload_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when integration options change (e.g. scan interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries to the latest schema (options, version bumps)."""
    if entry.version == 1:
        options = dict(entry.options)
        if CONF_SCAN_INTERVAL not in options:
            options[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL
        hass.config_entries.async_update_entry(entry, version=2, options=options)

    if entry.version == 2:
        # Version 3: Modbus unit ID is stored explicitly (shared Modbus connection).
        data = dict(entry.data)
        data.setdefault(CONF_UNIT_ID, DEFAULT_UNIT_ID)
        hass.config_entries.async_update_entry(entry, version=3, data=data)

    if entry.version == 3:
        # Version 4: the unique ID includes the unit ID (host:port:unit_id), so
        # several chargers behind one gateway address can be added.
        unique_id = build_unique_id(
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data.get(CONF_UNIT_ID, DEFAULT_UNIT_ID),
        )
        hass.config_entries.async_update_entry(entry, version=4, unique_id=unique_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        entry.runtime_data = None
        ir.async_delete_issue(hass, DOMAIN, f"{_ISSUE_ID_SCAN_INTERVAL}_{entry.entry_id}")

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removal of orphaned devices from the UI."""
    return True


class AbbTerraAcDataUpdateCoordinator(DataUpdateCoordinator[AbbTerraAcData]):
    """Coordinator for fetching data from the charger."""

    def __init__(
        self, hass: HomeAssistant, device: AbbTerraAcDevice, entry: ConfigEntry
    ) -> None:
        """Initialize the DataUpdateCoordinator."""
        self.device = device
        self.entry_id = entry.entry_id
        scan_s = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        self._scan_interval_s = scan_s
        self._is_available = True
        self.last_command: str = LastCommand.NONE
        self._state_5_polls = 0
        self._session_was_active = False
        self._failed_polls = 0
        self._last_logged_raw: tuple[int, ...] | None = None

        # Firmware bug auto-fix: fallback limit
        self._last_valid_fallback_limit: int | None = None
        self._fallback_fix_attempted = False

        # Firmware bug auto-fix: charging current limit
        self._last_valid_current_limit: int | None = None
        self._current_limit_fix_attempted = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_s),
        )

    @property
    def serial_number(self) -> str | None:
        """Serial number, cached by the device after the first poll."""
        return self.device.serial_number

    def _async_create_limit_issue(
        self,
        issue_id: str,
        limit_name: str,
        current_value: int,
        max_value: int,
    ) -> None:
        """Create a repair issue for an invalid charger limit that could not be restored."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"{issue_id}_{self.entry_id}",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="firmware_limit_restore_failed",
            translation_placeholders={
                "limit_name": limit_name,
                "current_value": str(current_value),
                "max_value": str(max_value),
            },
        )

    def _async_check_scan_interval(self, data: AbbTerraAcData) -> None:
        """Warn when polling is not faster than the charger's communication timeout.

        The charger counts Modbus communication as lost when nothing is read
        within its communication timeout (register 4106h, read back in 4020h).
        Our poll is that read, so a poll interval at or above the timeout can
        make the charger report ``modbus_communication_lost``.
        """
        timeout = int(data["communication_timeout"])
        issue_id = f"{_ISSUE_ID_SCAN_INTERVAL}_{self.entry_id}"
        if timeout > 0 and self._scan_interval_s >= timeout:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="scan_interval_exceeds_timeout",
                translation_placeholders={
                    "scan_interval": str(self._scan_interval_s),
                    "timeout": str(timeout),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)

    def _async_delete_limit_issue(self, issue_id: str) -> None:
        """Delete a previously created invalid charger limit issue."""
        ir.async_delete_issue(self.hass, DOMAIN, f"{issue_id}_{self.entry_id}")

    async def _async_update_data(self) -> AbbTerraAcData:
        """Fetch the latest data from the charger.

        The shared Modbus connection serializes requests and reopens itself
        after a dropped link, so no reconnect or retry logic is needed here.
        """
        try:
            data = await self.device.async_read_status()
        except (ModbusConnectionError, ModbusTimeoutError, TimeoutError) as err:
            self._failed_polls += 1
            if self.data is not None and self._failed_polls <= TOLERATED_FAILED_POLLS:
                # The charger sometimes resets while idle and misses exactly one
                # poll. Keep the last data for that one poll instead of marking
                # every entity unavailable for a whole scan interval.
                _LOGGER.debug(
                    "Poll failed (%s); keeping the previous data", err
                )
                return self.data
            self._async_log_unavailable(f"Connection error: {err}")
            raise UpdateFailed(f"Connection error: {err}") from err
        except ModbusError as err:
            self._async_log_unavailable(f"Error reading registers: {err}")
            raise UpdateFailed(f"Error reading registers: {err}") from err
        except Exception as err:
            self._async_log_unavailable(f"Unexpected error: {err}")
            _LOGGER.error("Unexpected error: %s", err, exc_info=True)
            raise UpdateFailed(err) from err

        self._failed_polls = 0
        await self._async_restore_invalid_limits(data)
        self._async_check_scan_interval(data)

        if not self._is_available:
            _LOGGER.info("ABB Terra AC charger is available again")
        self._is_available = True
        self._sync_last_command_after_poll(data)
        self._state_5_polls = (
            self._state_5_polls + 1 if data["charging_state"] == 5 else 0
        )
        self._update_session_was_active(data)
        self._async_log_raw_changes()
        return data

    def _update_session_was_active(self, data: AbbTerraAcData) -> None:
        """Remember whether charging or a pause was seen since the vehicle was idle."""
        raw = data["charging_state"]
        if raw in (3, 4, 5):
            self._session_was_active = True
        elif raw in (0, 2) or data["socket_lock_state"] == 0:
            self._session_was_active = False

    def _async_log_raw_changes(self) -> None:
        """Debug-log the registers behind the session state when they change.

        400Ch-400Dh (charging state, bit 7), 400Eh-400Fh (limit in use) and
        4022h-4023h (limit set via Modbus) are logged as hex together with the
        phase currents, so a log shows how they move relative to each other.
        """
        registers = self.device.last_registers
        if registers is None or not _LOGGER.isEnabledFor(logging.DEBUG):
            return
        key = (*registers[12:16], *registers[34:36])
        if key == self._last_logged_raw:
            return
        self._last_logged_raw = key
        _LOGGER.debug(
            "Status registers: 400C-400D=%04X %04X, 400E-400F=%04X %04X, "
            "4022-4023=%04X %04X, I(mA) L1=%d L2=%d L3=%d, P=%d W, "
            "last_command=%s",
            *key,
            (registers[16] << 16) | registers[17],
            (registers[18] << 16) | registers[19],
            (registers[20] << 16) | registers[21],
            (registers[28] << 16) | registers[29],
            self.last_command,
        )

    async def _async_restore_invalid_limits(self, data: AbbTerraAcData) -> None:
        """Work around the firmware resetting limits to invalid values after a reboot."""
        user_max = int(data["user_settable_max_current"])

        # --- Firmware bug fix: Fallback Limit ---
        # Known firmware bug: fallback limit resets to an invalid value (the documented
        # default is 0xFF) after unexpected reboot.
        # Restore to last known valid value, or user_settable_max_current as fallback.
        fallback_limit = data["fallback_limit"]

        if fallback_limit <= user_max or fallback_limit == 0:
            self._last_valid_fallback_limit = fallback_limit
            self._fallback_fix_attempted = False
            self._async_delete_limit_issue(_ISSUE_ID_INVALID_FALLBACK_LIMIT)
        elif fallback_limit > user_max:
            _LOGGER.warning(
                "Invalid fallback limit detected: %sA (max allowed: %sA). Attempting to restore.",
                fallback_limit, user_max
            )
            if not self._fallback_fix_attempted:
                self._fallback_fix_attempted = True
                restore_value = (
                    self._last_valid_fallback_limit
                    if self._last_valid_fallback_limit is not None
                    else user_max
                )
                try:
                    await self.device.async_set_fallback_limit(int(restore_value))
                    _LOGGER.info("Fallback limit restored to %sA.", restore_value)
                    data["fallback_limit"] = restore_value
                    self._async_delete_limit_issue(_ISSUE_ID_INVALID_FALLBACK_LIMIT)
                except Exception as err:
                    _LOGGER.error("Exception while writing fallback limit: %s", err)
                    self._async_create_limit_issue(
                        _ISSUE_ID_INVALID_FALLBACK_LIMIT,
                        "fallback limit",
                        fallback_limit,
                        user_max,
                    )

        # --- Firmware bug fix: Charging Current Limit ---
        # Known firmware bug: charging current limit resets to 32A after unexpected reboot.
        # Restore to last known valid value, or user_settable_max_current as fallback.
        current_limit = int(data["charging_current_limit_modbus"])

        if user_max > 0 and current_limit <= user_max:
            self._last_valid_current_limit = current_limit
            self._current_limit_fix_attempted = False
            self._async_delete_limit_issue(_ISSUE_ID_INVALID_CURRENT_LIMIT)
        elif user_max > 0 and current_limit > user_max:
            _LOGGER.warning(
                "Invalid charging current limit detected: %sA (max allowed: %sA). Attempting to restore.",
                current_limit, user_max
            )
            if not self._current_limit_fix_attempted:
                self._current_limit_fix_attempted = True
                restore_value = (
                    self._last_valid_current_limit
                    if self._last_valid_current_limit is not None
                    else user_max
                )
                try:
                    await self.device.async_set_current_limit(restore_value)
                    _LOGGER.info("Charging current limit restored to %sA.", restore_value)
                    data["charging_current_limit_modbus"] = restore_value
                    self._async_delete_limit_issue(_ISSUE_ID_INVALID_CURRENT_LIMIT)
                except Exception as err:
                    _LOGGER.error("Exception while writing charging current limit: %s", err)
                    self._async_create_limit_issue(
                        _ISSUE_ID_INVALID_CURRENT_LIMIT,
                        "charging current limit",
                        current_limit,
                        user_max,
                    )

    def _sync_last_command_after_poll(self, data: AbbTerraAcData) -> None:
        """Clear last_command when the cable is unplugged or the session ends."""
        if data["socket_lock_state"] == 0:
            self.last_command = LastCommand.NONE
            return
        raw = data["charging_state"]
        if raw >= 2 and self.last_command == LastCommand.START:
            self.last_command = LastCommand.NONE
        elif raw in (0, 1):
            if self.last_command == LastCommand.START:
                return
            if self.last_command == LastCommand.STOP:
                self.last_command = LastCommand.NONE
            else:
                self.last_command = LastCommand.NONE

    @property
    def session_state(self) -> SessionState:
        """Derived session state from the latest poll and last_command."""
        if not self.data:
            return SessionState.UNKNOWN  # type: ignore[unreachable]
        return derive_session_state(
            charging_state_raw=self.data["charging_state"],
            current_limit_modbus=float(self.data["charging_current_limit_modbus"]),
            last_command=self.last_command,
            charging_current_l1=float(self.data["charging_current_l1"]),
            charging_current_l2=float(self.data["charging_current_l2"]),
            charging_current_l3=float(self.data["charging_current_l3"]),
            state_5_polls=self._state_5_polls,
            session_was_active=self._session_was_active,
        )

    def _async_log_unavailable(self, reason: str) -> None:
        """Log when the charger becomes unavailable without spamming logs."""
        if self._is_available:
            _LOGGER.warning("ABB Terra AC charger became unavailable: %s", reason)
        self._is_available = False
