import logging
import select
import sys
import termios
import tty

from .utils import log_and_print, make_red


class InteractiveMode:
    def __init__(self, cluster_interface, comm_server):
        self.cluster_interface = cluster_interface
        self.comm_server = comm_server
        self.input_to_fn_dict = {
            "list_jobs": self.list_jobs,
            "list_running_jobs": self.list_running_jobs,
            "list_successful_jobs": self.list_successful_jobs,
            "list_idle_jobs": self.list_idle_jobs,
            "show_job": self.show_job,
            "stop_remaining_jobs": self.stop_remaining_jobs,
        }

    def __enter__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
        self.print = print
        tty.setcbreak(sys.stdin.fileno())
        return self.check_for_input

    def __exit__(self, _type, _value, _traceback):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def list_jobs(self):
        self.print("List of all jobs:")
        self.print([job.id for job in self.cluster_interface.jobs])

    def list_running_jobs(self):
        self.print("List of running jobs:")
        self.print([job.id for job in self.cluster_interface.running_jobs])

    def list_successful_jobs(self):
        self.print("List of successful jobs:")
        self.print([job.id for job in self.cluster_interface.successful_jobs])

    def list_idle_jobs(self):
        self.print("List of idle jobs:")
        self.print([job.id for job in self.cluster_interface.idle_jobs])

    def show_job(self):
        try:
            self.print("Enter ID")
            job_id = int(input())
            job = self.cluster_interface.get_job(job_id)
            [self.print(attr, ": ", job.__dict__[attr]) for attr in job.__dict__]
        except Exception:
            self.print("Error encountered, maybe invalid ID?")

    def stop_remaining_jobs(self):
        try:
            self.print(
                make_red("Are you sure you want to stop all remaining jobs? [y/N]")
            )
            jobs_to_cancel = [
                job.id
                for job in self.cluster_interface.jobs
                if job not in self.cluster_interface.successful_jobs
            ]
            self.print(jobs_to_cancel)
            answer = input()
            if answer.lower() in ["y", "yes"]:
                logger = logging.getLogger("cluster_utils")
                logger.info("User manually stopped all remaining jobs.")
                msg = "Job cancelled by cluster utils"
                [
                    self.comm_server.handle_error_encountered((job_id, [msg]))
                    for job_id in jobs_to_cancel
                ]
                log_and_print(logger, "Cancelled all remaining jobs.")
        except Exception:
            self.print("Error encountered")

    def keyboard_input_available(self):
        # checks if theres sth to read from stdin
        return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

    def check_for_input(self):
        if self.keyboard_input_available():
            esc_key_pushed = False
            # check for key push and empty stdin (in case several keys were pushed)
            while self.keyboard_input_available():
                c = sys.stdin.read(1)
                if c == "\x1b":  # x1b is ESC
                    esc_key_pushed = True
            if esc_key_pushed:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
                self.print("\n\n")  # hack to get into right line after tqdms
                self.print(
                    "Enter command, e.g. ", ", ".join(self.input_to_fn_dict.keys())
                )
                self.print(">>>")

                fn_string = input()
                if fn_string in self.input_to_fn_dict:
                    self.input_to_fn_dict[fn_string]()

                tty.setcbreak(sys.stdin.fileno())


class NonInteractiveMode:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return lambda: None

    def __exit__(self, _type, _value, _traceback):
        pass
