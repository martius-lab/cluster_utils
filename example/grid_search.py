import os
import shutil

from cluster import cluster_run, execute_submission, init_plotting
from cluster.distributions import *
from cluster.report import produce_basic_report

init_plotting()

submission_name = 'test_parallel'
main_path = '/is/sg/mrolinek/Projects/Cluster_utils/example'

paths_and_files = dict(script_to_run=os.path.join(main_path, 'dummy.py'),
                       result_dir=os.path.join(main_path, 'results', 'cluster', submission_name),
                       jobs_dir=os.path.join(main_path, 'jobs', submission_name))

submission_requirements = dict(request_cpus=1,
                               request_gpus=0,
                               cuda_requirement=None,  # 'x.0' or None
                               memory_in_mb=4000,
                               bid=10)

other_params = {}

hyperparam_dict = {'numbers.u': list(np.linspace(-3.0, 3.0, 3)),
                   'numbers.v': list(np.linspace(-3.0, 3.0, 3)),
                   'numbers.w': list(np.linspace(-3.0, 3.0, 3)),
                   'numbers.x': list(np.linspace(-3.0, 3.0, 3)),
                   'numbers.y': list(np.linspace(-3.0, 3.0, 3)),
                   'numbers.z': list(np.linspace(-3.0, 3.0, 3)),
                   }

submit = True

all_args = dict(submission_name=submission_name,
                paths=paths_and_files,
                submission_requirements=submission_requirements,
                hyperparam_dict=hyperparam_dict,
                other_params=other_params,
                samples=None,
                restarts_per_setting=1,
                smart_naming=True)

if __name__ == '__main__':
  submission = cluster_run(**all_args)
  if submit:
    df, all_params, metrics = execute_submission(submission, paths_and_files['result_dir'])
    df.to_csv(os.path.join(paths_and_files['result_dir'], 'results_raw.csv'))

    relevant_params = list(hyperparam_dict.keys())
    output_pdf = os.path.join(paths_and_files['result_dir'], '{}_report.pdf'.format(submission_name))
    produce_basic_report(df, relevant_params, metrics, procedure_name=submission_name,
                         output_file=output_pdf)

  # copy this script to the result dir
  my_path = os.path.realpath(__file__)
  shutil.copy(my_path, paths_and_files['result_dir'])
