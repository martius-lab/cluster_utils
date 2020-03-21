import tqdm
from time import sleep
from random import random
from colorama import Fore
from abc import ABC, abstractmethod
from contextlib import contextmanager
import inspect


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
        tqdm.tqdm.write(Fore.RESET + to_print, **kwargs)
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
        self.value = 0

    @abstractmethod
    def start_tqdm(self, **kwargs):
        ...

    def update(self, new_value):
        real_new_value = max(new_value, self.value)  # Negative updates may occur due to instability. This silences the error
        self.tqdm.update(real_new_value - self.value)
        self.value = real_new_value

    def close(self):
        self.tqdm.close()


# Color disabled until a bug in tqdm is fixed.
# see https://stackoverflow.com/questions/58328625/tqdm-colored-progress-bar-printing-on-multiple-lines

class SubmittedJobsBar(ProgressBar):
    def start_tqdm(self, total_jobs):
        new_rbar = '| {n_fmt}/{total_fmt} {postfix}'
        #bar_format = '{l_bar}%s{bar}%s' % (Fore.RED, Fore.RESET)
        bar_format = '{l_bar}{bar}'
        self.tqdm = tqdm.tqdm(desc='Submitted', total=total_jobs, unit='jobs', bar_format=bar_format+new_rbar,dynamic_ncols=True, position=2)

    def update_failed_jobs(self, failed_jobs):
        self.tqdm.set_postfix(Failed=failed_jobs)


class RunningJobsBar(ProgressBar):
    def start_tqdm(self, total_jobs):
        new_rbar = '| {n_fmt}/{total_fmt}'
        #bar_format = '{l_bar}%s{bar}%s' % (Fore.YELLOW, Fore.RESET)
        bar_format = '{l_bar}{bar}'
        self.tqdm = tqdm.tqdm(desc='Started execution', total=total_jobs, unit='jobs', bar_format=bar_format+new_rbar, dynamic_ncols=True, position=1)


class CompletedJobsBar(ProgressBar):
    def start_tqdm(self, total_jobs, minimize):
        new_rbar = ('| {n_fmt}/{total_fmt} [{elapsed}<{remaining}'
                    '{postfix}]')
        #bar_format = '{l_bar}%s{bar}%s' % (Fore.GREEN, Fore.RESET)
        bar_format = '{l_bar}{bar}'
        self.tqdm = tqdm.tqdm(desc='Completed', total=total_jobs, unit='jobs', bar_format=bar_format+new_rbar, dynamic_ncols=True, position=0)
        self.bestval = None
        self.minimize = minimize

    def update_best_val(self, new_val):
        self.bestval = self.bestval or new_val
        if self.minimize:
            self.bestval = min(self.bestval, new_val)
        else:
            self.bestval = max(self.bestval, new_val)

        self.tqdm.set_postfix(best_value=self.bestval)


if __name__ == "__main__":
    with redirect_stdout_to_tqdm():
        total_jobs = 100


        submitted_bar = SubmittedJobsBar(total_jobs=total_jobs)
        running_bar = RunningJobsBar(total_jobs=total_jobs)
        completed_bar = CompletedJobsBar(total_jobs=total_jobs, minimize=False)

        running = 0
        submitted = 0
        completed = 0

        while completed < total_jobs:
            sleep(0.2)
            if submitted < total_jobs:
                submitted += 1


            if submitted > running and random() > 0.5:
                running += 1

            if running > completed and random() > 0.5:
                result = random()
                if result > 0.6:
                        print(f"Nice new result found {result}")
                completed += 1
                completed_bar.update_best_val(result)

            submitted_bar.update(submitted)
            running_bar.update(running)
            completed_bar.update(completed)

        submitted_bar.close()
        running_bar.close()
        completed_bar.close()
