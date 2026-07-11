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
        self._attr_name = f"{device.name} {self.sensor_label} Energy"
        self._attr_unique_id = f"sensor.{device.name.lower()}_{device.id}_{self.sensor_label.lower()}_energy"
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
            self.hub.http = aiohttp.ClientSession()
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
        LOGGER.debug(f"Removing energy consumption entity ({self._attr_name}) from HA")
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
        LOGGER.debug(f"Fetching {self.sensor_label} energy consumption for device: {self._attr_name}, period: {date_string}")
        consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
        return consumption.get(date_string)

    async def _set_last_reset_time(self):
        """Set the last reset time for the yesterday energy sensor entity."""
        now = dt_util.now()
        start_of_today = dt_util.start_of_local_day(now)
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_today:
            self._attr_last_reset = now

class MirAIeTodayEnergySensor(MirAIeEnergySensor):
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
        LOGGER.debug(f"Fetching {self.sensor_label} energy consumption for device: {self._attr_name}, period: {date_string}")
        consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
        return consumption.get(date_string)

    async def _set_last_reset_time(self):
        """Set the last reset time for the today energy sensor entity."""
        now = dt_util.now()
        start_of_today = dt_util.start_of_local_day(now)
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_today:
            self._attr_last_reset = now

class MirAIeWeeklyEnergySensor(MirAIeEnergySensor):
    @property
    def period_type(self) -> ConsumptionPeriodType:
        return ConsumptionPeriodType.WEEKLY

    async def get_energy_consumption(self) -> float | None:
        """Fetch the latest weekly energy consumption data."""
        date_string = get_last_sunday().strftime("%d%m%Y")
        LOGGER.debug(f"Fetching {self.period_type.value} energy consumption for device: {self._attr_name}, period: {date_string}")
        consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
        return consumption.get(date_string)

    async def _set_last_reset_time(self):
        """Set the last reset time for the weekly energy sensor entity."""
        now = dt_util.now()
        start_of_week = dt_util.start_of_local_day(now - timedelta(days=now.weekday() + 1))
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_week:
            self._attr_last_reset = now

class MirAIeMonthlyEnergySensor(MirAIeEnergySensor):
    @property
    def period_type(self) -> ConsumptionPeriodType:
        return ConsumptionPeriodType.MONTHLY

    async def get_energy_consumption(self) -> float | None:
        """Fetch the latest monthly energy consumption data."""
        yesterday = dt_util.now().date() - timedelta(days=1)
        date_string = yesterday.strftime("%m%Y")
        LOGGER.debug(f"Fetching {self.period_type.value} energy consumption for device: {self._attr_name}, period: {date_string}")
        consumption = await self.hub.get_energy_consumption(self.device, self.period_type, from_date=date_string)
        return consumption.get(date_string)

    async def _set_last_reset_time(self):
        """Set the last reset time for the monthly energy sensor entity."""
        now = dt_util.now()
        start_of_month = dt_util.start_of_local_day(now.replace(day=1))
        if not getattr(self, "_attr_last_reset", None) or self._attr_last_reset < start_of_month:
            self._attr_last_reset = now


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up MirAIe energy and status sensors from a config entry."""
    hub: MirAIeHub = hass.data[DOMAIN][entry.entry_id]
    
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
        for sensor in energy_sensors:
            await sensor.async_update()
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
        self._attr_unique_id = f"sensor.{device.name.lower()}_{device.id}_room_temperature"
        self._attr_name = f"{device.name} Room Temperature"
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
        self._attr_unique_id = f"sensor.{device.name.lower()}_{device.id}_wifi_signal"
        self._attr_name = f"{device.name} WiFi Signal"
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
        self._attr_unique_id = f"sensor.{device.name.lower()}_{device.id}_control_source"
        self._attr_name = f"{device.name} Last Control Source"
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
