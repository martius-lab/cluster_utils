import logging
import os
from .cluster_system import ClusterSubmission
from collections import namedtuple
from copy import copy
from subprocess import run, PIPE
from .constants import *
from threading import Thread
import time

CondorRecord = namedtuple('CondorRecord',
                          ['ID', 'owner', 'sub_date', 'sub_time', 'run_time', 'status', 'priority', 'size', 'cmd'])

logger = logging.getLogger('cluster_utils')

class Condor_ClusterSubmission(ClusterSubmission):
    def __init__(self, requirements, paths, remove_jobs_dir=True, iteration_mode=True):
        super().__init__(paths, remove_jobs_dir, iteration_mode)

        os.environ["MPLBACKEND"] = 'agg'
        self._process_requirements(requirements)
        self.exceptions_seen = set({})

    def submit_fn(self, job):
        self.generate_job_spec_file(job)
        submit_cmd = 'condor_submit_bid {} {}\n'.format(self.bid, job.job_spec_file_path)
        result = run([submit_cmd], cwd=str(self.submission_dir), shell=True, stdout=PIPE).stdout.decode('utf-8')
        logger.info(f"Job with id {job.id} submitted.")

        good_lines = [line for line in result.split('\n') if 'submitted' in line]
        bad_lines = [line for line in result.split('\n') if 'WARNING' in line or 'ERROR' in line]
        if not good_lines or bad_lines:
            print(bad_lines)
            self.close()
            raise RuntimeError('Cluster submission failed')
        assert len(good_lines) == 1
        new_cluster_id = good_lines[0].split(' ')[-1][:-1]
        return new_cluster_id

    def stop_fn(self, cluster_id):
        cmd = 'condor_rm {}'.format(cluster_id)
        return run([cmd], shell=True, stderr=PIPE, stdout=PIPE)

    def generate_job_spec_file(self, job):
        job_file_name = 'job_{}_{}.sh'.format(job.iteration, job.id)
        run_script_file_path = os.path.join(self.submission_dir, job_file_name)
        job_spec_file_path = os.path.join(self.submission_dir, job_file_name + '.sub')
        cmd = job.generate_execution_cmd(self.paths)
        # Prepare namespace for string formatting (class vars + locals)
        namespace = copy(vars(self))
        namespace.update(vars(job))
        namespace.update(locals())

        with open(run_script_file_path, 'w') as script_file:
            script_file.write(MPI_CLUSTER_RUN_SCRIPT % namespace)
        os.chmod(run_script_file_path, 0O755)  # Make executable

        with open(job_spec_file_path, 'w') as spec_file:
            spec_file.write(MPI_CLUSTER_JOB_SPEC_FILE % namespace)

        job.job_spec_file_path = job_spec_file_path
        job.run_script_path = run_script_file_path

    def is_blocked(self):
        for job in self.jobs:
            if self.status(job) == 1:
                return True
        return False

    # TODO: Check that two simultaneous HPOs dont collide

    def _process_requirements(self, requirements):
        # Job requirements
        self.mem = requirements['memory_in_mb']
        self.cpus = requirements['request_cpus']
        self.gpus = requirements['request_gpus']
        self.bid = requirements['bid']

        other_requirements = []

        if self.gpus > 0 and requirements['cuda_requirement'] is not None:
            self.cuda_line = 'Requirements=CUDACapability>={}'.format(requirements['cuda_requirement'])
            self.partition = 'gpu'
            self.constraint = 'gpu'
        else:
            self.cuda_line = ''
            self.partition = 'general'
            self.constraint = ''

        if self.gpus > 0 and 'gpu_memory_mb' in requirements:
            other_requirements.append('TARGET.CUDAGlobalMemoryMb>{}'.format(requirements['gpu_memory_mb']))

        def hostnames_to_requirement(hostnames):
            single_reqs = [f'UtsnameNodename =?= \"{hostname}\"' for hostname in hostnames]
            return '(' + ' || '.join(single_reqs) + ')'

        hostname_list = requirements.get('hostname_list', [])
        if hostname_list:
            other_requirements.append(hostnames_to_requirement(hostname_list))

        forbidden_hostnames = requirements.get('forbidden_hostnames', [])
        if forbidden_hostnames:
            single_reqs = [f'UtsnameNodename =!= \"{hostname}\"' for hostname in forbidden_hostnames]
            other_requirements.extend(single_reqs)

        if other_requirements:
            concat_requirements = ' && '.join(other_requirements)
            self.requirements_line = f"requirements={concat_requirements}"
        else:
            self.requirements_line = ''
