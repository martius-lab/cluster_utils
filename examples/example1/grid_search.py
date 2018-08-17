import os
import shutil
from pathlib import Path
import tempfile

from cluster import cluster_run, execute_submission, init_plotting
from cluster.distributions import *
from cluster.report import produce_basic_report
import cluster.git_utils as git_utils

init_plotting()

submission_name = 'test'
home = str(Path.home())
project_path = git_utils.temp_dir() # location of project files (either just some folder, a local git repo or a location
                                  # where the specified git repo will be cloned in)
results_path = os.path.join(home, 'tmp/results') # where results go to
jobs_path = tempfile.mkdtemp() # where job files go to

git_params = dict(url='git@gitlab.tuebingen.mpg.de:mrolinek/cluster_utils.git', # can be url or path to local repo from
                                                                                # which url is retrieved from
                  git_local_path=project_path,
                  branch='git_integration', # checkout specific branch
                  commit=None, # hard reset to specific commit within branch
                  ) # Set to None if not needed

paths_and_files = dict(script_to_run=os.path.join(project_path, 'examples/sbl/main.py'),
                       result_dir=os.path.join(results_path, 'examples/sbl/results', submission_name),
                       jobs_dir=os.path.join(results_path, 'examples/sbl/jobs', submission_name))

submission_requirements = dict(request_cpus=1,
                               request_gpus=0,
                               cuda_requirement=None,  # 'x.0' or None
                               memory_in_mb=4000,
                               bid=10)

other_params = {}

hyperparam_dict = {'u': list(np.linspace(-3.0, 3.0, 3)),
                   'v': list(np.linspace(-3.0, 3.0, 3)),
                   'w': list(np.linspace(-3.0, 3.0, 3)),
                   'x': list(np.linspace(-3.0, 3.0, 3)),
                   'y': list(np.linspace(-3.0, 3.0, 3)),
                   'z': list(np.linspace(-3.0, 3.0, 3)),
                   }

submit = True

all_args = dict(submission_name=submission_name,
                paths=paths_and_files,
                submission_requirements=submission_requirements,
                hyperparam_dict=hyperparam_dict,
                other_params=other_params,
                samples=None,
                restarts_per_setting=1,
                smart_naming=True,
                git_params=git_params
               )

if __name__ == '__main__':
  submission = cluster_run(**all_args)
  if submit:
    df, all_params, metrics, git_meta = execute_submission(submission, paths_and_files['result_dir'])
    df.to_csv(os.path.join(paths_and_files['result_dir'], 'results_raw.csv'))

    relevant_params = list(hyperparam_dict.keys())
    output_pdf = os.path.join(paths_and_files['result_dir'], '{}_report.pdf'.format(submission_name))
    produce_basic_report(df, relevant_params, metrics, git_meta=git_meta, procedure_name=submission_name,
                         output_file=output_pdf)

  # copy this script to the result dir
  my_path = os.path.realpath(__file__)
  shutil.copy(my_path, paths_and_files['result_dir'])
