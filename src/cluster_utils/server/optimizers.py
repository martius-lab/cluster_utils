from __future__ import annotations

import logging
import os
import pickle
import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Sequence

import pandas as pd

from cluster_utils.base import constants
from cluster_utils.base.utils import OptionalDependencyImport

from . import data_analysis, distributions
from .utils import get_sample_generator, nested_to_dict

if TYPE_CHECKING:
    from . import latex_utils


class Optimizer(ABC):
    def __init__(
        self,
        *,
        metric_to_optimize: str,
        minimize: bool,
        report_hooks: Sequence[latex_utils.SectionHook],
        number_of_samples: int,
        optimized_params: Sequence[distributions.Distribution],
    ) -> None:
        self.optimized_params = optimized_params
        self.metric_to_optimize = metric_to_optimize
        self.minimize = minimize
        self.report_hooks = report_hooks or []
        self.number_of_samples = number_of_samples
        self.iteration = 0
        # TODO check if obsolete

        self.with_restarts = False

        self.full_df = pd.DataFrame()
        self.minimal_df = pd.DataFrame()
        self.params = [param.param_name for param in self.optimized_params]

    @abstractmethod
    def ask(self):
        """Return parameters for next job."""
        pass

    @abstractmethod
    def tell(self, df, jobs):
        """Add results of finished jobs."""
        for job in jobs:
            job.results_used_for_update = True
        df[constants.ITERATION] = self.iteration + 1

        if self.metric_to_optimize not in df:
            # raise a more understandable error
            raise KeyError(
                "Trying to optimize metric '{}' but it is not provided by the job.".format(
                    self.metric_to_optimize
                )
            )

        self.full_df = pd.concat([self.full_df, df], ignore_index=True, sort=True)
        self.full_df = self.full_df.sort_values(
            [self.metric_to_optimize], ascending=self.minimize
        )

        self.minimal_df = data_analysis.average_out(
            self.full_df,
            [self.metric_to_optimize],
            self.params,
            sort_ascending=self.minimize,
        )

    @abstractmethod
    def try_load_from_pickle(
        self,
        file,
        optimized_params,
        metric_to_optimize,
        minimize,
        report_hooks,
        **optimizer_settings,
    ):
        pass

    def best_jobs_working_dirs(self, how_many):
        logger = logging.getLogger("cluster_utils")
        df_to_use = self.full_df
        if how_many > df_to_use.shape[0]:
            logger.warning(
                "Requesting more best_jobs_working_dirs than data is available, "
                f"reducing number to: {df_to_use.shape[0]}"
            )
            how_many = df_to_use.shape[0]
        df_to_use = df_to_use[["working_dir", self.metric_to_optimize]]
        return data_analysis.best_jobs(
            df_to_use,
            metric=self.metric_to_optimize,
            how_many=how_many,
            minimum=self.minimize,
        )["working_dir"]

    @property
    def minimal_restarts_to_count(self):
        return 1

    def get_best(self, how_many=10):
        if self.iteration > 0:
            df_to_use = self.minimal_df[
                self.minimal_df[constants.RESTART_PARAM_NAME]
                >= self.minimal_restarts_to_count
            ]
            return data_analysis.best_jobs(
                df_to_use,
                metric=self.metric_to_optimize,
                how_many=how_many,
                minimum=self.minimize,
            )
        else:
            return ""


class Metaoptimizer(Optimizer):
    def __init__(self, *, num_jobs_in_elite, with_restarts, **kwargs):
        super().__init__(**kwargs)
        self.num_jobs_in_elite = max(
            5, num_jobs_in_elite
        )  # Force a minimum of 5 jobs in an elite
        self.with_restarts = with_restarts
        self.best_param_values = {}

    @classmethod
    def try_load_from_pickle(
        cls,
        file,
        optimized_params,
        metric_to_optimize,
        minimize,
        report_hooks,
        **optimizer_settings,
    ):
        if not os.path.exists(file):
            return None

        _, with_restarts = optimizer_settings

        with open(file, "rb") as f:
            metaopt = pickle.load(f)
        if (metric_to_optimize, minimize) != (
            metaopt.metric_to_optimize,
            metaopt.minimize,
        ):
            raise ValueError("Attempted to continue but optimizes a different metric!")
        current_best_params = metaopt.get_best_params()
        for distr, _meta_distr in zip(optimized_params, metaopt.optimized_params):
            if distr.param_name in metaopt.params:
                distr.fit(current_best_params[distr.param_name])

        metaopt.optimized_params = optimized_params
        metaopt.with_restarts = with_restarts
        metaopt.params = [distr.param_name for distr in metaopt.optimized_params]
        metaopt.report_hooks = report_hooks or []
        return metaopt

    def ask(self):
        if (
            not self.with_restarts
            or len(self.minimal_df) < self.num_jobs_in_elite
            or random.random() < 0.8
        ):
            return_settings = self.distribution_list_sampler(num_samples=1)
            return list(return_settings)[0]
        else:
            return self.random_setting_to_restart

    def tell(self, jobs):
        iteration_df = None
        if not isinstance(jobs, list):
            jobs = [jobs]
        for job in jobs:
            result = job.get_results()
            if result is not None:
                df, _, _ = result
            if iteration_df is not None:
                iteration_df = pd.concat((iteration_df, df), axis=0, sort=True)
            else:
                iteration_df = df
        if iteration_df is None:
            return
        super().tell(iteration_df, jobs)
        current_best_params = self.get_best_params()
        for distr in self.optimized_params:
            distr.fit(current_best_params[distr.param_name])

    def get_best_params(self):
        return data_analysis.best_params(
            self.minimal_df,
            params=self.params,
            metric=self.metric_to_optimize,
            minimum=self.minimize,
            how_many=self.num_jobs_in_elite,
        )

    @property
    def random_setting_to_restart(self):
        best_ones = self.get_best_params()
        length = min(len(val) for val in best_ones.values())
        random_index = random.choice(range(length // 2))
        nested_items = [
            (key.split("."), val[random_index]) for key, val in best_ones.items()
        ]
        return nested_to_dict(nested_items)

    @property
    def minimal_restarts_to_count(self):
        if self.with_restarts:
            return 1 + (self.iteration // 4)
        else:
            return 1

    def distribution_list_sampler(self, num_samples):
        for distr in self.optimized_params:
            distr.prepare_samples(howmany=num_samples)
        for _ in range(num_samples):
            nested_items = [
                (distr.param_name.split(constants.OBJECT_SEPARATOR), distr.sample())
                for distr in self.optimized_params
            ]
            yield nested_to_dict(nested_items)

    def save_data_and_self(self, directory):
        self.full_df.to_csv(os.path.join(directory, constants.FULL_DF_FILE))
        self.minimal_df.to_csv(os.path.join(directory, constants.REDUCED_DF_FILE))
        self_file = os.path.join(directory, constants.STATUS_PICKLE_FILE)
        with open(self_file, "wb") as f:
            pickle.dump(self, f)


class NGOptimizer(Optimizer):
    @staticmethod
    def get_optimizer_dict():
        # conditional import as it depends on optional dependencies
        with OptionalDependencyImport("nevergrad"):
            import nevergrad as ng

        return {
            "twopointsde": ng.optimizers.TwoPointsDE,
            "oneplusone": ng.optimizers.OnePlusOne,
            "cma": ng.optimizers.CMA,
            "tbpsa": ng.optimizers.TBPSA,
            "pso": ng.optimizers.PSO,
            "randomsearch": ng.optimizers.RandomSearch,
        }

    def __init__(self, *, opt_alg, **kwargs):
        # conditional import as it depends on optional dependencies
        with OptionalDependencyImport("nevergrad"):
            import nevergrad.parametrization.parameter as par

        super().__init__(**kwargs)

        ng_optimizer_dict = self.get_optimizer_dict()
        assert opt_alg in ng_optimizer_dict
        # TODO: Adjust for arbitrary types
        self.instrumentation = {
            param.param_name: self.get_ng_instrumentation(param)
            for param in self.optimized_params
        }
        self.instrumentation = par.Instrumentation(**self.instrumentation)
        self.optimizer = ng_optimizer_dict[opt_alg](
            parametrization=self.instrumentation
        )
        self.with_restarts = False
        self.candidates = {}

    def get_ng_instrumentation(self, param):
        # conditional import as it depends on optional dependencies
        with OptionalDependencyImport("nevergrad"):
            import nevergrad.parametrization.parameter as par

        if type(param) is distributions.TruncatedLogNormal:
            return par.Log(lower=param.lower, upper=param.upper)
        if type(param) is distributions.TruncatedNormal:
            return par.Scalar(lower=param.lower, upper=param.upper)
        if type(param) is distributions.IntLogNormal:
            return par.Log(lower=param.lower, upper=param.upper).set_integer_casting()
        if type(param) is distributions.IntNormal:
            return par.Scalar(
                lower=param.lower, upper=param.upper
            ).set_integer_casting()
        if type(param) is distributions.NumericalDistribution:
            return par.Scalar()
        if type(param) is distributions.Discrete:
            return par.TransitionChoice(param.option_list)
        raise ValueError("Invalid Distribution")

    def ask(self):
        candidate = self.optimizer.ask()
        if -1 in self.candidates:
            raise ValueError("There is already one unassociated candidate!")
        self.candidates[-1] = candidate
        nested_items = [
            (param_name.split(constants.OBJECT_SEPARATOR), value)
            for param_name, value in candidate.kwargs.items()
        ]
        return nested_to_dict(nested_items)

    def add_candidate(self, job_id):
        if -1 not in self.candidates:
            raise ValueError("There is no unassociated candidate!")
        self.candidates[job_id] = self.candidates[-1]
        del self.candidates[-1]

    def tell(self, jobs):
        for job in jobs:
            results = job.get_results()
            if results is not None:
                df, params, metrics = results
            else:
                return
            super().tell(df, jobs)
            if self.minimize:
                self.optimizer.tell(
                    self.candidates[job.id], df.iloc[0][self.metric_to_optimize]
                )
            else:
                self.optimizer.tell(
                    self.candidates[job.id], -df.iloc[0][self.metric_to_optimize]
                )

    def provide_recommendation_settings(self, how_many=1):
        if self.iteration > 0:
            for _ in range(how_many):
                yield self.optimizer.provide_recommendation().kwargs

    @classmethod
    def try_load_from_pickle(
        cls,
        file,
        optimized_params,
        metric_to_optimize,
        minimize,
        report_hooks,
        **optimizer_settings,
    ):
        opt_alg = optimizer_settings["opt_alg"]

        if not os.path.exists(file):
            return None

        with open(file, "rb") as f:
            ngopt = pickle.load(f)
        if (metric_to_optimize, minimize) != (ngopt.metric_to_optimize, ngopt.minimize):
            raise ValueError("Attempted to continue but optimizes a different metric!")

        # hack to circumvent weird type issues with nevergrad optimizers
        ng_optimizer_dict = cls.get_optimizer_dict()
        tmp_optimizer = ng_optimizer_dict[opt_alg](
            instrumentation=ngopt.instrumentation
        )
        assert isinstance(ngopt.optimizer, type(tmp_optimizer))
        ngopt.optimized_params = optimized_params
        ngopt.report_hooks = report_hooks or []
        return ngopt

    def min_fraction_to_finish(self):
        return 0.1

    def save_data_and_self(self, directory):
        self.full_df.to_csv(os.path.join(directory, constants.FULL_DF_FILE))
        self.minimal_df.to_csv(os.path.join(directory, constants.REDUCED_DF_FILE))
        self_file = os.path.join(directory, constants.STATUS_PICKLE_FILE)
        with open(self_file, "wb") as f:
            pickle.dump(self, f)


class GridSearchOptimizer(Optimizer):
    def __init__(self, *, restarts, **kwargs):
        super().__init__(**kwargs)

        def maybe_list_to_tuple(names):
            return tuple(names) if isinstance(names, list) else names

        self.parameter_dicts = {
            maybe_list_to_tuple(param.param_name): param.values
            for param in self.optimized_params
        }
        self.set_setting_generator()
        self.restarts = restarts

    def set_setting_generator(self):
        self.setting_generator = get_sample_generator(
            self.number_of_samples,
            self.parameter_dicts,
            distribution_list=None,
            extra_settings=None,
        )

    def ask(self):
        settings = next(self.setting_generator, None)
        if settings is None:
            self.iteration += 1
            if self.iteration == self.restarts:
                return None
            self.set_setting_generator()
            settings = next(self.setting_generator)
            assert settings is not None
            return settings
        return settings

    def ask_all(self):
        settings = self.ask()
        while settings is not None:
            yield settings
            settings = self.ask()

    def tell(self, df):
        pass

    def get_best(self, how_many=1):
        raise NotImplementedError

    def min_fraction_to_finish(self):
        raise NotImplementedError

    @classmethod
    def try_load_from_pickle(
        cls,
        file,
        optimized_params,
        metric_to_optimize,
        minimize,
        report_hooks,
        **optimizer_settings,
    ):
        return None
