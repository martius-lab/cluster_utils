import os
import shutil
import cluster
from time import sleep
from cluster.distributions import *
from cluster.analyze_results import *
from subprocess import run

username = 'mrolinek'
opt_procedure_name = 'optimize'

base_paths_and_files = dict(project_dir='/is/sg/mrolinek/Projects/Cluster_utils/example',
                       main_python_script='dummy.py',
                       general_result_dir=os.path.join('results', 'cluster', opt_procedure_name),
                       result_file_name='results.csv',
                       jobs_dir=os.path.join('jobs', opt_procedure_name))

job_requirements = dict(request_cpus=1,
                        request_gpus=0,
                        cuda_requirement=None,  # 'x.0' or None (GPU only)
                        memory_in_mb=4000,
                        bid=10)

metric_to_optimize = 'result'
number_of_samples = 100
number_of_restarts = 1
percentage_that_need_to_finish = 0.9
num_jobs = number_of_samples * number_of_restarts
percentage_of_best = 0.1
total_rounds = 3
check_every_secs = 30


other_params = {'random_param':'yay'}

distribution_list = [TruncatedNormal('num:x', bounds=(-5.0, 5.0), sample_decimals=2),
                     TruncatedNormal('num:y', bounds=(-5.0, 5.0), sample_decimals=2),
                     TruncatedNormal('num:num:z', bounds=(-5.0, 5.0), sample_decimals=2),
                     TruncatedNormal('num:num:w', bounds=(-5.0, 5.0), sample_decimals=2)]


defaults = {'param_file_name': 'param_choice.csv',
            'metric_file': 'metrics.csv',
            'id_columns': ['id', 'model_dir'],
            'save_dir': 'pdf_results',
            }

def produce_all_args(distributions, iteration):
  return dict(job_name='iteration_{}'.format(iteration+1),
                paths=base_paths_and_files,
                job_requirements=job_requirements,
                distribution_list=distributions,
                other_params=other_params,
                samples=number_of_samples,
                restarts_per_setting=number_of_restarts,
                smart_naming=False,
                submit=True)


cdf = None
all_params = [distr.param_name for distr in distribution_list]

for i in range(total_rounds):

  all_args = produce_all_args(distribution_list, i)
  cluster.cluster_run(**all_args)
  print('New jobs submitted! (iteration {})'.format(i+1))

  result_path = os.path.join(base_paths_and_files['general_result_dir'], all_args['job_name'])

  if i > 0:
    print('Last best results:')
    best_df = cdf.best_jobs(metric_to_optimize, 10)[all_params + [metric_to_optimize]]
    print(best_df)

  while True:
    sleep(check_every_secs)
    print('Checking if jobs from iteration {} are finished...'.format(i+1))
    cdf = ClusterDataFrame(result_path, defaults['param_file_name'], defaults['metric_file'])
    if len(cdf.df) >= percentage_that_need_to_finish * num_jobs:
      print('Enough jobs ({}/{}) are finished, proceeding...'.format(len(cdf.df), num_jobs))
      break
    else:
      print('Only {}/{} jobs are finished, waiting further...'.format(len(cdf.df), num_jobs))


  best_params = cdf.best_params(metric_to_optimize, how_many=int(percentage_of_best*number_of_samples))
  print('Best parameters found...')
  print(best_params)

  best_df = cdf.best_jobs(metric_to_optimize, 10)[all_params + [metric_to_optimize]]
  best_df.to_csv(os.path.join(base_paths_and_files['general_result_dir'], 'best_from_iter{}.csv'.format(i+1)))
  for distr in distribution_list:
    distr.fit(best_params[distr.param_name])

  print('Distributions updated...')
  run(['condor_rm', username])
  print('Remaining jobs killed...')
  cluster.rm_dir_full(result_path)
  print('Intermediate results deleted...')

print('Procedure finished')

