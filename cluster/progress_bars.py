import tqdm
from time import sleep
from random import random
from colorama import Fore
from abc import ABC, abstractmethod
from contextlib import contextmanager
import inspect
import sys

@contextmanager
def redirect_stdout_to_tqdm():
    # Store builtin print
    old_print = print

    def str_or_repr(x):
        try:
            return str(x)
        except TypeError:
            return repr(x)

    def new_print(*args, **kwargs):
        to_print = "".join(map(str_or_repr, args))
        tqdm.tqdm.write(to_print,  **kwargs)
    try:
        # Globally replace print with new_print
        inspect.builtins.print = new_print
        yield
    finally:
        inspect.builtins.print = old_print


class ProgressBar(ABC):
    def __init__(self, **kwargs):
        self.tqdm = None
        self.start_tqdm(**kwargs)

    @abstractmethod
    def start_tqdm(self, **kwargs):
        ...

    def update(self, increment):
        self.tqdm.update(increment)

    def close(self):
        self.tqdm.close()


class SubmittedJobsBar(ProgressBar):
    def start_tqdm(self, total_jobs):
        new_rbar = '| {n_fmt}/{total_fmt}'
        bar_format = '{l_bar}%s{bar}%s' % (Fore.RED, Fore.RESET)
        self.tqdm = tqdm.tqdm(desc='Submitted', total=total_jobs, unit='jobs', bar_format=bar_format+new_rbar,dynamic_ncols=True)


class RunningJobsBar(ProgressBar):
    def start_tqdm(self, total_jobs):
        new_rbar = '| {n_fmt}/{total_fmt}'
        bar_format = '{l_bar}%s{bar}%s' % (Fore.YELLOW, Fore.RESET)
        self.tqdm = tqdm.tqdm(desc='Started execution', total=total_jobs, unit='jobs', bar_format=bar_format+new_rbar, dynamic_ncols=True)


class CompletedJobsBar(ProgressBar):
    def start_tqdm(self, total_jobs, maximize):
        new_rbar = ('| {n_fmt}/{total_fmt} [{elapsed}<{remaining}'
                    '{postfix}]')
        bar_format = '{l_bar}%s{bar}%s' % (Fore.GREEN, Fore.RESET)
        self.tqdm = tqdm.tqdm(desc='Completed', total=total_jobs, unit='jobs', bar_format=bar_format+new_rbar, dynamic_ncols=True)
        self.bestval = None
        self.maximize = maximize

    def update_best_val(self, new_val):
        self.bestval = self.bestval or new_val
        if self.maximize:
            self.bestval = max(self.bestval, new_val)
        else:
            self.bestval = min(self.bestval, new_val)

        self.tqdm.set_postfix(best_value=self.bestval)

if __name__ == "__main__":
    total_jobs = 100

    submitted_bar = SubmittedJobsBar(total_jobs=total_jobs)
    running_bar = RunningJobsBar(total_jobs=total_jobs)
    completed_bar = CompletedJobsBar(total_jobs=total_jobs, maximize=True)

    running = 0
    submitted = 0
    completed = 0

    #with redirect_stdout_to_tqdm():
    if True:
        while completed < total_jobs:
            sleep(0.2)
            if submitted < total_jobs:
                submitted += 1
                submitted_bar.update(increment=1)

            if submitted > running and random() > 0.5:
                running += 1
                running_bar.update(increment=1)

            if running > completed and random() > 0.5:
                result = random()
                if result > 0.6:
                    tqdm.tqdm.write(f"Nice new result found {result}")
                completed_bar.update(increment=1)
                completed += 1
                completed_bar.update_best_val(result)

    submitted_bar.close()
    running_bar.close()
    completed_bar.close()
