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
        lhs, eq, rhs = extra_flag.rpartition("=")
        parsed_lhs = lhs.split(".")
        new_lhs = "base_dict" + "".join([f'["{item}"]' for item in parsed_lhs])
        cmd = new_lhs + eq + rhs
        try:
            exec(cmd)
        except Exception as e:
            raise RuntimeError(f"Command {cmd} failed") from e
