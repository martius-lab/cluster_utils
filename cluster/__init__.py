import warnings

warnings.simplefilter('always', UserWarning)


def custom_format_warning(msg, *args, **kwargs):
  # ignore everything except the message
  return 'WARNING: {}\n'.format(str(msg))


warnings.formatwarning = custom_format_warning

from .job_manager import hyperparameter_optimization, cluster_run
from .submission import execute_submission
from .report import init_plotting
from .settings import save_metrics_params, update_params_from_cmdline

from . import job_manager
from . import distributions
from . import analyze_results
from . import utils
from . import settings
from . import submission
from . import report
