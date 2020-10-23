import datetime
import itertools
import logging
import os
import random
from abc import ABC, abstractmethod
from tempfile import TemporaryDirectory

import cloudpickle as pickle
import nevergrad as ng
import numpy as np
import pandas as pd

from cluster import constants, data_analysis, distributions
from cluster.latex_utils import LatexFile
from cluster.utils import get_sample_generator, nested_to_dict, shorten_string


class Optimizer(ABC):
    def __init__(self, *, metric_to_optimize, minimize, report_hooks, number_of_samples,
                 optimized_params):
        self.optimized_params = optimized_params
        self.metric_to_optimize = metric_to_optimize
        self.minimize = minimize
        self.report_hooks = report_hooks or []
        self.number_of_samples = number_of_samples
        self.iteration = 0
        # TODO check if obsolete

        self.full_df = pd.DataFrame()
        self.minimal_df = pd.DataFrame()
        self.params = [param.param_name for param in self.optimized_params]

    @abstractmethod
    def ask(self):
        pass

    @abstractmethod
    def tell(self, df, jobs):
        for job in jobs:
            job.results_used_for_update = True
        df[constants.ITERATION] = self.iteration + 1

        self.full_df = pd.concat([self.full_df, df], ignore_index=True, sort=True)
        self.full_df = self.full_df.sort_values([self.metric_to_optimize], ascending=self.minimize)

        self.minimal_df = data_analysis.average_out(self.full_df, [self.metric_to_optimize], self.params)
        self.minimal_df = self.minimal_df.sort_values([self.metric_to_optimize], ascending=self.minimize)

    @abstractmethod
    def get_best(self, how_many=1):
        pass

    @abstractmethod
    def try_load_from_pickle(cls):
        pass

    def save_pdf_report(self, output_file, submission_hook_stats, current_result_path):
        today = datetime.datetime.now().strftime("%B %d, %Y")
        latex_title = 'Results of optimization procedure from ({})'.format(today)
        latex = LatexFile(latex_title)

        if 'GitConnector' in submission_hook_stats and submission_hook_stats['GitConnector']:
            latex.add_generic_section('Git Meta Information', content=submission_hook_stats['GitConnector'])

        def filename_gen(base_path):
            for num in itertools.count():
                yield os.path.join(base_path, '{}.pdf'.format(num))

        with TemporaryDirectory() as tmpdir:
            file_gen = filename_gen(tmpdir)
            hook_args = dict(df=self.full_df,
                             path_to_results=current_result_path)
            overall_progress_file = next(file_gen)
            data_analysis.plot_opt_progress(self.full_df, self.metric_to_optimize, overall_progress_file)

            sensitivity_file = next(file_gen)
            data_analysis.importance_by_iteration_plot(self.full_df, self.params, self.metric_to_optimize,
                                                       self.minimize, sensitivity_file)

            distr_plot_files = self.distribution_plots(file_gen)

            latex.add_section_from_figures('Overall progress', [overall_progress_file], common_scale=1.2)
            latex.add_section_from_dataframe('Top 5 recommendations', self.provide_recommendations(5))
            latex.add_section_from_figures('Hyperparameter importance', [sensitivity_file])
            latex.add_section_from_figures('Distribution development', distr_plot_files)

            for hook in self.report_hooks:
                hook.write_section(latex, file_gen, hook_args)
            latex.produce_pdf(output_file)

    def distribution_plots(self, filename_generator):
        for distr in self.optimized_params:
            filename = next(filename_generator)
            if isinstance(distr, distributions.NumericalDistribution):
                log_scale = isinstance(distr, distributions.TruncatedLogNormal)
                res = data_analysis.distribution(self.full_df, constants.ITERATION, distr.param_name,
                                                 filename=filename, metric_logscale=log_scale,
                                                 x_bounds=(distr.lower, distr.upper))
                if res:
                    yield filename
            elif isinstance(distr, distributions.Discrete):
                data_analysis.count_plot_horizontal(self.full_df, constants.ITERATION, distr.param_name, filename=filename)
                yield filename
            else:
                assert False

    @abstractmethod
    def try_load_from_pickle(cls, file, optimized_params, metric_to_optimize, minimize, report_hooks,
                             **optimizer_settings):
        pass

    def best_jobs_working_dirs(self, how_many):
        logger = logging.getLogger('cluster_utils')
        df_to_use = self.full_df
        if how_many > df_to_use.shape[0]:
            logger.warning('Requesting more best_jobs_working_dirs than data is available, reducing number to: ' +
                 str(df_to_use.shape[0]))
            how_many = df_to_use.shape[0]
        df_to_use = df_to_use[['working_dir', self.metric_to_optimize]]
        return data_analysis.best_jobs(df_to_use, metric=self.metric_to_optimize,
                                       how_many=how_many, minimum=self.minimize)['working_dir']

    @property
    def minimal_restarts_to_count(self):
        return 1

    def get_best(self, how_many=10):
        if self.iteration > 0:
            df_to_use = self.minimal_df[self.minimal_df[constants.RESTART_PARAM_NAME] >= self.minimal_restarts_to_count]
            return data_analysis.best_jobs(df_to_use, metric=self.metric_to_optimize,
                                           how_many=how_many, minimum=self.minimize)
        else:
            return ''

    def provide_recommendations(self, how_many):
        jobs_df = self.minimal_df[self.minimal_df[constants.RESTART_PARAM_NAME] >= self.minimal_restarts_to_count].copy()

        metric_std = self.metric_to_optimize + constants.STD_ENDING
        final_metric = f'expected {self.metric_to_optimize}'
        if self.with_restarts and self.minimal_restarts_to_count > 1:
            sign = -1.0 if self.minimize else 1.0
            mean, std = jobs_df[self.metric_to_optimize], jobs_df[metric_std]
            median_std = jobs_df[metric_std].median()

            # pessimistic estimate mean - std/sqrt(samples), based on Central Limit Theorem
            expected_metric = mean - (sign * (np.maximum(std, median_std)) / np.sqrt(jobs_df[constants.RESTART_PARAM_NAME]))
            jobs_df[final_metric] = expected_metric
        else:
            jobs_df[final_metric] = jobs_df[self.metric_to_optimize]

        best_jobs_df = jobs_df.sort_values([final_metric], ascending=self.minimize)[:how_many].reset_index()
        del best_jobs_df[metric_std]
        del best_jobs_df[self.metric_to_optimize]
        del best_jobs_df[constants.RESTART_PARAM_NAME]
        del best_jobs_df['index']

        best_jobs_df.index += 1
        best_jobs_df[final_metric] = list(distributions.smart_round(best_jobs_df[final_metric]))

        best_jobs_df = best_jobs_df.transpose()
        best_jobs_df.index = [shorten_string(el, 40) for el in best_jobs_df.index]
        return best_jobs_df


class Metaoptimizer(Optimizer):
    def __init__(self, *, num_jobs_in_elite, with_restarts, **kwargs):
        super().__init__(**kwargs)
        self.num_jobs_in_elite = max(5, num_jobs_in_elite)  # Force a minimum of 5 jobs in an elite
        self.with_restarts = with_restarts
        self.best_param_values = {}

    @classmethod
    def try_load_from_pickle(cls, file, optimized_params, metric_to_optimize, minimize,
                             report_hooks, **optimizer_settings):

        if not os.path.exists(file):
            return None

        _, with_restarts = optimizer_settings

        metaopt = pickle.load(open(file, 'rb'))
        if (metric_to_optimize, minimize) != (metaopt.metric_to_optimize, metaopt.minimize):
            raise ValueError('Attempted to continue but optimizes a different metric!')
        current_best_params = metaopt.get_best_params()
        for distr, meta_distr in zip(optimized_params, metaopt.optimized_params):
            if distr.param_name in metaopt.params:
                distr.fit(current_best_params[distr.param_name])

        metaopt.optimized_params = optimized_params
        setattr(metaopt, 'with_restarts', with_restarts)
        metaopt.params = [distr.param_name for distr in metaopt.optimized_params]
        metaopt.report_hooks = report_hooks or []
        return metaopt

    def ask(self):
        if not self.with_restarts or len(self.minimal_df) < self.num_jobs_in_elite or random.random() < 0.8:
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
        return data_analysis.best_params(self.minimal_df, params=self.params, metric=self.metric_to_optimize,
                                         minimum=self.minimize, how_many=self.num_jobs_in_elite)

    @property
    def random_setting_to_restart(self):
        best_ones = self.get_best_params()
        length = min(len(val) for val in best_ones.values())
        random_index = random.choice(range(length // 2))
        nested_items = [(key.split('.'), val[random_index]) for key, val in best_ones.items()]
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
        for i in range(num_samples):
            nested_items = [(distr.param_name.split(constants.OBJECT_SEPARATOR), distr.sample())
                            for distr in self.optimized_params]
            yield nested_to_dict(nested_items)

    def save_data_and_self(self, directory):
        self.full_df.to_csv(os.path.join(directory, constants.FULL_DF_FILE))
        self.minimal_df.to_csv(os.path.join(directory, constants.REDUCED_DF_FILE))
        self_file = os.path.join(directory, constants.STATUS_PICKLE_FILE)
        with open(self_file, 'wb') as f:
            pickle.dump(self, f)


ng_optimizer_dict = {'twopointsde': ng.optimizers.TwoPointsDE,
                     'oneplusone': ng.optimizers.OnePlusOne,
                     'cma': ng.optimizers.CMA,
                     'tbpsa': ng.optimizers.TBPSA,
                     'pso': ng.optimizers.PSO,
                     'randomsearch': ng.optimizers.RandomSearch}


class NGOptimizer(Optimizer):
    def __init__(self, *, opt_alg, **kwargs):
        super().__init__(**kwargs)
        assert opt_alg in ng_optimizer_dict.keys()
        # TODO: Adjust for arbitrary types
        self.instrumentation = {param.param_name: self.get_ng_instrumentation(param) for
                                param in self.optimized_params}
        self.instrumentation = ng.Instrumentation(**self.instrumentation)
        self.optimizer = ng_optimizer_dict[opt_alg](instrumentation=self.instrumentation)
        self.with_restarts = False
        self.candidates = {}

    def get_ng_instrumentation(self, param):
        if type(param) == distributions.TruncatedLogNormal:
            return ng.var.Log(param.lower, param.upper, width=2.0)
        if type(param) == distributions.TruncatedNormal:
            return ng.var.Scalar().bounded(param.lower, param.upper)
        if type(param) == distributions.IntLogNormal:
            return ng.var.Log(param.lower, param.upper, width=2.0, dtype=int)
        if type(param) == distributions.IntNormal:
            return ng.var.Scalar(int).bounded(param.lower, param.upper)
        if type(param) == distributions.NumericalDistribution:
            return ng.var.Scalar()
        if type(param) == distributions.Discrete:
            return ng.var.OrderedDiscrete(param.option_list)
        raise ValueError('Invalid Distribution')

    def ask(self):
        candidate = self.optimizer.ask()
        if -1 in self.candidates.keys():
            raise ValueError("There is already one unassociated candidate!")
        self.candidates[-1] = candidate
        nested_items = [(param_name.split(constants.OBJECT_SEPARATOR), value)
                        for param_name, value in candidate.kwargs.items()]
        return nested_to_dict(nested_items)

    def add_candidate(self, job_id):
        if not -1 in self.candidates.keys():
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
                self.optimizer.tell(self.candidates[job.id], df.iloc[0][self.metric_to_optimize])
            else:
                self.optimizer.tell(self.candidates[job.id], -df.iloc[0][self.metric_to_optimize])

    def provide_recommendation_settings(self, how_many=1):
        if self.iteration > 0:
            for _ in range(how_many):
                yield self.optimizer.provide_recommendation().kwargs

    @classmethod
    def try_load_from_pickle(cls, file, optimized_params, metric_to_optimize, minimize, report_hooks,
                             **optimizer_settings):
        opt_alg = optimizer_settings['opt_alg']

        if not os.path.exists(file):
            return None

        ngopt = pickle.load(open(file, 'rb'))
        if (metric_to_optimize, minimize) != (ngopt.metric_to_optimize, ngopt.minimize):
            raise ValueError('Attempted to continue but optimizes a different metric!')

        # hack to circumvent weird type issues with nevergrad optimizers
        tmp_optimizer = ng_optimizer_dict[opt_alg](instrumentation=ngopt.instrumentation)
        assert isinstance(ngopt.optimizer, type(tmp_optimizer))
        ngopt.optimized_params = optimized_params
        ngopt.report_hooks = report_hooks or []
        return ngopt

    def min_fraction_to_finish(self):
        return .1

    def save_data_and_self(self, directory):
        self.full_df.to_csv(os.path.join(directory, constants.FULL_DF_FILE))
        self.minimal_df.to_csv(os.path.join(directory, constants.REDUCED_DF_FILE))
        self_file = os.path.join(directory, constants.STATUS_PICKLE_FILE)
        with open(self_file, 'wb') as f:
            pickle.dump(self, f)


class GridSearchOptimizer(Optimizer):
    def __init__(self, *, restarts, **kwargs):
        super().__init__(**kwargs)
        def maybe_list_to_tuple(names):
            return tuple(names) if isinstance(names, list) else names
        self.parameter_dicts = {maybe_list_to_tuple(param.param_name): param.values for param in self.optimized_params}
        self.set_setting_generator()
        self.restarts = restarts

    def set_setting_generator(self):
        self.setting_generator = get_sample_generator(self.number_of_samples, self.parameter_dicts, distribution_list=None,
                                                      extra_settings=None)

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
    def try_load_from_pickle(cls, file, optimized_params, metric_to_optimize, minimize, report_hooks,
                             **optimizer_settings):
        return None
