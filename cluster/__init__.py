print('Local version')

__all__ = []

def export(defn):
  globals()[defn.__name__] = defn
  __all__.append(defn)
  return defn

import warnings
warnings.simplefilter('always', UserWarning)

def custom_formatwarning(msg, *args, **kwargs):
  # ignore everything except the message
  return 'WARNING: {}\n'.format(str(msg))


warnings.formatwarning = custom_formatwarning


from .job_manager import *
from . import distributions
from . import analyze_results
from . import utils
from . import settings
from .report import run_report
