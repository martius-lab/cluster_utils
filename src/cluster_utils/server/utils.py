from __future__ import annotations

import collections
import datetime
import enum
import itertools
import json
import logging
import os
import pathlib
import pickle
import random
import re
import shutil
import signal
from collections import defaultdict
from pathlib import Path
from time import sleep
from typing import Any

import colorama

from cluster_utils.base import constants


class ClusterRunType(enum.Enum):
    """Enumeration of possible cluster run types."""

    GRID_SEARCH = 0
    HP_OPTIMIZATION = 1


class SignalWatcher:
    """Watch for a signal.

    Upon initialization, a signal handler is registered to watch for the specified
    signal.  The method :meth:`has_received_signal` can then be used to check if the
    signal was received.

    **Note:** This overwrites any existing signal handler for the specified signal.

    Signal flags are stored in a class variable, so they are shared among all instances.
    This allows use of multiple instances for the same signal in different places of the
    code.
    """

    # Use a class variable dict to store received signals.  This dict will be shared
    # among all instances of SignalWatcher and thus allow multiple instances to watch
    # the same signal without ousting each other (since new instances will overwrite the
    # signal handler of the older ones).
    received_signals: dict[signal.Signals, bool] = {}

    def __init__(self, signal_to_watch_for: int = signal.SIGINT) -> None:
        """
        Args:
            signal_to_watch_for: The signal to watch for.
        """
        self.signal = signal_to_watch_for
        signal.signal(signal_to_watch_for, self._signal_handler)

    def _signal_handler(self, sig, frame) -> None:
        """Handles the received signal.

        Args:
            sig (int): The signal number.
            frame (frame object): The current stack frame.
        """
        SignalWatcher.received_signals[sig] = True

    def has_received_signal(self) -> bool:
        """Checks if the signal has been received.

        Returns:
            bool: True if the signal has been received, False otherwise.
        """
        return self.signal in SignalWatcher.received_signals


def shorten_string(string, max_len):
    if len(string) > max_len - 3:
        return "..." + string[-max_len + 3 :]
    return string


def list_to_tuple(maybe_list):
    if isinstance(maybe_list, list):
        return tuple(maybe_list)
    else:
        return maybe_list


def check_valid_param_name(string):
    pat = "[A-Za-z0-9_.:-]*$"
    if not isinstance(string, str):
        raise TypeError("Parameter '{}' not valid. String expected.".format(string))
    if string in constants.RESERVED_PARAMS + (constants.WORKING_DIR,):
        # working_dir cannot be injected in grid_search/hpo
        raise ValueError(
            "Parameter name {} is reserved, cannot be overwritten from outside.".format(
                string
            )
        )
    if string.endswith(constants.STD_ENDING):
        raise ValueError(
            "Parameter name '{}' not valid."
            "Ends with '{}' (may cause collisions)".format(string, constants.STD_ENDING)
        )
    if not bool(re.compile(pat).match(string)):
        raise ValueError(
            "Parameter name '{}' not valid. Only '[0-9][a-z][A-Z]_-.:' allowed.".format(
                string
            )
        )
    if string.startswith(".") or string.endswith("."):
        raise ValueError(
            "Parameter name '{}' not valid. '.' not allowed the end".format(string)
        )


def rm_dir_full(dir_name):
    logger = logging.getLogger("cluster_utils")
    sleep(0.5)
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name, ignore_errors=True)

    # filesystem is sometimes slow to response
    if os.path.exists(dir_name):
        sleep(1.0)
        shutil.rmtree(dir_name, ignore_errors=True)

    if os.path.exists(dir_name):
        logger.warning(f"Removing of dir {dir_name} failed")


def get_sample_generator(
    samples, hyperparam_dict, distribution_list, extra_settings=None
):
    logger = logging.getLogger("cluster_utils")
    if hyperparam_dict and distribution_list:
        raise TypeError(
            "At most one of hyperparam_dict and distribution list can be provided"
        )
    if not hyperparam_dict and not distribution_list:
        logger.warning("No hyperparameters vary. Only running restarts")
        return iter([{}])
    if distribution_list and not samples:
        raise TypeError("Number of samples not specified")
    if distribution_list:
        ans = distribution_list_sampler(distribution_list, samples)
    elif samples:
        assert hyperparam_dict
        ans = hyperparam_dict_samples(hyperparam_dict, samples)
    else:
        ans = hyperparam_dict_product(hyperparam_dict)
    if extra_settings is not None:
        return itertools.chain(extra_settings, ans)
    else:
        return ans


def process_other_params(other_params, hyperparam_dict, distribution_list):
    if hyperparam_dict:
        name_list = hyperparam_dict.keys()
    elif distribution_list:
        name_list = [distr.param_name for distr in distribution_list]
    else:
        name_list = []
    for name, value in other_params.items():
        check_valid_param_name(name)
        if name in name_list:
            raise ValueError("Duplicate setting '{}' in other params!".format(name))
        value = list_to_tuple(value)
        if not isinstance(value, constants.PARAM_TYPES):
            raise TypeError(
                f"Settings must from the following types: {constants.PARAM_TYPES}, "
                f"not {type(value)} for setting {name}: {value}"
            )
    nested_items = [
        (list(filter(lambda x: x, name.split("."))), value)
        for name, value in other_params.items()
    ]
    return nested_to_dict(nested_items)


def validate_hyperparam_dict(hyperparam_dict):
    for name, option_list in hyperparam_dict.items():
        if isinstance(name, tuple):
            [check_valid_param_name(n) for n in name]
        else:
            check_valid_param_name(name)
        if not isinstance(option_list, list):
            raise TypeError(
                f"Entries in hyperparam dict must be type list (not {name}:"
                f" {type(option_list)})"
            )
        option_list = [list_to_tuple(o) for o in option_list]
        hyperparam_dict[name] = option_list
        for item in option_list:
            if not isinstance(item, constants.PARAM_TYPES):
                raise TypeError(
                    f"Settings must from the following types: {constants.PARAM_TYPES},"
                    f" not {type(item)}"
                )


def hyperparam_dict_samples(hyperparam_dict, num_samples):
    validate_hyperparam_dict(hyperparam_dict)
    nested_items = [
        (name.split(constants.OBJECT_SEPARATOR), options)
        for name, options in hyperparam_dict.items()
    ]

    for _ in range(num_samples):
        nested_samples = [
            (nested_path, random.choice(options))
            for nested_path, options in nested_items
        ]
        yield nested_to_dict(nested_samples)


def hyperparam_dict_product(hyperparam_dict):
    validate_hyperparam_dict(hyperparam_dict)
    names, option_lists = zip(*hyperparam_dict.items())

    for sample_from_product in itertools.product(*list(option_lists)):
        list_of_samples = []
        for name_or_tuple, option_or_tuple in zip(names, sample_from_product):
            if isinstance(name_or_tuple, tuple):
                # in case we specify a tuple/list of keys and values, we unzip them here
                list_of_samples.extend(zip(name_or_tuple, option_or_tuple))
            else:
                list_of_samples.append((name_or_tuple, option_or_tuple))
        nested_items = [
            (name.split(constants.OBJECT_SEPARATOR), options)
            for name, options in list_of_samples
        ]
        yield nested_to_dict(nested_items)


def default_to_regular(d):
    if isinstance(d, defaultdict):
        d = {k: default_to_regular(v) for k, v in d.items()}
    return d


def nested_to_dict(nested_items):
    def nested_dict():
        return defaultdict(nested_dict)

    result = nested_dict()
    for nested_key, value in nested_items:
        ptr = result
        for key in nested_key[:-1]:
            ptr = ptr[key]
        ptr[nested_key[-1]] = value
    return default_to_regular(result)


def distribution_list_sampler(distribution_list, num_samples):
    for distr in distribution_list:
        distr.prepare_samples(howmany=num_samples)
    for _ in range(num_samples):
        nested_items = [
            (distr.param_name.split(constants.OBJECT_SEPARATOR), distr.sample())
            for distr in distribution_list
        ]
        yield nested_to_dict(nested_items)


home = str(Path.home())


def make_red(text):
    return f"\x1b[1;31m{text}\x1b[0m"


def get_time_string() -> str:
    """Get representation of current time as string"""
    return f"{datetime.datetime.now():%Y%m%d-%H%M%S}"


def get_cache_directory() -> str:
    """Return path to cache directory used by cluster_utils."""
    if "CLUSTER_UTILS_CACHE_DIR" in os.environ:
        cache_dir = os.environ["CLUSTER_UTILS_CACHE_DIR"]
    else:
        cache_dir = os.path.join(home, ".cache", "cluster_utils")

    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)

    return cache_dir


def make_temporary_dir(name: str) -> str:
    """Make temporary directory with specified name.

    Directory name is made unique by appending an id if the directory already exists.
    """
    base_dir = get_cache_directory()
    run_dir = os.path.join(base_dir, name)

    count = 2
    while os.path.isdir(run_dir):
        run_dir = os.path.join(base_dir, f"{name}-{count}")
        count += 1

    os.mkdir(run_dir, mode=0o700)
    return run_dir


def dict_to_dirname(setting, job_id, smart_naming=True):
    vals = [
        "{}={}".format(str(key)[:3], str(value)[:6])
        for key, value in setting.items()
        if not isinstance(value, dict)
    ]
    res = "{}_{}".format(job_id, "_".join(vals))
    if len(res) < 35 and smart_naming:
        return res
    return str(job_id)


def update_recursive(d, u, defensive=False):
    for k, v in u.items():
        if defensive and k not in d:
            raise KeyError("Updating a non-existing key")
        if isinstance(v, collections.abc.Mapping):
            d[k] = update_recursive(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def check_import_in_fixed_params(setting_dict):
    if "fixed_params" in setting_dict and "__import__" in setting_dict["fixed_params"]:
        raise ImportError(
            "Cannot import inside fixed params. Did you mean __import_promise__?"
        )


def rename_import_promise(setting_dict):
    if (
        "fixed_params" in setting_dict
        and "__import_promise__" in setting_dict["fixed_params"]
    ):
        setting_dict["fixed_params"]["__import__"] = setting_dict["fixed_params"][
            "__import_promise__"
        ]
        del setting_dict["fixed_params"]["__import_promise__"]


def log_and_print(logger, msg):
    logger.info(msg)
    print(msg)


def save_metadata(results_dir: str | os.PathLike, cluster_run_type, start_time) -> None:
    """Save file with metadata about the cluster run in the results directory.

    The file will be saved with the name defined in :var:`constants.METADATA_FILE`.

    **If the file already exists, it will be overwritten!**

    Args:
        results_dir:  Directory in which the data should be saved.
        TODO

    Raises:
        NotADirectoryError: if results_dir does not exist or is not a directory.
    """
    results_dir = pathlib.Path(results_dir)

    if not results_dir.is_dir():
        raise NotADirectoryError(results_dir)

    logger = logging.getLogger("cluster_utils")

    filename = results_dir / constants.METADATA_FILE
    logger.info("Save metadata to %s", filename)
    with open(filename, "w") as f:
        json.dump(
            {
                "run_type": cluster_run_type.name,
                "start_time": start_time.isoformat(),
            },
            f,
        )


def save_report_data(results_dir: str | os.PathLike, **kwargs: Any) -> None:
    """Save the given keyword arguments as report data in the results directory.

    The file will be saved with the name defined in :var:`constants.REPORT_DATA_FILE`
    and should contain all data that is needed for offline-generation of the report,
    which is not already saved in separate files.

    **If the file already exists, it will be overwritten!**

    Args:
        results_dir:  Directory in which the data should be saved.
        kwargs:  Arbitrary number of objects that will be saved in the report data file.
            Given objects must be picklable.

    Raises:
        NotADirectoryError: if results_dir does not exist or is not a directory.
    """
    results_dir = pathlib.Path(results_dir)

    if not results_dir.is_dir():
        raise NotADirectoryError(results_dir)

    logger = logging.getLogger("cluster_utils")

    filename = results_dir / constants.REPORT_DATA_FILE
    logger.info("Save report data to %s", filename)
    with open(filename, "wb") as f:
        pickle.dump(kwargs, f)


def styled(text: str, *args) -> str:
    """Little helper to apply color/style using colorama on a string.

    It simply prepends all given args to text and appends ``colorama.Style.RESET_ALL``.
    """
    return "".join([*args, text, colorama.Style.RESET_ALL])
