"""This is package is deprecated!  Use `cluster_utils` instead."""

import warnings

warnings.warn(
    "The 'cluster' package has been renamed to 'cluster_utils'.  Please update your"
    " code accordingly.  Importing 'cluster' is deprecated and will be removed in the"
    " next major release!",
    FutureWarning,
    stacklevel=2,
)

from cluster_utils import *  # noqa F403
