"""Dynamic Home Assistant module stub loader for standalone unit testing."""

import sys
import types
from enum import Enum, IntFlag
from pathlib import Path

LOCAL_MIRAIE_AC = Path("/home/skk/Documents/GitHub/miraie-ac")
LOCAL_PANASONIC_MODELS = Path("/home/skk/Documents/GitHub/panasonic-ac-models")

if LOCAL_MIRAIE_AC.exists():
    if str(LOCAL_MIRAIE_AC) in sys.path:
        sys.path.remove(str(LOCAL_MIRAIE_AC))
    sys.path.insert(0, str(LOCAL_MIRAIE_AC))

if LOCAL_PANASONIC_MODELS.exists():
    if str(LOCAL_PANASONIC_MODELS) in sys.path:
        sys.path.remove(str(LOCAL_PANASONIC_MODELS))
    sys.path.insert(0, str(LOCAL_PANASONIC_MODELS))



class _HADynamicModule(types.ModuleType):
    """Module that returns dummy objects for unknown attributes while allowing custom getattr overrides."""

    def __getattr__(self, name):
        if self.__name__ == "homeassistant.components.climate" and name in (
            "PRECISION_HALVES",
            "PRECISION_WHOLE",
            "PRECISION_TENTHS",
        ):
            raise AttributeError(f"module 'homeassistant.components.climate' has no attribute '{name}'")

        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        dummy = type(name, (), {})
        setattr(self, name, dummy)
        return dummy


def setup_ha_stubs():
    if LOCAL_MIRAIE_AC.exists():
        if str(LOCAL_MIRAIE_AC) in sys.path:
            sys.path.remove(str(LOCAL_MIRAIE_AC))
        sys.path.insert(0, str(LOCAL_MIRAIE_AC))

    try:
        import panasonic_ac_models
    except ImportError:
        pan_mod = types.ModuleType("panasonic_ac_models")
        class ACModelLookup:
            @classmethod
            def is_cooling_only(cls, model):
                m = str(model)
                return False if ("EZ" in m or "KZ" in m) else True
            @classmethod
            def get_capabilities(cls, model):
                m = str(model)
                has_heat = 1 if ("EZ" in m or "KZ" in m) else 0
                has_nanoe = 1 if ("XU" in m or "HU" in m) else 0
                has_wifi = 0 if ("-1" in m or "-2" in m or "KN" in m or "CW" in m) else 1
                converti_type = "8-in-1" if ("BKY" in m or "CKY" in m) else ("7-in-1" if "AKY" in m or "NU" in m else "none")
                return {
                    "has_wifi": has_wifi,
                    "has_heat_mode": has_heat,
                    "has_nanoe": has_nanoe,
                    "converti_type": converti_type,
                }
        pan_mod.ACModelLookup = ACModelLookup
        sys.modules["panasonic_ac_models"] = pan_mod

    try:
        import voluptuous
    except ImportError:
        vol = types.ModuleType("voluptuous")
        class MockHass:
            def __init__(self):
                self.data = {}
                self.config_entries = MagicMock()
                self.services = MagicMock()
                self.services.async_call = AsyncMock()
                self.states = MagicMock()
                
                async def _dummy_task(coro):
                    pass
                self.async_create_task = MagicMock(side_effect=_dummy_task)
                
                async def _dummy_exec(func, *args, **kwargs):
                    return func(*args, **kwargs)
                self.async_add_executor_job = AsyncMock(side_effect=_dummy_exec)
        class Schema:
            def __init__(self, schema):
                self.schema = schema
        def Required(key, default=None):
            return key
        def Optional(key, default=None):
            return key
        vol.Schema = Schema
        vol.Required = Required
        vol.Optional = Optional
        sys.modules["voluptuous"] = vol

    if "homeassistant" in sys.modules:
        return

    # Install sys.meta_path finder for homeassistant.*
    class HAModuleFinder:
        def find_spec(self, fullname, path, target=None):
            if fullname in (
                "homeassistant.components.climate.PRECISION_HALVES",
                "homeassistant.components.climate.PRECISION_WHOLE",
                "homeassistant.components.climate.PRECISION_TENTHS",
            ):
                return None
            if fullname.startswith("homeassistant"):
                from importlib.machinery import ModuleSpec
                return ModuleSpec(fullname, HAModuleLoader(), is_package=True)
            return None

    class HAModuleLoader:
        def create_module(self, spec):
            mod = _HADynamicModule(spec.name)
            mod.__path__ = []
            return mod

        def exec_module(self, module):
            pass

    sys.meta_path.insert(0, HAModuleFinder())

    # Pre-populate specific strict symbol locations
    import homeassistant.const
    import homeassistant.components.climate
    import homeassistant.config_entries
    class ConfigEntry:
        pass
    class ConfigFlow:
        def async_show_menu(self, step_id, menu_options, description_placeholders=None):
            return {"type": "menu", "step_id": step_id, "menu_options": menu_options}
        def add_suggested_values_to_schema(self, data_schema, suggested_values):
            return data_schema
        def async_show_form(self, step_id, data_schema=None, errors=None, description_placeholders=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors, "description_placeholders": description_placeholders}
        def async_create_entry(self, title="", data=None, options=None):
            return {"type": "create_entry", "title": title, "data": data, "options": options}
        def async_abort(self, reason=""):
            return {"type": "abort", "reason": reason}
        async def async_set_unique_id(self, unique_id=None, raise_on_progress=True):
            self.unique_id = unique_id
        def _abort_if_unique_id_configured(self):
            pass
        @classmethod
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

    class OptionsFlow:
        def __init__(self, config_entry=None):
            self.config_entry = config_entry
        def add_suggested_values_to_schema(self, data_schema, suggested_values):
            return data_schema
        def async_show_menu(self, step_id, menu_options, description_placeholders=None):
            return {"type": "menu", "step_id": step_id, "menu_options": menu_options}
        def async_show_form(self, step_id, data_schema=None, errors=None, description_placeholders=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors, "description_placeholders": description_placeholders}
        def async_create_entry(self, title="", data=None):
            return {"type": "create_entry", "title": title, "data": data}

    class ConfigFlowResult:
        pass
    homeassistant.config_entries.ConfigEntry = ConfigEntry
    homeassistant.config_entries.ConfigFlow = ConfigFlow
    homeassistant.config_entries.OptionsFlow = OptionsFlow
    homeassistant.config_entries.ConfigFlowResult = ConfigFlowResult
    import homeassistant.core
    homeassistant.core.callback = lambda func: func

    import homeassistant.exceptions

    class HomeAssistantError(Exception):
        pass
    homeassistant.exceptions.HomeAssistantError = HomeAssistantError

    import homeassistant.components.sensor

    # homeassistant.const symbols
    class UnitOfTemperature(Enum):
        CELSIUS = "°C"
        FAHRENHEIT = "°F"

    class Platform(Enum):
        CLIMATE = "climate"
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        BUTTON = "button"
        SWITCH = "switch"

    class UnitOfPower(Enum):
        KILO_WATT = "kW"
        WATT = "W"

    class UnitOfEnergy(Enum):
        KILO_WATT_HOUR = "kWh"

    class UnitOfElectricPotential(Enum):
        VOLT = "V"

    class UnitOfElectricCurrent(Enum):
        AMPERE = "A"

    homeassistant.const.UnitOfTemperature = UnitOfTemperature
    homeassistant.const.Platform = Platform
    homeassistant.const.UnitOfPower = UnitOfPower
    homeassistant.const.UnitOfEnergy = UnitOfEnergy
    homeassistant.const.UnitOfElectricPotential = UnitOfElectricPotential
    homeassistant.const.UnitOfElectricCurrent = UnitOfElectricCurrent
    homeassistant.const.PRECISION_WHOLE = 1.0
    homeassistant.const.PRECISION_HALVES = 0.5
    homeassistant.const.PRECISION_TENTHS = 0.1
    homeassistant.const.SIGNAL_STRENGTH_DECIBELS_MILLIWATT = "dBm"
    homeassistant.const.PERCENTAGE = "%"

    # homeassistant.components.climate symbols
    class ClimateEntityFeature(IntFlag):
        TARGET_TEMPERATURE = 1
        FAN_MODE = 2
        PRESET_MODE = 4
        SWING_MODE = 8
        TURN_OFF = 16
        TURN_ON = 32
        SWING_HORIZONTAL_MODE = 64

    class HVACMode(Enum):
        AUTO = "auto"
        COOL = "cool"
        HEAT = "heat"
        OFF = "off"
        DRY = "dry"
        FAN_ONLY = "fan_only"

    homeassistant.components.climate.ClimateEntityFeature = ClimateEntityFeature
    homeassistant.components.climate.HVACMode = HVACMode
    homeassistant.components.climate.PRESET_ECO = "eco"
    homeassistant.components.climate.PRESET_BOOST = "boost"
    homeassistant.components.climate.PRESET_NONE = "none"
    homeassistant.components.climate.FAN_AUTO = "auto"
    homeassistant.components.climate.FAN_LOW = "low"
    homeassistant.components.climate.FAN_MEDIUM = "medium"
    homeassistant.components.climate.FAN_HIGH = "high"
    homeassistant.components.climate.FAN_OFF = "off"

    # Sensor symbols
    class SensorStateClass(Enum):
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"
        TOTAL = "total"

    class SensorDeviceClass(Enum):
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        ENERGY = "energy"
        POWER = "power"
        VOLTAGE = "voltage"
        CURRENT = "current"

    homeassistant.components.sensor.SensorStateClass = SensorStateClass
    homeassistant.components.sensor.SensorDeviceClass = SensorDeviceClass

    # Recorder symbols
    import homeassistant.components.recorder.statistics
    import homeassistant.components.recorder.models
    class StatisticMeanType(Enum):
        NONE = 0
    class StatisticData(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.__dict__.update(kwargs)
    class StatisticMetaData(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.__dict__.update(kwargs)
    homeassistant.components.recorder.statistics.StatisticMeanType = StatisticMeanType
    homeassistant.components.recorder.models.StatisticData = StatisticData
    homeassistant.components.recorder.models.StatisticMetaData = StatisticMetaData
    homeassistant.components.recorder.statistics.StatisticData = StatisticData
    homeassistant.components.recorder.statistics.StatisticMetaData = StatisticMetaData
    homeassistant.components.recorder.statistics.async_import_statistics = lambda hass, metadata, statistics: None
    homeassistant.components.recorder.statistics.clear_statistics = lambda instance, statistic_ids: None

    class MockRecorderInstance:
        def async_clear_statistics(self, statistic_ids):
            pass
        async def async_block_till_done(self):
            pass
        async def async_add_executor_job(self, target, *args):
            return target(*args) if callable(target) else None

    # Selector helper stubs
    import homeassistant.helpers.selector as selector_mod
    class SelectorBase(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(**kwargs)
        def __call__(self, v):
            return v
    class SelectOptionDict(dict):
        def __init__(self, value="", label=""):
            super().__init__(value=value, label=label)
            self.value = value
            self.label = label
    class SelectSelector(SelectorBase):
        pass
    class SelectSelectorConfig(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.__dict__.update(kwargs)
    class SelectSelectorMode(Enum):
        DROPDOWN = "dropdown"
        LIST = "list"
    class BooleanSelector(SelectorBase):
        pass
    class EntitySelector(SelectorBase):
        pass
    class EntitySelectorConfig(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.__dict__.update(kwargs)
    class DateSelector(SelectorBase):
        pass

    selector_mod.SelectOptionDict = SelectOptionDict
    selector_mod.SelectSelector = SelectSelector
    selector_mod.SelectSelectorConfig = SelectSelectorConfig
    selector_mod.SelectSelectorMode = SelectSelectorMode
    selector_mod.BooleanSelector = BooleanSelector
    selector_mod.EntitySelector = EntitySelector
    selector_mod.EntitySelectorConfig = EntitySelectorConfig
    selector_mod.DateSelector = DateSelector


    # Event helper stubs
    import homeassistant.helpers.event
    homeassistant.helpers.event.async_track_time_change = lambda hass, action, hour=None, minute=None, second=None: (lambda: None)

    # Entity helper stubs
    import homeassistant.helpers.entity
    class EntityCategory(Enum):
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"
    homeassistant.helpers.entity.EntityCategory = EntityCategory

    # Dispatcher helper stubs
    import homeassistant.helpers.dispatcher
    homeassistant.helpers.dispatcher.async_dispatcher_send = lambda *args, **kwargs: None
    homeassistant.helpers.dispatcher.async_dispatcher_connect = lambda *args, **kwargs: (lambda: None)

    # dt_util helper stub
    import homeassistant.util.dt as dt_util
    from datetime import datetime, timezone
    dt_util.now = lambda: datetime.now(timezone.utc)
    dt_util.start_of_local_day = lambda dt: dt.replace(hour=0, minute=0, second=0, microsecond=0)
    dt_util.as_utc = lambda dt: dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    dt_util.as_local = lambda dt: dt

    # aiohttp_client helper symbol
    import homeassistant.helpers.aiohttp_client
    homeassistant.helpers.aiohttp_client.async_get_clientsession = lambda hass=None: None

    # issue_registry helper symbol
    import homeassistant.helpers.issue_registry
    class IssueSeverity(Enum):
        WARNING = "warning"
        CRITICAL = "critical"
    homeassistant.helpers.issue_registry.IssueSeverity = IssueSeverity
    homeassistant.helpers.issue_registry.async_create_issue = lambda *args, **kwargs: None

    # Infrared helper stubs
    ir_mod = types.ModuleType("homeassistant.components.infrared")
    ir_helpers_mod = types.ModuleType("homeassistant.components.infrared.helpers")

    async def _async_send_command_stub(hass, entity_id, command):
        return True
    ir_helpers_mod.async_send_command = _async_send_command_stub
    ir_mod.helpers = ir_helpers_mod
    sys.modules["homeassistant.components.infrared"] = ir_mod
    sys.modules["homeassistant.components.infrared.helpers"] = ir_helpers_mod

    # restore_state helper stub
    import homeassistant.helpers.restore_state
    class RestoreEntity:
        async def async_added_to_hass(self):
            pass
        async def async_get_last_state(self):
            return None
    homeassistant.helpers.restore_state.RestoreEntity = RestoreEntity



    # Ensure climate module dict strictly lacks precision constants
    for const_name in ("PRECISION_HALVES", "PRECISION_WHOLE", "PRECISION_TENTHS"):
        if const_name in homeassistant.components.climate.__dict__:
            del homeassistant.components.climate.__dict__[const_name]
