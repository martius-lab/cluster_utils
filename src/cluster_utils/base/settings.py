import ast
from typing import Any, Mapping

from cluster_utils.base import constants


class SettingsError(Exception):
    """Custom error for anything related to the settings."""

    ...


def check_reserved_params(orig_dict: Mapping[str, Any]) -> None:
    """Check if the given dict contains reserved keys.  If yes, raise SettingsError."""
    for key in orig_dict:
        if key in constants.RESERVED_PARAMS:
            msg = f"'{key}' is a reserved param name"
            raise SettingsError(msg)


def add_cmd_line_params(base_dict, extra_flags):
    for extra_flag in extra_flags:
        name_path, eq, value = extra_flag.partition("=")
        name_path = name_path.strip()
        value = value.strip()

        # fail if extra_flag doesn't have the format "<xxx>=<yyy>"
        if any([not name_path, not eq, not value]):
            raise SettingsError(f"Invalid format for {extra_flag}")

        # parse value
        try:
            literal_value = ast.literal_eval(value)
        except Exception as e:
            raise SettingsError(
                f"Failed to parse value '{value}' in '{extra_flag}'"
            ) from e

        # walk through base_dict, based on name_path
        try:
            name_segments = name_path.split(".")
            _dict = base_dict
            for seg in name_segments[:-1]:
                _dict = _dict[seg]
        except KeyError as e:
            raise SettingsError(
                f"Invalid settings path '{name_path}' in '{extra_flag}'"
            ) from e

        _dict[name_segments[-1]] = literal_value
