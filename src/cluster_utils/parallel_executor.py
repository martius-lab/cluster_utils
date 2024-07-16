import argparse
import concurrent.futures
import os
from multiprocessing import cpu_count
from subprocess import PIPE, run
from time import sleep

defaults = {
    "std_out_file_extension": ".out",
    "std_err_file_extension": ".err",
    "log_file_extension": ".log",
    "log_file_content": "exit code: {}",
}


def execute_parallel_shell_scripts(
    scripts,
    cpus_per_job,
    std_out_file_extension,
    std_err_file_extension,
    log_file_extension,
    log_file_content,
):
    def get_callback_fn(script_name):
        def callback_fn(future):
            out_filename = "{}{}".format(script_name, std_out_file_extension)
            with open(out_filename, "w") as f:
                f.write(future.result().stdout.decode("utf-8"))

            err_filename = "{}{}".format(script_name, std_err_file_extension)
            with open(err_filename, "w") as f:
                f.write(future.result().stderr.decode("utf-8"))

            log_filename = "{}{}".format(script_name, log_file_extension)
            with open(log_filename, "w") as f:
                f.write(log_file_content.format(future.result().returncode))

        return callback_fn

    print("Jobs to execute ", len(scripts))
    num_jobs = len(scripts)
    idle, running = 0, num_jobs

    num_cpus = cpu_count()
    print("Num cpus: ", num_cpus)

    with concurrent.futures.ProcessPoolExecutor(num_cpus // cpus_per_job) as executor:
        futures = [
            executor.submit(run, ["bash", script], stdout=PIPE, stderr=PIPE)
            for script in scripts
        ]
        for future, script_name in zip(futures, scripts):
            future.add_done_callback(get_callback_fn(script_name))
        while idle + running > 0:
            sleep(30)
            running = len([f for f in futures if f.running()])
            done_futures = [f for f in futures if f.done()]
            done_success = len([f for f in done_futures if f.result().returncode == 0])
            done_fail = len(done_futures) - done_success
            idle = num_jobs - running - done_success - done_fail
            info_str = "Done: {}, Running: {}, Idle: {}, Failed: {}"
            print(info_str.format(done_success, running, idle, done_fail))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cpus_per_job", type=int, default=1, help="Number of CPUs per a single job"
    )
    parser.add_argument(
        "--file_with_scripts",
        type=str,
        help="Absolute path to a file containing list of executables to run",
    )
    return parser.parse_args()


if __name__ == "__main__":
    params = parse_args()
    if not os.path.exists(params.file_with_scripts):
        raise FileNotFoundError(
            "File {} does not exist".format(params.file_with_scripts)
        )
    with open(params.file_with_scripts) as f:
        raw_script_names = f.readlines()
    script_names = [name.strip() for name in raw_script_names]
    execute_parallel_shell_scripts(script_names, params.cpus_per_job, **defaults)

# Example call:
# python3 -m cluster_utils.parallel_executor --file_with_scripts=files.txt --cpus_per_job=2
