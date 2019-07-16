from concurrent.futures import ThreadPoolExecutor

class JobExecutor():
  def __init__(self):
    self.thread_pool_executor = ThreadPoolExecutor(max_workers=5)

  def submit_job(self, job):
    self.thread_pool_executor.submit(self.submission_fn, job)

  def submission_fn(self, job):
    pass