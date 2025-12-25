from typing import Tuple, List
from core.setting.settings_base import SettingsBase


class ChoiceSetting(SettingsBase):
    """Setting that allows selection from a list of valid choices."""

    def __init__(self, default, choices: List):
        if default not in choices:
            raise ValueError(f"Default value {default} not in choices {choices}")
        self.param_value = default
        self.param_choices = choices

    def get_value(self):
        return self.param_value

    def set_value(self, value):
        if value not in self.param_choices:
            raise ValueError(f"Value {value} not in valid choices {self.param_choices}")
        self.param_value = value


class IntRangeSetting(SettingsBase):
    """Setting for integer values within a specified range."""

    def __init__(self, default: int, min_value: int, max_value: int):
        if not isinstance(default, int):
            raise TypeError(f"Default must be int, got {type(default)}")
        if not min_value <= default <= max_value:
            raise ValueError(f"Default {default} not in range [{min_value}, {max_value}]")
        self.param_value = default
        self.param_min_value = min_value
        self.param_max_value = max_value

    def get_value(self):
        return self.param_value

    def set_value(self, value):
        if not isinstance(value, int):
            raise TypeError(f"Value must be int, got {type(value)}")
        if not self.param_min_value <= value <= self.param_max_value:
            raise ValueError(f"Value {value} not in range [{self.param_min_value}, {self.param_max_value}]")
        self.param_value = value


class FloatRangeSetting(SettingsBase):
    """Setting for float values within a specified range."""

    def __init__(self, default: float, min_value: float, max_value: float):
        if not isinstance(default, (int, float)):
            raise TypeError(f"Default must be float, got {type(default)}")
        default = float(default)
        if not min_value <= default <= max_value:
            raise ValueError(f"Default {default} not in range [{min_value}, {max_value}]")
        self.param_value = default
        self.param_min_value = min_value
        self.param_max_value = max_value

    def get_value(self):
        return self.param_value

    def set_value(self, value):
        if not isinstance(value, (int, float)):
            raise TypeError(f"Value must be float, got {type(value)}")
        value = float(value)
        if not self.param_min_value <= value <= self.param_max_value:
            raise ValueError(f"Value {value} not in range [{self.param_min_value}, {self.param_max_value}]")
        self.param_value = value


class ResolutionSetting(SettingsBase):
    """Setting for video resolution (width, height) with independent range validation."""

    def __init__(self, default: Tuple[int, int], min_width: int, max_width: int,
                 min_height: int, max_height: int):
        if not isinstance(default, tuple) or len(default) != 2:
            raise TypeError("Default must be a tuple of 2 elements")
        width, height = default
        if not isinstance(width, int) or not isinstance(height, int):
            raise TypeError("Width and height must be integers")
        if not min_width <= width <= max_width:
            raise ValueError(f"Width {width} not in range [{min_width}, {max_width}]")
        if not min_height <= height <= max_height:
            raise ValueError(f"Height {height} not in range [{min_height}, {max_height}]")

        self.param_value = default
        self.param_min_width = min_width
        self.param_max_width = max_width
        self.param_min_height = min_height
        self.param_max_height = max_height

    def get_value(self):
        return self.param_value

    def set_value(self, value: Tuple[int, int]):
        if not isinstance(value, tuple) or len(value) != 2:
            raise TypeError("Value must be a tuple of 2 elements")
        width, height = value
        if not isinstance(width, int) or not isinstance(height, int):
            raise TypeError("Width and height must be integers")
        if not self.param_min_width <= width <= self.param_max_width:
            raise ValueError(f"Width {width} not in range [{self.param_min_width}, {self.param_max_width}]")
        if not self.param_min_height <= height <= self.param_max_height:
            raise ValueError(f"Height {height} not in range [{self.param_min_height}, {self.param_max_height}]")
        self.param_value = value
