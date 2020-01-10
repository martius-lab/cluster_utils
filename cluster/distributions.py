from abc import ABC, abstractmethod
from collections import Counter
from warnings import warn

import matplotlib.pyplot as plt
import numpy as np
import scipy
import scipy.stats

from .constants import *
from .utils import check_valid_name


def clip(number, bounds):
  low, high = bounds
  return min(max(number, low), high)


class Distribution(ABC):
  def __init__(self, *, param, **kwargs):
    self.param_name = param

    check_valid_name(self.param_name)

    self.samples = []
    self.iter = None

  @abstractmethod
  def fit(self, data):
    pass

  def sample(self):
    return next(self.iter)

  def prepare_samples(self, howmany):
    self.iter = iter(self.samples)


class BoundedDistribution(Distribution):
  def __init__(self, *, bounds, **kwargs):
    self.lower, self.upper = bounds
    if not self.lower < self.upper:
      raise ValueError('Bounds don\'t yield a proper interval.')
    super().__init__(**kwargs)

  def prepare_samples(self, howmany):
    self.samples = [clip(sample, (self.lower, self.upper)) for sample in self.samples]
    super().prepare_samples(howmany)


def significant_digits(number, digits):
  return '{:g}'.format(float('{:.{p}g}'.format(number, p=digits)))


def shatters(samples, digits):
  """ Decide whether rounding to 'digits' significant digits still keep the sample set shattered enough."""
  orig_size = len(set(samples))
  new_size = len(set(significant_digits(num, digits) for num in samples))
  return new_size >= orig_size // 2


def smart_round(samples):
  for i in [1, 2, 3, 4, 5]:  # Try up to five significant digits
    if shatters(samples, i):
      return (float(significant_digits(num, i)) for num in samples)
  return samples


class NumericalDistribution(Distribution):
  def __init__(self, *, smart_rounding=True, **kwargs):
    self.smart_rounding = smart_rounding
    super().__init__(**kwargs)

  def prepare_samples(self, howmany):
    if self.smart_rounding:
      self.samples = smart_round(self.samples)
    super().prepare_samples(howmany)


class DistributionOverIntegers(Distribution):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    if hasattr(self, 'lower') and hasattr(self, 'upper'):
      if not (type(self.lower) == type(self.upper) == int):
        raise TypeError('Bounds for integer distribution must be integral')

  def prepare_samples(self, howmany):
    self.samples = [int(sample + 0.5) for sample in self.samples]
    super().prepare_samples(howmany)


class TruncatedNormal(NumericalDistribution, BoundedDistribution):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.mean = 0.5 * (self.lower + self.upper)
    self.std = (self.upper - self.lower) / 4.0
    self.last_mean = None

  def fit(self, data_points):
    self.mean, self.std = scipy.stats.norm.fit(np.array(data_points))
    if not (self.lower <= self.mean <= self.upper):
      warn('Mean of {} is out of bounds'.format(self.param_name))

  def prepare_samples(self, howmany):
    howmany = min(10, howmany)  # HACK: for smart rounding a reasonable sample size is needed
    mean_to_use = self.mean if self.last_mean is None else 2*self.mean - self.last_mean
    self.last_mean = self.mean
    if not (self.lower <= mean_to_use <= self.upper):
      mean_to_use = self.mean
    self.samples = np.random.normal(size=howmany) * self.std + mean_to_use
    super().prepare_samples(howmany)

  def plot(self):
    pass


class IntNormal(TruncatedNormal, DistributionOverIntegers):
  pass


class TruncatedLogNormal(NumericalDistribution, BoundedDistribution):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    if self.lower < 1e-10:
      raise ValueError("Bounds for {} must be positive.".format(self.__class__.__name__))
    self.log_lower = np.log(self.lower)
    self.log_upper = np.log(self.upper)
    self.log_mean = 0.5 * (self.log_lower + self.log_upper)
    self.log_std = (self.log_upper - self.log_lower) / 4.0
    self.last_log_mean = None

  def fit(self, data_points):
    self.last_log_mean = self.log_mean
    self.log_mean, self.log_std = scipy.stats.norm.fit(np.log(np.array(data_points)))
    if not (self.log_lower <= self.log_mean <= self.log_upper):
      warn('Mean of {} is out of bounds'.format(self.param_name))

  def prepare_samples(self, howmany):
    howmany = min(10, howmany)  # HACK: for smart rounding a reasonable sample size is needed
    log_mean_to_use = self.log_mean if self.last_log_mean is None else 2 * self.log_mean - self.last_log_mean
    if not (self.lower <= log_mean_to_use <= self.upper):
      log_mean_to_use = self.log_mean
    self.samples = np.exp(np.random.normal(size=howmany) * self.log_std + log_mean_to_use)
    super().prepare_samples(howmany)


class IntLogNormal(TruncatedLogNormal, DistributionOverIntegers):
  pass


def hashable(v):
  """Determine whether 'v' can be hashed."""
  try:
    hash(v)
  except TypeError:
    return False
  return True


class RelaxedCounter(Counter):
  """Counter class that potentially falls back to a string representation of a key"""
  def __getitem__(self, key):
    if key not in self.keys():
      if str(key) in self.keys():
        warn('String comparison used for key {}'.format(key))
        return super().__getitem__(str(key))
    return super().__getitem__(key)


class Discrete(Distribution):
  def __init__(self, *, options, **kwargs):
    super().__init__(**kwargs)
    self.option_list = options
    for item in options:
      if not any([isinstance(item, allowed_type) for allowed_type in PARAM_TYPES]):
        raise TypeError('Discrete options must from the following types: {}, not {}'.format(PARAM_TYPES, type(item)))
      if not hashable(item):
        raise TypeError('Discrete options must be hashable, {} failed'.format(item))

    self.probs = [1.0 / len(options) for _ in options]

  def fit(self, samples):
    frequencies = RelaxedCounter(samples)
    # Add plus one to all frequencies to keep all options
    self.probs = [(1.0 / (len(samples) + len(self.option_list))) * (1.0 + frequencies[val]) for val in self.option_list]
    sum = np.sum(self.probs)
    if not np.isclose(sum, 1.0):
      warn('Probabilities of \'{}\' do not sum up to one.'.format(self.param_name))
      self.probs = list(np.array(self.probs) / sum)

  def prepare_samples(self, howmany):
    howmany = min(10, howmany)  # HACK: for smart rounding a reasonable sample size is needed
    self.samples = np.random.choice(self.option_list, p=self.probs, size=howmany)
    super().prepare_samples(howmany)

  def plot(self):
    plt.pie(self.probs, labels=self.option_list, autopct='%1.1f%%', shadow=True)
    plt.show()
