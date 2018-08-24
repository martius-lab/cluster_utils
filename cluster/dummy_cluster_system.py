from .cluster_system import ClusterSubmission
from multiprocessing import cpu_count
import concurrent.futures
from subprocess import run, PIPE

class Dummy_ClusterSubmission(ClusterSubmission):
  def __init__(self, job_commands, submission_dir, requirements, name):
    super().__init__()
    self.cmds = job_commands
    self.submission_dir = submission_dir
    self._process_requirements(requirements)
    self.name = name
    self.exceptions_seen = set({})

    self.submission_cmds = ['Submitted dummy job number {}'.format(i) for i in range(len(list(job_commands)))]

  @property
  def total_jobs(self):
    return len(self.submission_cmds)

  def _process_requirements(self, requirements):
    # Job requirements
    pass

  def submit(self):
    if self.submitted:
      raise RuntimeError('Attempt for second submission!')
    self.submitted = True
    for submit_cmd in self.submission_cmds:
      print(submit_cmd)
    print('Jobs submitted successfully. This is not doing anything yet, sorry')

  def close(self):
    print('Killing remaining jobs...')
    if not self.submitted:
      raise RuntimeError('Submission cleanup called before submission completed')
    print('Remaining jobs killed')
    self.finished = True
    super().close()

  def get_status(self):
    return 42, 42, 42

  def check_error_msgs(self):
    found_err = False
    return found_err
