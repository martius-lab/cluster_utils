import logging
import os
import subprocess
from collections import namedtuple
from copy import copy
from subprocess import PIPE, run

from cluster import constants
from cluster.cluster_system import ClusterSubmission

CondorRecord = namedtuple(
    "CondorRecord",
    [
        "ID",
        "owner",
        "sub_date",
        "sub_time",
        "run_time",
        "status",
        "priority",
        "size",
        "cmd",
    ],
)


class CondorClusterSubmission(ClusterSubmission):
    def __init__(self, requirements, paths, remove_jobs_dir=True):
        super().__init__(paths, remove_jobs_dir)

        os.environ["MPLBACKEND"] = "agg"
        self._process_requirements(requirements)
        self.exceptions_seen = set({})

    def submit_fn(self, job):
        logger = logging.getLogger("cluster_utils")
        self.generate_job_spec_file(job)
        submit_cmd = "condor_submit_bid {} {}\n".format(
            self.bid, job.job_spec_file_path
        )
        for try_number in range(10):
            if try_number == 9:
                logging.exception("Job aborted, cluster unstable.")
                raise Exception(
                    "Too many submission timeouts, cluster seems to be too unstable to"
                    " submit jobs"
                )
            try:
                result = run(
                    [submit_cmd],
                    cwd=str(self.submission_dir),
                    shell=True,
                    stdout=PIPE,
                    timeout=15.0,
                )
                submit_output = result.stdout.decode("utf-8")
                break
            except subprocess.TimeoutExpired:
                logger.warning(f"Job submission for id {job.id} hangs. Retrying...")

        good_lines = [line for line in submit_output.split("\n") if "submitted" in line]
        bad_lines = [
            line
            for line in submit_output.split("\n")
            if "WARNING" in line or "ERROR" in line
        ]
        if not good_lines or bad_lines:
            logger.error(
                f"Job with id {job.id} submitted to condor cluster, but job submission"
                f" failed. Submission output:\n{submit_output}"
            )
            print(bad_lines)
            self.close()
            raise RuntimeError("Cluster submission failed")

        assert len(good_lines) == 1
        new_cluster_id = good_lines[0].split(" ")[-1][:-1]
        logger.info(
            f"Job with id {job.id} submitted to condor cluster with cluster id"
            f" {new_cluster_id}."
        )

        return new_cluster_id

    def stop_fn(self, cluster_id):
        cmd = "condor_rm {}".format(cluster_id)
        return run([cmd], shell=True, stderr=PIPE, stdout=PIPE)

    def generate_job_spec_file(self, job):
        job_file_name = "job_{}_{}.sh".format(job.iteration, job.id)
        run_script_file_path = os.path.join(self.submission_dir, job_file_name)
        job_spec_file_path = os.path.join(self.submission_dir, job_file_name + ".sub")
        cmd = job.generate_execution_cmd(self.paths)
        # Prepare namespace for string formatting (class vars + locals)
        namespace = copy(vars(self))
        namespace.update(vars(job))
        namespace.update(locals())

        with open(run_script_file_path, "w") as script_file:
            script_file.write(constants.MPI_CLUSTER_RUN_SCRIPT % namespace)
        os.chmod(run_script_file_path, 0o755)  # Make executable

        with open(job_spec_file_path, "w") as spec_file:
            spec_file.write(constants.MPI_CLUSTER_JOB_SPEC_FILE % namespace)

        job.job_spec_file_path = job_spec_file_path
        job.run_script_path = run_script_file_path

    def is_blocked(self):
        return any(self.status(job) == 1 for job in self.jobs)

    # TODO: Check that two simultaneous HPOs dont collide

    def _process_requirements(self, requirements):
        # Job requirements
        self.mem = requirements["memory_in_mb"]
        self.cpus = requirements["request_cpus"]
        self.gpus = requirements["request_gpus"]
        self.bid = requirements["bid"]

        condor_requirements = []
        if self.gpus > 0:
            self.partition = "gpu"
            self.constraint = "gpu"

            if requirements["cuda_requirement"] is not None:
                cuda_req = requirements["cuda_requirement"]
                try:
                    float(cuda_req)
                    requirement_is_float = True
                except ValueError:
                    requirement_is_float = False

                if cuda_req.startswith("<") or cuda_req.startswith(">"):
                    cuda_line = "TARGET.CUDACapability{}".format(cuda_req)
                elif requirement_is_float:
                    cuda_line = "TARGET.CUDACapability>={}".format(cuda_req)
                else:
                    cuda_line = "{}".format(cuda_req)

                condor_requirements.append(cuda_line)
        else:
            self.partition = "general"
            self.constraint = ""

        if self.gpus > 0 and "gpu_memory_mb" in requirements:
            condor_requirements.append(
                "TARGET.CUDAGlobalMemoryMb>={}".format(requirements["gpu_memory_mb"])
            )

        def hostnames_to_requirement(hostnames):
            single_reqs = [
                f'UtsnameNodename =?= "{hostname}"' for hostname in hostnames
            ]
            return "(" + " || ".join(single_reqs) + ")"

        hostname_list = requirements.get("hostname_list", [])
        if hostname_list:
            condor_requirements.append(hostnames_to_requirement(hostname_list))

        forbidden_hostnames = requirements.get("forbidden_hostnames", [])
        if forbidden_hostnames:
            single_reqs = [
                f'UtsnameNodename =!= "{hostname}"' for hostname in forbidden_hostnames
            ]
            condor_requirements.extend(single_reqs)

        if len(condor_requirements) > 0:
            concat_requirements = " && ".join(condor_requirements)
            self.requirements_line = f"requirements={concat_requirements}"
        else:
            self.requirements_line = ""

        concurrency_limit_tag = requirements.get("concurrency_limit_tag", None)
        concurrency_limit = requirements.get("concurrency_limit", None)

        self.concurrent_line = ""
        if concurrency_limit_tag is not None and concurrency_limit is not None:
            concurrency_limit = (
                constants.MPI_CLUSTER_MAX_NUM_TOKENS // concurrency_limit
            )
            self.concurrent_line = (
                f"concurrency_limits=user.{concurrency_limit_tag}:{concurrency_limit}"
            )

        if "extra_submission_options" in requirements:
            extra_options = requirements["extra_submission_options"]
            if isinstance(extra_options, dict):
                extra_options = [
                    f"{key}={value}" for key, value in extra_options.items()
                ]
            if isinstance(extra_options, list):
                extra_options = "\n".join(extra_options)
            self.extra_submission_lines = f"# Extra options\n{extra_options}"
        else:
            self.extra_submission_lines = ""
