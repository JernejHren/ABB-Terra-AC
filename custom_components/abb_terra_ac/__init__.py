"""Integracija za ABB Terra AC polnilnico."""
import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException

from .const import DOMAIN, PLATFORMS, CONF_HOST, CONF_PORT, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Nastavi ABB Terra AC iz konfiguracijskega vnosa."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
   
    client = AsyncModbusTcpClient(host=host, port=port)
    coordinator = AbbTerraAcDataUpdateCoordinator(hass, client)
   
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Odstrani konfiguracijski vnos."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Zapri Modbus povezavo pred odstranjevanjem
        client = hass.data[DOMAIN][entry.entry_id]["client"]
        if client.connected:
            try:
                client.close()
                _LOGGER.debug("Modbus povezava uspešno zaprta")
            except Exception as err:
                _LOGGER.warning(f"Napaka pri zapiranju Modbus povezave: {err}")
        
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


class AbbTerraAcDataUpdateCoordinator(DataUpdateCoordinator):
    """Upravitelj za pridobivanje podatkov s polnilnice."""
    
    def __init__(self, hass: HomeAssistant, client: AsyncModbusTcpClient) -> None:
        """Inicializira DataUpdateCoordinator."""
        self.client = client
        self.serial_number: str | None = None
        # Flag za preprečevanje ponavljajočih se poskusov popravka fallback limita
        self._fallback_fix_attempted = False
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Pridobi najnovejše podatke s polnilnice."""
        try:
            if not self.client.connected:
                await self.client.connect()
            
            result = await self.client.read_holding_registers(address=16384, count=37)
            
            if result.isError():
                raise UpdateFailed(f"Napaka pri branju registrov: {result}")
            
            data: dict[str, Any] = {}
            registers = result.registers
           
            # Serial number - preberi samo enkrat
            if self.serial_number is None:
                self.serial_number = self._decode_serial_number(registers[0:4])
            data["serial_number"] = self.serial_number
            
            # Ostali podatki
            data["firmware_version"] = self._decode_firmware_version(registers[4:6])
            data["user_settable_max_current"] = self._decode_32bit_value(registers[6:8], 0.001)
            data["error_code"] = registers[8]
            data["socket_lock_state"] = self._decode_32bit_value(registers[10:12])
           
            # Pravilno dekodiranje stanja: preberemo register 16397,
            # izoliramo zgornji bajt in iz njega vzamemo kodo stanja.
            charging_state_register = registers[13]
            high_byte = (charging_state_register >> 8) & 0xFF
            state_code = high_byte & 0x0F
            data["charging_state"] = state_code
            
            data["charging_current_limit"] = self._decode_32bit_value(registers[14:16], 0.001)
            data["charging_current_l1"] = self._decode_32bit_value(registers[16:18], 0.001)
            data["charging_current_l2"] = self._decode_32bit_value(registers[18:20], 0.001)
            data["charging_current_l3"] = self._decode_32bit_value(registers[20:22], 0.001)
            data["voltage_l1"] = self._decode_32bit_value(registers[22:24], 0.1)
            data["voltage_l2"] = self._decode_32bit_value(registers[24:26], 0.1)
            data["voltage_l3"] = self._decode_32bit_value(registers[26:28], 0.1)
            data["active_power"] = self._decode_32bit_value(registers[28:30])
            data["energy_delivered"] = self._decode_32bit_value(registers[30:32])
            data["communication_timeout"] = registers[32]
            data["charging_current_limit_modbus"] = self._decode_32bit_value(registers[34:36], 0.001)
            data["fallback_limit"] = registers[36]
            
            # --- ZAČETEK SPREMEMBE: Preverjanje in popravek Fallback Limita ---
            fallback_limit = data["fallback_limit"]
            
            # Preverimo, ali je vrednost neveljavna (večja od 32A)
            if fallback_limit > 32:
                _LOGGER.warning(
                    f"Zaznana neveljavna vrednost za 'fallback limit': {fallback_limit}A "
                    "(verjetno napaka v firmware). Poskus ponastavitve na 6A."
                )
                
                # Poskusi popraviti samo enkrat na refresh cikel, da se izognemo zanki
                if not self._fallback_fix_attempted:
                    self._fallback_fix_attempted = True
                    
                    try:
                        # PRAVILNI register: 16649 (kot v number entity)
                        write_result = await self.client.write_register(address=16649, value=6)
                       
                        if write_result.isError():
                            _LOGGER.error(f"Napaka pri pisanju nove 'fallback' vrednosti: {write_result}")
                        else:
                            _LOGGER.info("Uspešno ponastavljena 'fallback' vrednost na 6A.")
                            # Takoj posodobimo podatke v koordinatorju za ta cikel
                            data["fallback_limit"] = 6
                           
                    except Exception as e:
                        _LOGGER.error(f"Izjema med pisanjem 'fallback' vrednosti: {e}")
            else:
                # Če je vrednost normalna, resetiraj flag za prihodnje cikle
                self._fallback_fix_attempted = False
            # --- KONEC SPREMEMBE ---
            
            return data
            
        except (ConnectionException, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Napaka pri povezavi s polnilnico: {err}")
        except Exception as err:
            _LOGGER.error("Nepričakovana napaka: %s", err, exc_info=True)
            raise UpdateFailed(err)

    def _decode_32bit_value(self, regs: list[int], resolution: float = 1) -> float:
        """Dekodira 32-bitno vrednost iz dveh registrov."""
        value = (regs[0] << 16) | regs[1]
        return value * resolution

    def _decode_serial_number(self, regs: list[int]) -> str:
        """Dekodira serijsko številko iz registrov."""
        try:
            connector_type = {0x47: "G", 0x50: "P", 0x53: "S", 0x54: "T"}
            byte7 = (regs[0] >> 8) & 0xFF
            byte5 = (regs[1] >> 8) & 0xFF
            byte3 = (regs[2] >> 8) & 0xFF
            byte2 = regs[2] & 0xFF
            byte1 = (regs[3] >> 8) & 0xFF
            byte0 = regs[3] & 0xFF
            
            connector = connector_type.get(byte7, f"Neznano (0x{byte7:02X})")
            plant_id = byte5
            prod_week = ((byte3 >> 4) & 0xF) * 10 + (byte3 & 0xF)
            prod_year = ((byte2 >> 4) & 0xF) * 10 + (byte2 & 0xF)
            serial_num = (
                ((byte1 >> 4) & 0xF) * 1000 + 
                (byte1 & 0xF) * 100 + 
                ((byte0 >> 4) & 0xF) * 10 + 
                (byte0 & 0xF)
            )
            
            return f"TACW22{plant_id}{prod_week:02d}{prod_year:02d}{connector}{serial_num:04d}"
        except Exception as e:
            _LOGGER.warning(f"Ne morem dekodirati serijske številke: {e}")
            return f"Ne morem dekodirati: {regs}"

    def _decode_firmware_version(self, regs: list[int]) -> str:
        """Dekodira firmware verzijo iz registrov."""
        try:
            major = (regs[0] >> 8) & 0xFF
            minor = regs[0] & 0xFF
            patch = (regs[1] >> 8) & 0xFF
            patch_bcd = ((patch >> 4) & 0xF) * 10 + (patch & 0xF)
            return f"v{major}.{minor}.{patch_bcd}"
        except Exception as e:
            _LOGGER.warning(f"Ne morem dekodirati firmware verzije: {e}")
            return f"Ne morem dekodirati: {regs}"
