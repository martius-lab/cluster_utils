from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import scipy
import scipy.stats


def clip(number, bounds):
  low, high = bounds
  return min(max(number, low), high)


class Distribution(object):
  def __init__(self, *, param, **kwargs):
    self.param_name = param
    self.samples = []
    self.iter = None

  def fit(self, data):
    raise NotImplementedError()

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

  def fit(self, data_points):
    self.mean, self.std = scipy.stats.norm.fit(np.array(data_points))
    assert (self.lower <= self.mean <= self.upper)

  def prepare_samples(self, howmany):
    self.samples = np.random.normal(size=howmany) * self.std + self.mean
    super().prepare_samples(howmany)

  def plot(self):
    pass


class IntNormal(TruncatedNormal, DistributionOverIntegers):
  pass


class TruncatedLogNormal(NumericalDistribution, BoundedDistribution):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.log_lower = np.log(self.lower)
    self.log_upper = np.log(self.upper)
    self.log_mean = 0.5 * (self.log_lower + self.log_upper)
    self.log_std = (self.log_upper - self.log_lower) / 4.0

  def fit(self, data_points):
    self.log_mean, self.log_std = scipy.stats.norm.fit(np.log(np.array(data_points)))
    assert (self.log_lower <= self.log_mean <= self.log_upper)

  def prepare_samples(self, howmany):
    self.samples = np.exp(np.random.normal(size=howmany) * self.log_std + self.log_mean)
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


class Discrete(Distribution):
  def __init__(self, *, options, **kwargs):
    super().__init__(**kwargs)
    self.option_list = options
    good_types = (bool, str, int, float, tuple)
    for item in options:
      if type(item) not in good_types:
        raise TypeError('Discrete options must from the following types: {}, {} failed'.format(good_types, item))
      if not hashable(item):
        raise TypeError('Discrete options must be hashable, {} failed'.format(item))

    self.probs = [1.0 / len(options) for item in options]

  def fit(self, samples):
    frequencies = Counter(samples)
    # Add plus one to all frequencies to keep all options
    self.probs = [(1.0 / (len(samples) + len(self.option_list))) * (1.0 + frequencies[val]) for val in self.option_list]

  def prepare_samples(self, howmany):
    self.samples = np.random.choice(self.option_list, p=self.probs, size=howmany)
    super().prepare_samples(howmany)

  def plot(self):
    plt.pie(self.probs, labels=self.option_list, autopct='%1.1f%%', shadow=True)
    plt.show()
