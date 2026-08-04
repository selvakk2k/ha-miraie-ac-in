import asyncio
from abc import ABC, abstractmethod
import calendar
from datetime import date, datetime, timezone, timedelta

import aiohttp
from miraie_ac import Device as MirAIeDevice, MirAIeHub, ConsumptionPeriodType

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    StatisticData,
    StatisticMetaData,
    async_import_statistics,
    get_last_statistics,
)

try:
    from homeassistant.components.recorder.statistics import StatisticMeanType
    MEAN_TYPE_NONE = StatisticMeanType.NONE
except ImportError:
    MEAN_TYPE_NONE = 0
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_INSTALL_DATE,
    get_converti_preset_modes,
    supports_heat_mode,
)
from .utils import six_months_ago
from .logger import LOGGER
from .utils import get_last_sunday



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
        self._attr_state_class = None
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_suggested_display_precision = 2
        self._attr_native_value = None

    async def async_update(self):
        """Update the sensor state with the latest energy consumption data."""
        now = dt_util.now()
        if not self.hub.http or self.hub.http.closed:
            LOGGER.error("MirAIe HTTP session is closed or unavailable")
            return
        consumption = await self.get_energy_consumption()

        if consumption is None:
            """Skip update if no new data."""
            return

        if self._attr_state_class == SensorStateClass.TOTAL:
            await self._set_last_reset_time()
        else:
            self._attr_last_reset = None
            
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


class MirAIeEnergyHistorySensor(MirAIeTodayEnergySensor):
    """Cumulative energy history sensor for long-term statistics & Energy Dashboard."""

    def __init__(self, hub: MirAIeHub, device: MirAIeDevice):
        super().__init__(hub, device)
        self._attr_translation_key = "energy_history"
        self._attr_unique_id = f"{device.id}_energy_history"
        # Omit state_class so HA recorder does not generate unwanted hourly statistics.
        # Long-term daily statistics are imported directly via async_import_statistics.
        self._attr_state_class = None

    @property
    def sensor_label(self) -> str:
        return "Energy History"

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"miraie_backfill_complete_{self.device.id}",
                self._handle_backfill_complete,
            )
        )

    async def _set_last_reset_time(self):
        """No last_reset for TOTAL_INCREASING sensors."""
        pass

    async def _handle_backfill_complete(self):
        """Update sensor state when backfill finishes."""
        LOGGER.debug("%s: Backfill completed, updating state", self.sensor_label)
        self.async_schedule_update_ha_state(True)

    async def get_energy_consumption(self) -> float | None:
        """Fetch total cumulative energy consumption up to yesterday."""
        if not hasattr(self.device, "backfilled_energy_sum"):
            LOGGER.debug("%s: Waiting for backfill to complete before reporting state", self.sensor_label)
            return None

        base_sum = max(0.0, float(getattr(self.device, "backfilled_energy_sum", 0.0)))
        return round(base_sum, 2)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up MirAIe energy and status sensors from a config entry."""
    hub: MirAIeHub = entry.runtime_data
    
    # 1. Setup Energy Sensors (which need active polling)
    energy_sensors = []
    entity_reg = er.async_get(hass)
    for device in hub.home.devices:
        statistic_id = entity_reg.async_get_entity_id("sensor", DOMAIN, f"{device.id}_energy_history")
        if not statistic_id:
            statistic_id = f"sensor.{device.id}_energy_history"
        try:
            last_stats = await get_instance(hass).async_add_executor_job(
                get_last_statistics, hass, 100, statistic_id, False, {"sum"}
            )
            if last_stats and last_stats.get(statistic_id):
                entries = last_stats[statistic_id]
                end_date = dt_util.now().date() - timedelta(days=1)
                for entry in reversed(entries):
                    raw_sum = float(entry.get("sum") or 0.0)
                    if not (0 <= raw_sum <= 400):
                        continue
                    entry_utc = datetime.fromtimestamp(entry["start"], tz=timezone.utc)
                    entry_local = dt_util.as_local(entry_utc)
                    for d in (entry_local.date(), entry_local.date() - timedelta(days=1)):
                        target_day = d + timedelta(days=1)
                        if entry_utc == _get_statistic_timestamp(target_day) and target_day <= end_date:
                            setattr(device, "backfilled_energy_sum", raw_sum)
                            break
                    if hasattr(device, "backfilled_energy_sum"):
                        break
        except Exception as e:
            LOGGER.debug("Could not pre-initialize backfilled_energy_sum for %s: %s", device.friendly_name, e)

        energy_sensors += [
            MirAIeYesterdayEnergySensor(hub, device),
            MirAIeTodayEnergySensor(hub, device),
            MirAIeWeeklyEnergySensor(hub, device),
            MirAIeMonthlyEnergySensor(hub, device),
            MirAIeEnergyHistorySensor(hub, device),
        ]
    async_add_entities(energy_sensors, update_before_add=True)

    poll_sensors = [s for s in energy_sensors if not isinstance(s, MirAIeEnergyHistorySensor)]

    async def update_sensors(now=None):
        # Gather updates concurrently to avoid sequential HTTP requests
        await asyncio.gather(
            *(sensor.async_update() for sensor in poll_sensors),
            return_exceptions=True
        )
        for sensor in poll_sensors:
            sensor.async_write_ha_state()  # Ensure HA is notified of new data

    cancel_interval = async_track_time_interval(hass, update_sensors, timedelta(minutes=30))
    if hasattr(entry, "async_on_unload"):
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


def _get_statistic_timestamp(target_date: date) -> datetime:
    """Return top-of-hour UTC timestamp corresponding to local midnight of target_date.

    Home Assistant statistics require UTC timestamps with minute=0 and second=0.
    For UTC+5:30 (India), local midnight 00:00 IST on date D is 18:30 UTC on D-1.
    Rounding to top of UTC hour yields 18:00 UTC on D-1, which aligns precisely
    with the local day bucket in Home Assistant Energy Dashboard.
    """
    local_dt = dt_util.start_of_local_day(datetime.combine(target_date, datetime.min.time()))
    utc_dt = dt_util.as_utc(local_dt)
    return utc_dt.replace(minute=0, second=0, microsecond=0)


async def async_backfill_energy_statistics(
    hass: HomeAssistant,
    hub: MirAIeHub,
    device: MirAIeDevice,
    default_start_date: date,
) -> None:
    """Backfill daily energy history into HA recorder statistics."""
    if not hub.http or hub.http.closed:
        hub.http = async_get_clientsession(hass)

    entity_reg = er.async_get(hass)
    statistic_id = entity_reg.async_get_entity_id("sensor", DOMAIN, f"{device.id}_energy_history")
    if not statistic_id:
        statistic_id = f"sensor.{device.id}_energy_history"

    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 100, statistic_id, False, {"sum"}
    )

    end_date = dt_util.now().date() - timedelta(days=1)
    start_date = default_start_date
    last_sum = 0.0
    has_imported_entry = False

    if last_stats and last_stats.get(statistic_id):
        entries = last_stats[statistic_id]
        if entries:
            latest_valid_timestamp = _get_statistic_timestamp(end_date + timedelta(days=1))
            corrupt = False
            for entry in entries:
                entry_utc = datetime.fromtimestamp(entry["start"], tz=timezone.utc)
                raw_sum = float(entry.get("sum") or 0.0)
                if (
                    raw_sum < 0
                    or raw_sum > 400
                    or entry_utc.minute != 0
                    or entry_utc.second != 0
                    or entry_utc > latest_valid_timestamp
                ):
                    LOGGER.warning(
                        "Legacy/corrupted/inflated/hourly energy statistics detected for %s (start=%s, sum=%s); "
                        "clearing via recorder API and rebuilding from scratch",
                        device.friendly_name,
                        entry_utc.isoformat(),
                        raw_sum,
                    )
                    corrupt = True
                    break

            if corrupt:
                try:
                    done = asyncio.Event()

                    def _on_clear_done() -> None:
                        hass.loop.call_soon_threadsafe(done.set)

                    get_instance(hass).async_clear_statistics([statistic_id], on_done=_on_clear_done)
                    async with asyncio.timeout(90):
                        await done.wait()
                except TimeoutError:
                    LOGGER.error(
                        "Timed out clearing legacy energy statistics for %s; aborting this "
                        "backfill run, will retry on next scheduled run",
                        device.friendly_name,
                    )
                    return
                except Exception:
                    LOGGER.exception(
                        "Failed to clear legacy energy statistics for %s; aborting this "
                        "backfill run, will retry on next scheduled run",
                        device.friendly_name,
                    )
                    return
                last_stats = None
                last_sum = 0.0
                start_date = default_start_date
            else:
                for entry in reversed(entries):
                    entry_utc = datetime.fromtimestamp(entry["start"], tz=timezone.utc)
                    entry_local = dt_util.as_local(entry_utc)
                    raw_sum = float(entry.get("sum") or 0.0)
                    for d in (entry_local.date(), entry_local.date() - timedelta(days=1)):
                        target_day = d + timedelta(days=1)
                        if entry_utc == _get_statistic_timestamp(target_day) and target_day <= end_date:
                            start_date = target_day
                            last_sum = raw_sum
                            has_imported_entry = True
                            break
                    if has_imported_entry:
                        break

    if start_date > end_date:
        LOGGER.info(
            "Backfill: no new daily data for %s (up to %s)",
            device.friendly_name,
            end_date.isoformat(),
        )
        setattr(device, "backfilled_energy_sum", last_sum)
        async_dispatcher_send(hass, f"miraie_backfill_complete_{device.id}")
        return

    daily = await hub.get_energy_consumption_full(
        device, ConsumptionPeriodType.DAILY, start_date, end_date
    )
    if not daily:
        LOGGER.info("Backfill: no data returned for %s", device.friendly_name)
        setattr(device, "backfilled_energy_sum", last_sum)
        async_dispatcher_send(hass, f"miraie_backfill_complete_{device.id}")
        return

    statistics = []
    running_sum = last_sum

    # If doing initial backfill (no existing statistics), insert baseline at start_date local midnight UTC hour
    if not has_imported_entry:
        start_baseline_dt = _get_statistic_timestamp(start_date)
        statistics.append(StatisticData(start=start_baseline_dt, sum=last_sum, state=last_sum))

    first_day = last_day = None
    for key in sorted(daily.keys(), key=lambda k: datetime.strptime(k, "%d%m%Y").date()):
        day = datetime.strptime(key, "%d%m%Y").date()
        if day < start_date or day > end_date:
            continue
        value = daily.get(key)
        val_float = max(0.0, float(value))
        running_sum += val_float
        # End of 'day' is local midnight of day + 1 day, converted to top-of-hour UTC
        end_dt = _get_statistic_timestamp(day + timedelta(days=1))
        statistics.append(StatisticData(start=end_dt, sum=running_sum, state=running_sum))
        if first_day is None:
            first_day = day
        last_day = day

    if not statistics or (len(statistics) == 1 and not has_imported_entry):
        LOGGER.info("Backfill: no new points built for %s", device.friendly_name)
        setattr(device, "backfilled_energy_sum", running_sum)
        async_dispatcher_send(hass, f"miraie_backfill_complete_{device.id}")
        return

    setattr(device, "backfilled_energy_sum", running_sum)

    metadata = StatisticMetaData(
        has_sum=True,
        has_mean=False,
        mean_type=MEAN_TYPE_NONE,
        unit_class="energy",
        name=f"{device.friendly_name} Energy History",
        source="recorder",
        statistic_id=statistic_id,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )
    async_import_statistics(hass, metadata, statistics)
    LOGGER.info(
        "Backfill: added %s daily points for %s (%s to %s)",
        len(statistics),
        device.friendly_name,
        first_day.isoformat() if first_day else start_date.isoformat(),
        last_day.isoformat() if last_day else end_date.isoformat(),
    )
    async_dispatcher_send(hass, f"miraie_backfill_complete_{device.id}")
