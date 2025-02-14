"""Provide storage for Remember The Milk integration."""

from __future__ import annotations

import json
import os
from typing import Any

from homeassistant.core import HomeAssistant

from .const import CONF_ID_MAP, CONF_LIST_ID, CONF_TASK_ID, CONF_TIMESERIES_ID, LOGGER

CONFIG_FILE_NAME = ".remember_the_milk.conf"


class RememberTheMilkConfiguration:
    """Internal configuration data for RememberTheMilk class.

    This class stores the authentication token it get from the backend.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Create new instance of configuration."""
        self._config_file_path = hass.config.path(CONFIG_FILE_NAME)
        self._config: dict[str, Any] = {}

    def setup(self) -> None:
        """Set up the configuration."""
        if not os.path.isfile(self._config_file_path):
            return
        try:
            LOGGER.debug("Loading configuration from file: %s", self._config_file_path)
            with open(self._config_file_path, encoding="utf8") as config_file:
                self._config = json.load(config_file)
        except ValueError:
            LOGGER.error(
                "Failed to load configuration file, creating a new one: %s",
                self._config_file_path,
            )
            self._config = {}

    def save_config(self) -> None:
        """Write the configuration to a file."""
        with open(self._config_file_path, "w", encoding="utf8") as config_file:
            json.dump(self._config, config_file)

    def _initialize_profile(self, profile_name: str) -> None:
        """Initialize the data structures for a profile."""
        if profile_name not in self._config:
            self._config[profile_name] = {}
        if CONF_ID_MAP not in self._config[profile_name]:
            self._config[profile_name][CONF_ID_MAP] = {}

    def get_rtm_id(
        self, profile_name: str, hass_id: str
    ) -> tuple[int, int, int] | None:
        """Get the RTM ids for a Home Assistant task ID.

        The id of a RTM tasks consists of the tuple:
        list id, timeseries id and the task id.
        """
        self._initialize_profile(profile_name)
        ids = self._config[profile_name][CONF_ID_MAP].get(hass_id)
        if ids is None:
            return None
        return ids[CONF_LIST_ID], ids[CONF_TIMESERIES_ID], ids[CONF_TASK_ID]

    def set_rtm_id(
        self,
        profile_name: str,
        hass_id: str,
        list_id: int,
        time_series_id: int,
        rtm_task_id: int,
    ) -> None:
        """Add/Update the RTM task ID for a Home Assistant task IS."""
        self._initialize_profile(profile_name)
        id_tuple = {
            CONF_LIST_ID: list_id,
            CONF_TIMESERIES_ID: time_series_id,
            CONF_TASK_ID: rtm_task_id,
        }
        self._config[profile_name][CONF_ID_MAP][hass_id] = id_tuple
        self.save_config()

    def delete_rtm_id(self, profile_name, hass_id) -> None:
        """Delete a key mapping."""
        self._initialize_profile(profile_name)
        if hass_id in self._config[profile_name][CONF_ID_MAP]:
            del self._config[profile_name][CONF_ID_MAP][hass_id]
            self.save_config()
