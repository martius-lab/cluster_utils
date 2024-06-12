import contextlib
import importlib.metadata

from .client import (
    announce_early_results,
    announce_fraction_finished,
    cluster_main,
    exit_for_resume,
    read_params_from_cmdline,
    save_metrics_params,
)
from .job_manager import grid_search, hp_optimization

# The version is set based on git at install time, so we get it from the metadata of the
# installed package here.  If this file is imported without the package being installed,
# this will fail.  In that case, catch the error and do not set __version__ at all.
with contextlib.suppress(importlib.metadata.PackageNotFoundError):
    __version__ = importlib.metadata.version(__package__)

__all__ = [
    "grid_search",
    "hp_optimization",
    "announce_early_results",
    "announce_fraction_finished",
    "cluster_main",
    "exit_for_resume",
    "save_metrics_params",
    "read_params_from_cmdline",
]
