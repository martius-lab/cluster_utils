import numpy as np
import scipy
import scipy.stats
from collections import Counter
import matplotlib.pyplot as plt


class Distribution(object):
  def __init__(self, param_name, **kwargs):
    self.param_name = param_name

  def fit(self, samples):
    raise NotImplementedError('Calling abstract class function')
    return False

  def sample(self):
    raise NotImplementedError('Calling abstract class function')
    return False

  def plot(self):
    raise NotImplementedError('Calling abstract class function')
    return False


class TruncatedNormal(Distribution):
  def __init__(self, param_name, bounds, sample_decimals=None):
    self.lower, self.upper = bounds

    self.mean = 0.5 * (self.lower + self.upper)
    self.std = 0.5 * (self.upper - self.lower)

    self.sample_decimals = sample_decimals
    super().__init__(param_name)

  def fit(self, samples):
    self.mean, self.std = scipy.stats.norm.fit(samples)
    if not (self.lower < self.mean < self.upper):
      raise ValueError('Estimated mean not in bounds')

  def _ab_from_bounds(self):
    return (self.lower - self.mean) / self.std, (self.upper - self.mean) / self.std

  def sample(self):
    while True:
      sample = scipy.stats.norm.rvs(loc=self.mean, scale=self.std, size=1)[0]
      if self.lower < sample < self.upper:
        if self.sample_decimals:
          return np.round(sample, decimals=self.sample_decimals)
        else:
          return sample

  def plot(self):
    x = np.linspace(self.lower - 2.0, self.upper + 2.0, 100)
    pdf_fitted = scipy.stats.truncnorm.pdf(x, *self._ab_from_bounds(), loc=self.mean, scale=self.std)
    pylab.plot(x, pdf_fitted, 'r-')
    show()


class IntNormal(TruncatedNormal):
  def __init__(self, *args, sample_decimals=None, **kwargs):
    super().__init__(*args, **kwargs)
    self.lower -= 0.45
    self.upper += 0.45
    self._sample_decimals = sample_decimals

  def sample(self):
    if self._sample_decimals:
      return np.round(int(super().sample() + 0.5), self._sample_decimals)
    else:
      return int(super().sample() + 0.5)


class LogDist(Distribution):
  def __init__(self, *args, bounds, sample_decimals=None, **kwargs):
    low, up = bounds
    bounds = np.log(low), np.log(up)
    self._sample_decimals = sample_decimals
    super().__init__(*args, bounds=bounds, sample_decimals=None, **kwargs)

  def fit(self, samples):
    new_samples = list(np.log(np.array(samples)))
    return super().fit(new_samples)

  def sample(self):
    log_sample = super().sample()
    if self._sample_decimals is not None:
      return np.round(np.exp(log_sample), decimals=self._sample_decimals)
    else:
      return np.exp(log_sample)


class LogTruncNormal(LogDist, TruncatedNormal):
  pass


class LogIntNormal(LogTruncNormal):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if self.decimals is None:
      self.decimals = 0

  def sample(self):
    return int(super().sample())


class Discrete(Distribution):
  def __init__(self, param_name, options):
    self.param_name = param_name
    self.option_list = options
    self.probs = [1.0 / len(options) for item in options]
    super().__init__(param_name)

  def fit(self, samples):
    frequencies = Counter(samples)
    print(frequencies)
    self.probs = [(1.0 / len(samples)) * frequencies[val] for val in self.option_list]

  def sample(self):
    return np.random.choice(self.option_list, p=self.probs)

  def plot(self):
    plt.pie(self.probs, labels=self.option_list, autopct='%1.1f%%', shadow=True)
    plt.show()