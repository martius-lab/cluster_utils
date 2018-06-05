CLUSTER_PARAM_FILE = 'param_choice.csv'
CLUSTER_METRIC_FILE = 'metrics.csv'
JSON_SETTINGS_FILE = 'settings.json'

STATUS_PICKLE_FILE = 'status.pickle'
FULL_DF_FILE = 'all_data.csv'
REDUCED_DF_FILE = 'reduced_data.csv'
STD_ENDING = '_std'

JSON_FILE_KEY = 'default_json'
OBJECT_SEPARATOR = '.'

PARAM_TYPES = (bool, str, int, float, tuple)

RESERVED_PARAMS = ('model_dir', 'id', 'iteration')

DISTR_BASE_COLORS = [(0.99, 0.7, 0.18), (0.7, 0.7, 0.9), (0.56, 0.692, 0.195), (0.923, 0.386, 0.209)]

MPI_CLUSTER_RUN_SCRIPT = '''
#!/bin/bash
# %(name)s%(id)d

export PATH=${HOME}/bin:/usr/bin:$PATH:/bin
export LD_LIBRARY_PATH=/is/software/nvidia/cuda-9.0/lib64:/is/software/nvidia/cudnn-7.0-cu9.0/lib64:$LD_LIBRARY_PATH
module load cuda/9.0
module load cudnn/7.0-cu9.0
%(cmd)s
rc=$?

if [[ $rc == 0 ]]; then
    rm -f %(run_script_file_path)s
    rm -f %(job_spec_file_path)s
elif [[ $rc == 3 ]]; then
    echo "exit with code 3 for resume"
    exit 3
elif [[ $rc == 1 ]]; then
    exit 1
fi
'''

MPI_CLUSTER_JOB_SPEC_FILE = '''
executable = %(run_script_file_path)s
error = %(run_script_file_path)s.err
output = %(run_script_file_path)s.out
log = %(run_script_file_path)s.log
request_memory=%(mem)s
request_cpus=%(cpus)s
request_gpus=%(gpus)s
%(cuda_line)s
on_exit_hold = (ExitCode =?= 3)
on_exit_hold_reason = "Checkpointed, will resume"
on_exit_hold_subcode = 2
periodic_release = ( (JobStatus =?= 5) && (HoldReasonCode =?= 3) && (HoldReasonSubCode =?= 2) )
queue
'''



SLURM_CLUSTER_JOB_SPEC_FILE = '''#!/bin/bash -l
# Standard output and error:
#SBATCH -o %(run_script_file_path)s.out
#SBATCH -e %(run_script_file_path)s.err
# Initial working directory:
#SBATCH -D ./
# Job Name:
#SBATCH -J %(name)s
# Queue (Partition):
#SBATCH --partition=%(partition)s
# Node feature:
#SBATCH --constraint=%(constraint)s
# Number of nodes and MPI tasks per node:
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=%(cpus)s
#SBATCH --mem=%(mem)s
#
#SBATCH --mail-type=None
#SBATCH --mail-user=your.name@tuebingen.mpg.de
#
# Wall clock limit:
#SBATCH --time=24:00:00

# Run the program:
srun %(run_script_file_path)s > %(run_script_file_path)s.log
'''


SLURM_CLUSTER_RUN_SCRIPT = '''#!/bin/bash -l
%(cuda_line)s
%(cmd)s
'''