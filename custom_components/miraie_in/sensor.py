import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta

import aiohttp
from miraie_ac import Device as MirAIeDevice, MirAIeHub, ConsumptionPeriodType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import DOMAIN

PARALLEL_UPDATES = 0
from .logger import LOGGER
from .utils import get_last_sunday


CUTOFF_HOUR = 12

class MirAIeEnergySensor(SensorEntity, ABC):
    """Sensor for AC Power Consumption."""
    @property
    @abstractmethod
    def period_type(self) -> ConsumptionPeriodType:
        return None

    @property
    def sensor_label(self) -> str:
        """Human-facing label used for the entity name/unique_id.

        Defaults to period_type's value, but can be overridden -- needed
        for sensors that share the same underlying period_type (e.g.
        Yesterday and Today both use ConsumptionPeriodType.DAILY, just
        with different dates) but must still get distinct names/IDs.
        """
        return self.period_type.value

    def __init__(self, hub: MirAIeHub, device: MirAIeDevice):
        """Initialize the sensor."""
        self.hub = hub
        self.device = device
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{device.id}_{self.sensor_label.lower()}_energy"
        self._attr_should_poll = False
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_display_precision = 2
        self._attr_native_value = None

    async def async_update(self):
        """Update the sensor state with the latest energy consumption data."""
        now = dt_util.now()
        cutoff_time = dt_util.start_of_local_day(now).replace(hour=CUTOFF_HOUR)
        if not self.hub.http or self.hub.http.closed:
            LOGGER.error("MirAIe HTTP session is closed or unavailable")
            return
        consumption = await self.get_energy_consumption()

        """Consumption figures are updated on the server some time between 7-10 am the next day.
        This skips setting the state to unavailable if the value is None and it's not yet
        past the cutoff time.
        """
        if consumption is None and now <= cutoff_time:
            """Skip update if no new data and it's before the cutoff time."""
            return

        await self._set_last_reset_time()
        self._attr_native_value = consumption

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        LOGGER.debug(f"Removing energy consumption entity ({self.entity_id}) from HA")
        return await super().async_will_remove_from_hass()

    @abstractmethod
    async def get_energy_consumption(self) -> float | None:
        """Fetch the latest power consumption data."""
        raise NotImplementedError

    @abstractmethod
    async def _set_last_reset_time(self):
        """Set the last reset time for the sensor entity."""
        raise NotImplementedError

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.device.id)
            },
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

class MirAIeYesterdayEnergySensor(MirAIeEnergySensor):
    def __init__(self, hub: MirAIeHub, device: MirAIeDevice):
        super().__init__(hub, device)
        self._attr_translation_key = "yesterday_consumption"

    @property
    def period_type(self) -> ConsumptionPeriodType:
        return ConsumptionPeriodType.DAILY

    @property
    def sensor_label(self) -> str:
        return "Yesterday"

    async def get_energy_consumption(self) -> float | None:
        """Fetch yesterday's total energy consumption data."""
        yesterday = dt_util.now().date() - timedelta(days=1)
        date_string = yesterday.strftime("%d%m%Y")
        try:
            consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
            value = consumption.get(date_string)
            LOGGER.debug(
                "%s | %s | key=%s | raw=%s | value=%s",
                self.sensor_label, self.device.friendly_name, date_string, consumption, value,
            )
            return value
        except Exception:
            LOGGER.exception(
                "%s energy consumption fetch failed for %s [date_key=%s]",
                self.sensor_label, self.device.friendly_name, date_string,
            )
            raise

    async def _set_last_reset_time(self):
        """Set the last reset time for the yesterday energy sensor entity."""
        now = dt_util.now()
        start_of_today = dt_util.start_of_local_day(now)
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_today:
            self._attr_last_reset = now

class MirAIeTodayEnergySensor(MirAIeEnergySensor):
    def __init__(self, hub: MirAIeHub, device: MirAIeDevice):
        super().__init__(hub, device)
        self._attr_translation_key = "current_consumption"

    @property
    def period_type(self) -> ConsumptionPeriodType:
        return ConsumptionPeriodType.DAILY

    @property
    def sensor_label(self) -> str:
        return "Today"

    async def get_energy_consumption(self) -> float | None:
        """Fetch today's (live, rolling) energy consumption data so far."""
        today = dt_util.now().date()
        date_string = today.strftime("%d%m%Y")
        try:
            consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
            value = consumption.get(date_string)
            LOGGER.debug(
                "%s | %s | key=%s | raw=%s | value=%s",
                self.sensor_label, self.device.friendly_name, date_string, consumption, value,
            )
            return value
        except Exception:
            LOGGER.exception(
                "%s energy consumption fetch failed for %s [date_key=%s]",
                self.sensor_label, self.device.friendly_name, date_string,
            )
            raise

    async def _set_last_reset_time(self):
        """Set the last reset time for the today energy sensor entity."""
        now = dt_util.now()
        start_of_today = dt_util.start_of_local_day(now)
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_today:
            self._attr_last_reset = now

class MirAIeWeeklyEnergySensor(MirAIeEnergySensor):
    def __init__(self, hub: MirAIeHub, device: MirAIeDevice):
        super().__init__(hub, device)
        self._attr_translation_key = "weekly_consumption"

    @property
    def period_type(self) -> ConsumptionPeriodType:
        return ConsumptionPeriodType.WEEKLY

    async def get_energy_consumption(self) -> float | None:
        """Fetch the latest weekly energy consumption data."""
        date_string = get_last_sunday().strftime("%d%m%Y")
        try:
            consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
            value = consumption.get(date_string)
            LOGGER.debug(
                "%s | %s | key=%s | raw=%s | value=%s",
                self.period_type.value, self.device.friendly_name, date_string, consumption, value,
            )
            return value
        except Exception:
            LOGGER.exception(
                "%s energy consumption fetch failed for %s [date_key=%s]",
                self.period_type.value, self.device.friendly_name, date_string,
            )
            raise

    async def _set_last_reset_time(self):
        """Set the last reset time for the weekly energy sensor entity."""
        now = dt_util.now()
        start_of_week = dt_util.start_of_local_day(now - timedelta(days=now.weekday() + 1))
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_week:
            self._attr_last_reset = now

class MirAIeMonthlyEnergySensor(MirAIeEnergySensor):
    def __init__(self, hub: MirAIeHub, device: MirAIeDevice):
        super().__init__(hub, device)
        self._attr_translation_key = "monthly_consumption"

    @property
    def period_type(self) -> ConsumptionPeriodType:
        return ConsumptionPeriodType.MONTHLY

    async def get_energy_consumption(self) -> float | None:
        """Fetch the latest monthly energy consumption data."""
        yesterday = dt_util.now().date() - timedelta(days=1)
        date_string = yesterday.strftime("%m%Y")
        try:
            consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
            value = consumption.get(date_string)
            LOGGER.debug(
                "%s | %s | key=%s | raw=%s | value=%s",
                self.period_type.value, self.device.friendly_name, date_string, consumption, value,
            )
            return value
        except Exception:
            LOGGER.exception(
                "%s energy consumption fetch failed for %s [date_key=%s]",
                self.period_type.value, self.device.friendly_name, date_string,
            )
            raise

    async def _set_last_reset_time(self):
        """Set the last reset time for the monthly energy sensor entity."""
        now = dt_util.now()
        start_of_month = dt_util.start_of_local_day(now.replace(day=1))
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_month:
            self._attr_last_reset = now


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up MirAIe energy and status sensors from a config entry."""
    hub: MirAIeHub = entry.runtime_data
    
    # 1. Setup Energy Sensors (which need active polling)
    energy_sensors = []
    for device in hub.home.devices:
        energy_sensors += [
            MirAIeYesterdayEnergySensor(hub, device),
            MirAIeTodayEnergySensor(hub, device),
            MirAIeWeeklyEnergySensor(hub, device),
            MirAIeMonthlyEnergySensor(hub, device),
        ]
    async_add_entities(energy_sensors, update_before_add=True)

    async def update_sensors(now=None):
        # Gather updates concurrently to avoid sequential HTTP requests
        await asyncio.gather(
            *(sensor.async_update() for sensor in energy_sensors),
            return_exceptions=True
        )
        for sensor in energy_sensors:
            sensor.async_write_ha_state()  # Ensure HA is notified of new data

    cancel_interval = async_track_time_interval(hass, update_sensors, timedelta(minutes=30))
    entry.async_on_unload(cancel_interval)

    # 2. Setup Non-Polling Sensors (updated via device callback pushed via MQTT)
    pushed_sensors = []
    for device in hub.home.devices:
        pushed_sensors += [
            MirAIeRoomTemperatureSensor(device),
            MirAIeWifiSignalSensor(device),
            MirAIeControlSourceSensor(device),
        ]
    async_add_entities(pushed_sensors)


class MirAIeRoomTemperatureSensor(SensorEntity):
    """Exposes current room temperature as a standalone sensor."""

    def __init__(self, device: MirAIeDevice):
        self._attr_should_poll = False
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{device.id}_room_temperature"
        self._attr_translation_key = "ac_temperature"
        self.device = device
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        return self.device.status.room_temperature

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

    async def async_added_to_hass(self):
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self.device.remove_callback(self.async_write_ha_state)


class MirAIeWifiSignalSensor(SensorEntity):
    """Exposes WiFi RSSI signal strength (disabled by default)."""

    def __init__(self, device: MirAIeDevice):
        self._attr_should_poll = False
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{device.id}_wifi_signal"
        self._attr_translation_key = "wifi_signal"
        self.device = device
        self._attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> int:
        return getattr(self.device.status, "wifi_signal", 0)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

    async def async_added_to_hass(self):
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self.device.remove_callback(self.async_write_ha_state)


class MirAIeControlSourceSensor(SensorEntity):
    """Exposes whether the AC was last controlled via app or remote (disabled by default)."""

    def __init__(self, device: MirAIeDevice):
        self._attr_should_poll = False
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{device.id}_control_source"
        self._attr_translation_key = "last_controlled_via"
        self.device = device
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str:
        source = getattr(self.device.status, "control_source", "an")
        mapping = {
            "an": "App",
            "ai": "AI Mode",
            "rem": "Remote",
            "auto": "Auto",
        }
        return mapping.get(source, source)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            name=self.device.friendly_name,
            manufacturer=self.device.details.brand,
            model=self.device.details.model_number,
            sw_version=self.device.details.firmware_version,
        )

    async def async_added_to_hass(self):
        self.device.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self.device.remove_callback(self.async_write_ha_state)
