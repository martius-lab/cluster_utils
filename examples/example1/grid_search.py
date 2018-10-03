import os
import shutil
from pathlib2 import Path

from cluster import cluster_run, execute_submission, init_plotting
from cluster.distributions import *
from cluster.report import produce_basic_report
from cluster.utils import mkdtemp

home = str(Path.home())

init_plotting()

submission_name = 'test123'
project_path = mkdtemp(suffix=submission_name + '-' + 'project')
results_path = os.path.join(home, 'experiments/results')
jobs_path = mkdtemp(suffix=submission_name + '-' + 'jobs')

git_params = dict(url='git@gitlab.tuebingen.mpg.de:mrolinek/cluster_utils.git',
                  local_path=project_path,
                  branch='master',
                  commit=None,
                  remove_local_copy=True,
                  )

paths_and_files = dict(script_to_run=os.path.join(project_path, 'examples/example1/main.py'),
                       result_dir=os.path.join(results_path, submission_name),
                       jobs_dir=jobs_path)

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
    df, all_params, metrics, submission_hook_stats = execute_submission(submission, paths_and_files['result_dir'])
    df.to_csv(os.path.join(paths_and_files['result_dir'], 'results_raw.csv'))

    relevant_params = list(hyperparam_dict.keys())
    output_pdf = os.path.join(paths_and_files['result_dir'], '{}_report.pdf'.format(submission_name))
    produce_basic_report(df, relevant_params, metrics, submission_hook_stats=submission_hook_stats,
                         procedure_name=submission_name, output_file=output_pdf)

  # copy this script to the result dir
  my_path = os.path.realpath(__file__)
  shutil.copy(my_path, paths_and_files['result_dir'])
