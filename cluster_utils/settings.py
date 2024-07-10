from __future__ import annotations

import argparse
import ast
import enum
import os
import pathlib
from typing import Any, NamedTuple, Optional

import smart_settings

from cluster_utils.base.settings import add_cmd_line_params, check_reserved_params

from .optimizers import GridSearchOptimizer, Metaoptimizer, NGOptimizer
from .utils import (
    check_import_in_fixed_params,
    rename_import_promise,
)


class GenerateReportSetting(enum.Enum):
    """The possible values for the "generate_report" setting."""

    #: Do not generate report automatically.
    NEVER = 0
    #: Generate report once when the optimization has finished.
    WHEN_FINISHED = 1
    #: Generate report after every iteration of the optimization.
    EVERY_ITERATION = 2

    @staticmethod
    def parse_generate_report_setting_hook(settings: dict[str, Any]) -> None:
        """Parse the "generate_report" parameter in the settings dict.

        Check if a key "generate_report" exists in the settings dictionary and parse its
        value to replace it with the proper enum value.  If no entry exists in settings,
        it will be added with default value ``NEVER``.

        Raises:
            ValueError: if the value in settings cannot be mapped to one of the enum
                values.
        """
        key = "generate_report"
        value_str: str = settings.get(key, GenerateReportSetting.NEVER.name)
        value_str = value_str.upper()
        try:
            value_enum = GenerateReportSetting[value_str]
        except KeyError as e:
            options = (
                GenerateReportSetting.NEVER.name,
                GenerateReportSetting.WHEN_FINISHED.name,
                GenerateReportSetting.EVERY_ITERATION.name,
            )
            raise ValueError(
                f"Invalid value {e} for setting {key}.  Valid options are {options}."
            ) from None

        settings[key] = value_enum


class SingularitySettings(NamedTuple):
    #: Path to time Singularity image
    image: str

    #: Singularity executable.  Defaults to "singularity" but can, for example, be used
    #: to explicitly use Apptainer instead.
    executable: str = "singularity"

    #: Per default the container is run with `singularity exec`.  Set this to True to
    #: use `singularity run` instead (for images that use a run script for environment
    #: setup before executing the given command).
    use_run: bool = False

    #: List of additional arguments to Singularity.
    args: list[str] = []

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> SingularitySettings:
        try:
            obj = cls(**settings)
        except TypeError as e:
            raise ValueError(f"Failed to process Singularity settings: {e}") from e

        # some additional checks
        if not os.path.exists(os.path.expanduser(obj.image)):
            raise FileNotFoundError(f"Singularity image {obj.image} not found.")

        return obj


def is_settings_file(cmd_line):
    if (
        cmd_line.endswith(".json")
        or cmd_line.endswith(".yml")
        or cmd_line.endswith(".yaml")
        or cmd_line.endswith(".toml")
    ):
        if not os.path.isfile(cmd_line):
            raise FileNotFoundError(f"{cmd_line}: No such settings file found")
        return True
    else:
        return False


def is_parseable_dict(cmd_line):
    try:
        res = ast.literal_eval(cmd_line)
        return isinstance(res, dict)
    except Exception as e:
        print("WARNING: Dict literal eval suppressed exception: ", e)
        return False


def init_main_script_argument_parser(description: str) -> argparse.ArgumentParser:
    """Initialise ArgumentParser with the base arguments

    Basic construction of an ArgumentParser with everything that is common between the
    cluster_utils main scripts (i.e. grid_search and hp_optimization).

    Args:
        description: Used in the help text shown when run with ``--help``.

    Returns:
        ArgumentParser instance with basic arguments already configured.
        Script-specific additional options can still be added.
    """
    parser = argparse.ArgumentParser(
        description=description, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "settings_file", type=pathlib.Path, help="Path to the settings file."
    )
    parser.add_argument(
        "settings",
        nargs="*",
        type=str,
        metavar="KEY_VALUE",
        help="""Additional settings in the format '<key>=<value>'.  This will overwrite
            settings in the settings file.  Key has to match a configuration option,
            value has to be valid Python.  Example: 'results_dir="/tmp"'
            'optimization_setting.run_local=True'
        """,
    )
    return parser


def read_main_script_params_from_args(args: argparse.Namespace):
    """Read settings for grid_search/hp_optimization from command line args.

    Args:
        args: Arguments parsed by ArgumentParser which was created using
            :function:`init_main_script_argument_parser`.

    Returns:
        smart_settings parameter structure.
    """
    return read_main_script_params_with_smart_settings(
        settings_file=args.settings_file,
        cmdline_settings=args.settings,
        pre_unpack_hooks=[check_import_in_fixed_params],
        post_unpack_hooks=[
            rename_import_promise,
            GenerateReportSetting.parse_generate_report_setting_hook,
        ],
    )


def read_main_script_params_with_smart_settings(
    settings_file: pathlib.Path,
    cmdline_settings: Optional[list[str]] = None,
    make_immutable: bool = True,
    dynamic: bool = True,
    pre_unpack_hooks: Optional[list] = None,
    post_unpack_hooks: Optional[list] = None,
) -> smart_settings.AttributeDict:
    """Read parameters for the cluster_utils main script using smart_settings.

    Args:
        settings_file:  Path to the settings file.
        cmdline_settings:  List of additional parameters provided via command line.
        make_immutable:  See ``smart_settings.load()``
        dynamic:  See ``smart_settings.load()``
        pre_unpack_hooks:  See ``smart_settings.load()``
        post_unpack_hooks:  See ``smart_settings.load()``

    Returns:
        Parameters as loaded by smart_settings.
    """
    cmdline_settings = cmdline_settings or []
    pre_unpack_hooks = pre_unpack_hooks or []
    post_unpack_hooks = post_unpack_hooks or []

    if not is_settings_file(os.fspath(settings_file)):
        raise ValueError(f"{settings_file} is not a supported settings file.")

    def add_cmd_params(orig_dict):
        add_cmd_line_params(orig_dict, cmdline_settings)

    return smart_settings.load(
        os.fspath(settings_file),
        make_immutable=make_immutable,
        dynamic=dynamic,
        post_unpack_hooks=([add_cmd_params, check_reserved_params] + post_unpack_hooks),
        pre_unpack_hooks=pre_unpack_hooks,
    )


optimizer_dict = {
    "cem_metaoptimizer": Metaoptimizer,
    "nevergrad": NGOptimizer,
    "gridsearch": GridSearchOptimizer,
}
