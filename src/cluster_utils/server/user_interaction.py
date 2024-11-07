from __future__ import annotations

import cmd
import logging
import select
import sys
import termios
import textwrap
import tty

from .utils import log_and_print, make_red


class InteractiveMode(cmd.Cmd):
    intro = textwrap.dedent(
        """
        ============= COMMAND MODE =============
        Type 'help' or '?' to list commands.
        Press enter with empty line to exit command mode.
        """
    )
    prompt = ">>> "

    def __init__(self, cluster_interface, comm_server):
        super().__init__()

        self.cluster_interface = cluster_interface
        self.comm_server = comm_server

    def __enter__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
        self.print = print
        tty.setcbreak(sys.stdin.fileno())
        return self.check_for_input

    def __exit__(self, _type, _value, _traceback):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def do_list_jobs(self, _):
        """List IDs of all jobs that have been submitted so far.

        This includes jobs that have finished already.
        """
        self.print("List of all jobs:")
        self.print([job.id for job in self.cluster_interface.jobs])
        return True

    def do_list_running_jobs(self, _):
        """List IDs of all jobs that are currently running."""
        self.print("List of running jobs:")
        self.print([job.id for job in self.cluster_interface.running_jobs])
        return True

    def do_list_successful_jobs(self, _):
        """List IDs of all jobs that finished successfully."""
        self.print("List of successful jobs:")
        self.print([job.id for job in self.cluster_interface.successful_jobs])
        return True

    def do_list_idle_jobs(self, _):
        """List IDs of all jobs that have been submitted but not yet started."""
        self.print("List of idle jobs:")
        self.print([job.id for job in self.cluster_interface.idle_jobs])

    def do_show_job(self, _):
        "Show information about a specific job."
        return True
        try:
            self.print("Enter ID")
            job_id = int(input())
            job = self.cluster_interface.get_job(job_id)
            [self.print(attr, ": ", job.__dict__[attr]) for attr in job.__dict__]
        except Exception:
            self.print("Error encountered, maybe invalid ID?")
            return False

        return True

    def do_stop_remaining_jobs(self, _):
        """Abort all submitted jobs.

        Abort all currently running jobs as well as jobs that already have been
        submitted but didn't start yet.

        Note: This will currently not stop submission of new jobs.  If you want to stop
        cluster_utils completely, press Ctrl + C instead.
        """
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

        return True

    def emptyline(self):
        # Do not execute a command when pressing enter with empty line.
        # Return True, to exit the command loop.
        return True

    def postcmd(self, stop, line):
        # if command returned True (usually the case if there is no error), exit the
        # command loop
        if stop:
            # print a line to separate command output from progress output
            print("========================================")
            return True

    def keyboard_input_available(self):
        # checks if there is something to read from stdin
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

                self.cmdloop()

                tty.setcbreak(sys.stdin.fileno())


class NonInteractiveMode:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return lambda: None

    def __exit__(self, _type, _value, _traceback):
        pass
