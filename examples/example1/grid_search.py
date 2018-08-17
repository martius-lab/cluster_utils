import os
import shutil
from pathlib import Path

from cluster import cluster_run, execute_submission, init_plotting
from cluster.distributions import *
from cluster.report import produce_basic_report

init_plotting()

submission_name = 'test'
home = str(Path.home())
git_url = 'git@gitlab.tuebingen.mpg.de:mrolinek/cluster_utils.git' # can be url or path to local git repo
git_local_path = os.path.join(home, 'tmp/repo') # location of local copy
results_path = os.path.join(home, 'tmp/results') # where results go to

git_params = dict(url=git_url,
                  branch='git_integration', # checkout specific branch
                  commit=None, # hard reset to specific commit within branch
                  remove_local_copy=True, # remove local copy after job is done
                  ) # Set to None if not needed

paths_and_files = dict(git_local_path=git_local_path,
                       script_to_run='examples/sbl/main.py', # relative to git_local_path
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
