import warnings

warnings.simplefilter('always', UserWarning)


def custom_format_warning(msg, *args, **kwargs):
  # ignore everything except the message
  return 'WARNING: {}\n'.format(str(msg))


warnings.formatwarning = custom_format_warning

from .job_manager import hyperparameter_optimization, asynchronous_optimization, grid_search
#from .submission import execute_iterated_submission
from .report import init_plotting
from .settings import save_metrics_params, update_params_from_cmdline
from .parallel_executor import execute_parallel_shell_scripts

from . import job_manager
from . import distributions
from . import optimizers
from . import utils
from . import settings
#from . import submission
from . import report
from . import parallel_executor
from . import submission_state
from . import optimize_hyperparams
