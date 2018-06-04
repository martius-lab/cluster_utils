from warnings import warn


class OneTimeExceptionHandler(object):
  def __init__(self, ignore_errors):
    self.ignore_errors = ignore_errors
    self.seen = set([])

  def maybe_raise(self, msg):
    """ Raise UNSEEN exception / warning. """
    msg = str(msg)
    if msg in self.seen:
      return
    self.seen.add(msg)
    if self.ignore_errors:
      warn(msg)
    else:
      raise RuntimeError(msg)

  def clear(self):
    self.seen = set([])
