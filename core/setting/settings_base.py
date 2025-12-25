class SettingsBase:
    """Base class for all settings.
    Must use param_ prefixed variable names to be serialised"""

    def get_value(self):
        """Get the current value of the setting."""
        raise NotImplementedError

    def set_value(self, value):
        """Set the value of the setting with validation."""
        raise NotImplementedError

    def serialise(self):
        """Serialise all parameters into a dict. Parameters must use param_ as a prefix"""
        serialised_data = {}
        for k, v in self.__dict__.items():
            if k.startswith('param_'):
                serialised_data[k] = v

        return serialised_data

    def deserialise(self, serialised_data):
        """Deserialise all params into the setting.
        For safety, only parameters already part of the setting will be updated"""
        for k in self.__dict__:
            if k.startswith('param_') and k in serialised_data:
                self.__setattr__(k, serialised_data[k])
