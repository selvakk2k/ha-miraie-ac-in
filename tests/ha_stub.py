"""Dynamic Home Assistant module stub loader for standalone unit testing."""

import sys
import types
from enum import Enum, IntFlag


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
    try:
        import voluptuous
    except ImportError:
        vol = types.ModuleType("voluptuous")
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
        @classmethod
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()
    class OptionsFlow:
        pass
    class ConfigFlowResult:
        pass
    homeassistant.config_entries.ConfigEntry = ConfigEntry
    homeassistant.config_entries.ConfigFlow = ConfigFlow
    homeassistant.config_entries.OptionsFlow = OptionsFlow
    homeassistant.config_entries.ConfigFlowResult = ConfigFlowResult
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
    class StatisticMeanType(Enum):
        NONE = 0
    homeassistant.components.recorder.statistics.StatisticMeanType = StatisticMeanType

    # Ensure climate module dict strictly lacks precision constants
    for const_name in ("PRECISION_HALVES", "PRECISION_WHOLE", "PRECISION_TENTHS"):
        if const_name in homeassistant.components.climate.__dict__:
            del homeassistant.components.climate.__dict__[const_name]
