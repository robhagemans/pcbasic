"""
PC-BASIC - interface.base
Interface utility classes

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os


# message displayed when wiating to close
WAIT_MESSAGE = u'Press a key to close window'
# message displayed when Alt-F4 inhibited
NOKILL_MESSAGE = u'to exit type <CTRL+BREAK> <ESC> SYSTEM'


class InitFailed(Exception):
    """Initialisation failed."""


class PluginRegister(object):
    """Plugin register."""

    def __init__(self):
        """Initialise plugin register."""
        self._plugins = {}

    def register(self, name):
        """Decorator to register a plugin."""
        def decorated_plugin(cls):
            self._plugins[name] = cls
            return cls
        return decorated_plugin

    def __getitem__(self, name):
        """Retrieve plugin."""
        return self._plugins[name]


class EnvironmentCache(object):
    """ Set environment variables for temporary use and clean up nicely."""

    def __init__(self):
        """Create the environment cache."""
        self._saved = {}

    def __enter__(self):
        """Context guard."""
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Context guard."""
        self.close()

    def set(self, key, value):
        """Set an environment variable and save the original value in the cache."""
        if key in self._saved:
            self.reset(key)
        self._saved[key] = os.environ.get(key)
        os.environ[key] = value

    def reset(self, key):
        """Restore the original value for an environment variable."""
        cached = self._saved.pop(key, None)
        if cached is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = cached

    def close(self):
        """Restore all environment variables."""
        for key in list(self._saved.keys()):
            self.reset(key)

    def __del__(self):
        """Clean up the cache."""
        self.close()


###############################################################################
# plugin registers

video_plugins = PluginRegister()
audio_plugins = PluginRegister()
