import pathlib
from types import SimpleNamespace

import pytest

from cluster_utils.server.job import Job
from cluster_utils.server.slurm_cluster_system import (
    SBatchArgumentBuilder,
    SlurmClusterSubmission,
    SlurmJobStatus,
    extract_job_status_from_sacct_output,
)


@pytest.fixture()
def job_data(tmp_path: pathlib.Path) -> SimpleNamespace:
    base_requirements = {
        "partition": "part-foo",
        "request_cpus": 10,
        "request_gpus": 2,
        "memory_in_mb": 1000,
        "request_time": "12:34",
    }

    jobs_dir = tmp_path / "jobs_dir"
    jobs_dir.mkdir()
    paths = {
        "main_path": str(tmp_path / "main_path"),
        "script_to_run": "foobar.py",
        "jobs_dir": str(jobs_dir),
        "current_result_dir": str(tmp_path / "current_result_dir"),
    }

    job = Job(
        id=13,
        settings={},
        other_params={},
        paths=paths,
        iteration=2,
        connection_info={"ip": "127.0.0.1", "port": 12345},
        opt_procedure_name="unittest",
        singularity_settings=None,
    )

    return SimpleNamespace(
        requirements=base_requirements,
        paths=paths,
        jobs_dir=jobs_dir,
        job=job,
    )


def test_sbatch_argument_builder():
    args = SBatchArgumentBuilder()
    args.add("foo", "bar")
    args.add("x", 42)
    args.extend_raw(["--extra1", "--extra2=val"])

    expected = """#SBATCH --foo=bar
#SBATCH --x=42
#SBATCH --extra1
#SBATCH --extra2=val"""

    assert args.construct_argument_comment_block() == expected


# Below is one big test, checking the whole run script file with only basic
# requirements, followed by several tests with optional requirements which only check
# that the corresponding argument appears in the file.


def test_generate_run_script(job_data):
    slurm_sub = SlurmClusterSubmission(job_data.requirements, job_data.paths)
    slurm_sub._generate_run_script(job_data.job)
    run_script_path = pathlib.Path(job_data.job.run_script_path)

    expected_path = job_data.jobs_dir / "job_2_13.sh"

    assert job_data.job.run_script_path == str(expected_path)

    job_cmd = job_data.job.generate_execution_cmd(job_data.paths, cmd_prefix="srun")
    run_script = run_script_path.read_text()
    assert (
        run_script
        == f"""#!/bin/bash
#SBATCH --job-name=unittest_13
#SBATCH --output={job_data.jobs_dir}/job_2_13.out
#SBATCH --error={job_data.jobs_dir}/job_2_13.err
#SBATCH --partition=part-foo
#SBATCH --cpus-per-task=10
#SBATCH --gpus-per-task=2
#SBATCH --mem=1000M
#SBATCH --time=12:34
#SBATCH --nodes=1
#SBATCH --ntasks=1

# Submission ID 13

echo "==== Start execution. ===="
echo "Job id: 13, cluster id: ${{SLURM_JOB_ID}}, hostname: $(hostname), time: $(date)"
echo

{job_cmd}
rc=$?

echo "==== Finished execution. ===="
if [[ $rc == 3 ]]; then
    echo "Exit with code 3 for resume"
    # do not forward the exit code, as otherwise Slurm will think there was an error
    exit 0
elif [[ $rc != 0 ]]; then
    echo "Failed with exit code $rc"
    # add an indicator file to more easily identify failed jobs
    echo "$rc" > "{job_data.jobs_dir}/job_2_13.sh.FAILED"
    exit $rc
fi
"""
    )


def test_generate_run_script_exclude_one(job_data):
    job_data.requirements["forbidden_hostnames"] = ["node1"]

    slurm_sub = SlurmClusterSubmission(job_data.requirements, job_data.paths)
    slurm_sub._generate_run_script(job_data.job)
    run_script_path = pathlib.Path(job_data.job.run_script_path)

    run_script_lines = run_script_path.read_text().splitlines(keepends=False)
    assert "#SBATCH --exclude=node1" in run_script_lines


def test_generate_run_script_exclude_many(job_data):
    job_data.requirements["forbidden_hostnames"] = ["node1", "node2", "node3"]

    slurm_sub = SlurmClusterSubmission(job_data.requirements, job_data.paths)
    slurm_sub._generate_run_script(job_data.job)
    run_script_path = pathlib.Path(job_data.job.run_script_path)

    run_script_lines = run_script_path.read_text().splitlines(keepends=False)
    assert "#SBATCH --exclude=node1,node2,node3" in run_script_lines


def test_generate_run_script_exclude_empty(job_data):
    job_data.requirements["forbidden_hostnames"] = []

    slurm_sub = SlurmClusterSubmission(job_data.requirements, job_data.paths)
    slurm_sub._generate_run_script(job_data.job)
    run_script_path = pathlib.Path(job_data.job.run_script_path)

    run_script_text = run_script_path.read_text()
    assert "#SBATCH --exclude=" not in run_script_text


def test_generate_run_script_extra_options(job_data):
    job_data.requirements["extra_submission_options"] = ["--one", "--two=2"]

    slurm_sub = SlurmClusterSubmission(job_data.requirements, job_data.paths)
    slurm_sub._generate_run_script(job_data.job)
    run_script_path = pathlib.Path(job_data.job.run_script_path)

    run_script_lines = run_script_path.read_text().splitlines(keepends=False)
    assert "#SBATCH --one" in run_script_lines
    assert "#SBATCH --two=2" in run_script_lines


def test_extract_job_status_from_sacct_output():
    # Test output below is from actual jobs. Causes for the sacct output below were:
    #
    #   264154: Finished without error
    #   264162: Failed with Python exception
    #   264329: Terminated itself with exit-code 2 (by calling sys.exit(2))
    #   264200: Still running
    #   264226: Terminated by Slurm due to timeout
    #   239026: Killed by unhandled SIGUSR1 (happens when setting --signal=SIG1)
    #   264930: Job that terminated with exit_for_resume()
    #
    # fields are JobID|NodeList|State|ExitCode
    sacct_output = """264154|galvani-cn002|COMPLETED|0:0
264162|galvani-cn002|FAILED|1:0
264329|galvani-cn002|FAILED|2:0
264200|galvani-cn002|RUNNING|0:0
264226|galvani-cn002|TIMEOUT|0:0
239026|galvani-cn002|FAILED|10:0
264930|galvani-cn002|COMPLETED|0:0
"""

    expected_status = {
        "264154": SlurmJobStatus("COMPLETED", 0, "galvani-cn002"),
        "264162": SlurmJobStatus("FAILED", 1, "galvani-cn002"),
        "264329": SlurmJobStatus("FAILED", 2, "galvani-cn002"),
        "264200": SlurmJobStatus("RUNNING", 0, "galvani-cn002"),
        "264226": SlurmJobStatus("TIMEOUT", 0, "galvani-cn002"),
        "239026": SlurmJobStatus("FAILED", 10, "galvani-cn002"),
        "264930": SlurmJobStatus("COMPLETED", 0, "galvani-cn002"),
    }
    expected_status_is_okay = {
        "264154": True,
        "264162": False,
        "264329": False,
        "264200": True,
        "264226": False,
        "239026": False,
        "264930": True,
    }

    actual = extract_job_status_from_sacct_output(sacct_output)

    # first check that statuses are parsed as expected
    assert actual == expected_status

    # ...then check that conclusions drawn from it are correct
    for job_id, expected_is_okay in expected_status_is_okay.items():
        assert actual[job_id].is_okay() == expected_is_okay


def test_extract_job_status_from_sacct_output__including_intermediate_steps():
    # extract_job_status_from_sacct_output() should complain about the *.batch|extern|0
    # lines.
    sacct_output = """4597753|cpu-short|FAILED|1:0
4597753.batch|cpu-short|FAILED|1:0
4597753.extern|cpu-short|COMPLETED|0:0
4597753.0|cpu-short|FAILED|1:0
"""
    with pytest.raises(
        AssertionError,
        match="Unexpected line in sacct output: 4597753.batch|cpu-short|FAILED|1:0",
    ):
        extract_job_status_from_sacct_output(sacct_output)
