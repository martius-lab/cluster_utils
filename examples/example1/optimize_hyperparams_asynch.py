import os
from pathlib2 import Path

from cluster import asynchronous_optimization, init_plotting
from cluster.distributions import *
from cluster.latex_utils import *
from cluster.utils import mkdtemp

home = str(Path.home())

init_plotting()

opt_procedure_name = 'dummy2_ng'

optimizer_str = 'ng'
optimizer_settings = {'opt_alg': 'cma'}

project_path = mkdtemp(suffix=opt_procedure_name + '-' + 'project')
results_path = os.path.join(home, 'experiments/results')
jobs_path = mkdtemp(suffix=opt_procedure_name + '-' + 'jobs')

git_params = dict(url='git@gitlab.tuebingen.mpg.de:mrolinek/cluster_utils.git',
                  local_path=project_path,
                  branch='new_plots',
                  )

base_paths_and_files = dict(script_to_run=os.path.join(project_path, 'examples/example1/main.py'),
                            result_dir=os.path.join(results_path, opt_procedure_name),
                            jobs_dir=jobs_path)

submission_requirements = dict(request_cpus=1,
                               request_gpus=0,
                               cuda_requirement=None,  # 'x.0' or None (GPU only)
                               memory_in_mb=4000,
                               bid=10)

optimization_setting = dict(metric_to_optimize='result',
                            number_of_samples=10,
                            min_n_jobs=2,
                            minimize=True)

other_params = {'flag': False}

optimized_params = [NGVariable(param='u'),
                    NGVariable(param='v'),
                    NGVariable(param='w'),
                    NGVariable(param='x'),
                    NGVariable(param='y'),
                    NGVariable(param='z')]

def find_json(df, path_to_results, filename_generator):
    return '/is/sg/mrolinek/Projects/mbrl/optimization_scripts/gym/halfcheetah/mpc_opt_script.json'



#json_hook = SectionFromJsonHook(section_title='Random script', section_generator=find_json)
asynchronous_optimization(base_paths_and_files=base_paths_and_files,
                            submission_requirements=submission_requirements,
                            optimizer_str=optimizer_str,
                            optimizer_settings=optimizer_settings,
                            optimized_params=optimized_params,
                            other_params=other_params,
                            git_params=git_params,
                            num_best_jobs_whose_data_is_kept=5,
                            report_hooks=None,
                            run_local=True,
                            **optimization_setting)
