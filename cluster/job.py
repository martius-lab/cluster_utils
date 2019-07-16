from concurrent.futures import Future
import os
from copy import copy
from .constants import *
from subprocess import run, PIPE

class Job():
  def __init__(self, execution_cmd, id_number, settings):
    self.execution_cmd = execution_cmd
    self.id_number = id_number
    self.settings = settings
    self.cluster_id = None

  def submit(self, cluster_system, id):
    cmd = self.execution_cmd
    job_file_name = '{}_{}.sh'.format(cluster_system.name, id)
    run_script_file_path = os.path.join(cluster_system.submission_dir, job_file_name)
    job_spec_file_path = os.path.join(cluster_system.submission_dir, job_file_name + '.sub')

    # Prepare namespace for string formatting (class vars + locals)
    namespace = copy(vars(self))
    namespace.update(locals())

    with open(run_script_file_path, 'w') as script_file:
      script_file.write(MPI_CLUSTER_RUN_SCRIPT % namespace)
    os.chmod(run_script_file_path, 0O755)  # Make executable

    with open(job_spec_file_path, 'w') as spec_file:
      spec_file.write(MPI_CLUSTER_JOB_SPEC_FILE % namespace)

    submit_cmd = cluster_system.get_submit_cmd(job_spec_file_path)

    return run([submit_cmd], cwd=str(self.submission_dir), shell=True, stdout=PIPE).stdout.decode('utf-8')

  def close(self, cluster_system):
    if self.cluster_id is None:
      raise RuntimeError('Can not close a job unless its cluster_id got specified')
    run([cluster_system.get_close_cmd(self.cluster_id)], shell=True, stderr=PIPE, stdout=PIPE)

  def running(self):
    pass
