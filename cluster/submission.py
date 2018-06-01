class SubmissionStatus(object):
  def __init__(self, total_jobs, fraction_to_finish, fraction_of_best):

    self.total = total_jobs
    self.fraction_to_finish = fraction_to_finish
    self.fraction_of_best = fraction_of_best

    self.completed = 0
    self.running = 0
    self.idle = total_jobs
    self.held = 0

  @property
  def hopeful_to_finish(self):
    return self.running + self.idle

  @property
  def gone_from_cluster(self):
    return self.total - self.hopeful_to_finish - self.held

  @property
  def no_output(self):
    return max(self.gone_from_cluster - self.completed, 0)

  @property
  def running_after_completion(self):
    return max(self.completed - self.gone_from_cluster, 0)

  @property
  def running_for_print(self):
    return self.running - self.running_after_completion

  @property
  def failed(self):
    return self.held + self.no_output

  @property
  def max_completable(self):
    return self.total - self.failed

  @property
  def total_need_to_finish(self):
    bare_minimum = self.total * self.fraction_of_best
    fraction_of_completable = int(self.fraction_to_finish * self.max_completable)
    return max(bare_minimum, fraction_of_completable)

  @property
  def still_need_to_finish(self):
    return self.total_need_to_finish - self.completed

  @property
  def finished(self):
    return self.completed >= self.total_need_to_finish

  def update(self, completed, cluster_response):
    self.completed = completed
    if cluster_response:
      self.running, self.idle, self.held = cluster_response

  def do_checks(self, error_handler):
    if self.held > 0:
      error_handler.maybe_raise('Some jobs held!')
    if self.no_output > 0:
      error_handler.maybe_raise('Some jobs exited without output!')
    if self.hopeful_to_finish < self.still_need_to_finish:
      raise RuntimeError('Too many jobs failed. Impossible to continue.')

  def __repr__(self):
    return ('Total: {.total}, Completed with output: {.completed}, Failed: {.failed}, '
            'Running: {.running_for_print}, Idle: {.idle}, Still need to finish: {.still_need_to_finish}').format(*(6 * [self]))
