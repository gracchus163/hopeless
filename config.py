# coding=utf-8

import csv
import logging
import os
import re
import sys
from typing import Any, List

from errors import ConfigError
import yaml

logger = logging.getLogger()


class Config(object):
    def __init__(self, filepath):
        """
        Args:
            filepath (str): Path to config file
        """
        if not os.path.isfile(filepath):
            raise ConfigError(f"Config file '{filepath}' does not exist")

        # Load in the config file at the given filepath
        with open(filepath) as file_stream:
            self.config = yaml.safe_load(file_stream.read())

        # Logging setup
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s [%(levelname)s] %(message)s"
        )

        log_level = self._get_cfg(["logging", "level"], default="INFO")
        logger.setLevel(log_level)

        file_logging_enabled = self._get_cfg(
            ["logging", "file_logging", "enabled"], default=False
        )
        file_logging_filepath = self._get_cfg(
            ["logging", "file_logging", "filepath"], default="bot.log"
        )
        if file_logging_enabled:
            handler = logging.FileHandler(file_logging_filepath)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        console_logging_enabled = self._get_cfg(
            ["logging", "console_logging", "enabled"], default=True
        )
        if console_logging_enabled:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        # Storage setup
        self.database_filepath = self._get_cfg(
            ["storage", "database_filepath"], required=True
        )
        self.store_filepath = self._get_cfg(
            ["storage", "store_filepath"], required=True
        )

        # Create the store folder if it doesn't exist
        if not os.path.isdir(self.store_filepath):
            if not os.path.exists(self.store_filepath):
                os.mkdir(self.store_filepath)
            else:
                raise ConfigError(
                    f"storage.store_filepath '{self.store_filepath}' is not a directory"
                )

        # Matrix bot account setup
        self.user_id = self._get_cfg(["matrix", "user_id"], required=True)
        if not re.match("@.*:.*", self.user_id):
            raise ConfigError("matrix.user_id must be in the form @name:domain")

        self.user_password = self._get_cfg(["matrix", "user_password"], required=True)
        self.device_id = self._get_cfg(["matrix", "device_id"], required=True)
        self.device_name = self._get_cfg(
            ["matrix", "device_name"], default="nio-template"
        )
        self.homeserver_url = self._get_cfg(["matrix", "homeserver_url"], required=True)

        self.command_prefix = self._get_cfg(["command_prefix"], default="!c") + " "
        self.rooms_path = self._get_cfg(["rooms_path"], required=True)
        self.tokens_path = self._get_cfg(["tokens_path"], required=True)
        self.community = self._get_cfg(["community"], required=False)
        self.volunteer_community = self._get_cfg(
            ["volunteer_community"], required=False
        )
        self.presenter_community = self._get_cfg(
            ["presenter_community"], required=False
        )
        with open(self.tokens_path, "rt") as f:
            reader = csv.reader(f)
            self.tokens = dict(reader)
        with open(self.rooms_path, "rt") as f:
            self.rooms = f.read().splitlines()
        try:
            f = open("volunteers.csv", "rt")
            reader = csv.reader(f)
            self.volunteer_tokens = dict(reader)
            f.close()
        except FileNotFoundError:
            print("No volunteers.csv")
            self.volunteer_tokens = []
        try:
            f = open("volunteer_rooms.csv", "rt")
            self.volunteer_rooms = f.read().splitlines()
            f.close()
        except FileNotFoundError:
            print("No volunteer_rooms.csv")
            self.volunteer_rooms = []
        try:
            f = open("presenters.csv", "rt")
            reader = csv.reader(f)
            self.presenter_tokens = dict(reader)
            f.close()
        except FileNotFoundError:
            print("No presenters.csv")
            self.presenter_tokens = []
        try:
            f = open("presenter_rooms.csv", "rt")
            self.presenter_rooms = f.read().splitlines()
            f.close()
        except FileNotFoundError:
            print("No presenter_rooms.csv")
            self.presenter_rooms = []

    def _get_cfg(
        self, path: List[str], default: Any = None, required: bool = True,
    ) -> Any:
        """Get a config option from a path and option name, specifying whether it is
        required.

        Raises:
            ConfigError: If required is specified and the object is not found
                (and there is no default value provided), this error will be raised
        """
        # Sift through the the config until we reach our option
        config = self.config
        for name in path:
            config = config.get(name)

            # If at any point we don't get our expected option...
            if config is None:
                # Raise an error if it was required
                if required or not default:
                    raise ConfigError(f"Config option {'.'.join(path)} is required")

                # or return the default value
                return default

        # We found the option. Return it
        return config
