import datetime
import os
import cloudpickle as pickle
from itertools import count
from tempfile import TemporaryDirectory
from abc import ABC, abstractmethod
import itertools
from .data_analysis import *
from .distributions import *
from .latex_utils import LatexFile
from .utils import nested_to_dict, shorten_string, get_sample_generator
import nevergrad as ng


class Optimizer(ABC):
  def __init__(self, *, metric_to_optimize, minimize, report_hooks, number_of_samples, iteration_mode,
               optimized_params):
    self.optimized_params = optimized_params
    self.metric_to_optimize = metric_to_optimize
    self.minimize = minimize
    self.report_hooks = report_hooks or []
    self.number_of_samples = number_of_samples
    self.iteration_mode = iteration_mode
    #TODO check if obsolete
    if self.iteration_mode:
      self.iteration = 0
    self.full_df = pd.DataFrame()
    self.minimal_df = pd.DataFrame()
    self.params = [param.param_name for param in self.optimized_params]

  @abstractmethod
  def ask(self, num_samples):
    raise NotImplementedError

  @abstractmethod
  def tell(self, df, jobs):
    for job in jobs:
      job.results_used_for_update = True
    df['iteration'] = self.iteration + 1

    self.full_df = pd.concat([self.full_df, df], ignore_index=True)
    self.full_df = self.full_df.sort_values([self.metric_to_optimize], ascending=self.minimize)

    self.minimal_df = average_out(self.full_df, [self.metric_to_optimize], self.params)
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
      for num in count():
        yield os.path.join(base_path, '{}.pdf'.format(num))

    with TemporaryDirectory() as tmpdir:
      file_gen = filename_gen(tmpdir)
      hook_args = dict(df=self.full_df,
                       path_to_results=current_result_path)
      overall_progress_file = next(file_gen)
      plot_opt_progress(self.full_df, self.metric_to_optimize, overall_progress_file)

      sensitivity_file = next(file_gen)
      importance_by_iteration_plot(self.full_df, self.params, self.metric_to_optimize, self.minimize,
                                   sensitivity_file)

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
      if isinstance(distr, NumericalDistribution):
        log_scale = isinstance(distr, TruncatedLogNormal)
        res = distribution(self.full_df, 'iteration', distr.param_name,
                           filename=filename, metric_logscale=log_scale,
                           transition_colors=True, x_bounds=(distr.lower, distr.upper))
        if res:
          yield filename
      elif isinstance(distr, Discrete):
        count_plot_horizontal(self.full_df, 'iteration', distr.param_name, filename=filename)
        yield filename
      else:
        assert False


  @abstractmethod
  def min_fraction_to_finish(self):
    pass

  @abstractmethod
  def try_load_from_pickle(cls, file, optimized_params, metric_to_optimize, minimize, report_hooks,
                           **optimizer_settings):
    pass

  def best_jobs_model_dirs(self, how_many):
    df_to_use = self.full_df
    if how_many > df_to_use.shape[0]:
      warn('Requesting more best_job_model_dirs than data is available, reducing number to: ' + str(df_to_use.shape[0]))
      how_many = df_to_use.shape[0]
    df_to_use = df_to_use[['model_dir', self.metric_to_optimize]]
    return best_jobs(df_to_use, metric=self.metric_to_optimize, how_many=how_many, minimum=self.minimize)['model_dir']

  @property
  def minimal_restarts_to_count(self):
    return 1

  def get_best(self, how_many=10):
    if self.iteration > 0:
      df_to_use = self.minimal_df[self.minimal_df[RESTART_PARAM_NAME] >= self.minimal_restarts_to_count]
      return best_jobs(df_to_use, metric=self.metric_to_optimize, how_many=how_many, minimum=self.minimize)
    else:
      return ''

  def provide_recommendations(self, how_many):
    jobs_df = self.minimal_df[self.minimal_df[RESTART_PARAM_NAME] >= self.minimal_restarts_to_count].copy()

    metric_std = self.metric_to_optimize + STD_ENDING
    final_metric = f'expected {self.metric_to_optimize}'
    if self.with_restarts and self.minimal_restarts_to_count > 1:
      sign = -1.0 if self.minimize else 1.0
      mean, std = jobs_df[self.metric_to_optimize], jobs_df[metric_std]
      median_std = jobs_df[metric_std].median()
      print('Median noise noise over restarts', median_std)

      # pessimistic estimate mean - std/sqrt(samples), based on Central Limit Theorem
      expected_metric = mean - (sign * (np.maximum(std, median_std)) / np.sqrt(jobs_df[RESTART_PARAM_NAME]))
      jobs_df[final_metric] = expected_metric
    else:
      jobs_df[final_metric] = jobs_df[self.metric_to_optimize]

    best_jobs_df = jobs_df.sort_values([final_metric], ascending=self.minimize)[:how_many].reset_index()
    del best_jobs_df[metric_std]
    del best_jobs_df[self.metric_to_optimize]
    del best_jobs_df[RESTART_PARAM_NAME]
    del best_jobs_df['index']

    best_jobs_df.index += 1
    best_jobs_df[final_metric] = list(smart_round(best_jobs_df[final_metric]))

    best_jobs_df = best_jobs_df.transpose()
    best_jobs_df.index = [shorten_string(el, 40) for el in best_jobs_df.index]
    return best_jobs_df


class Metaoptimizer(Optimizer):
  def __init__(self, *, best_fraction_to_use_for_update, with_restarts, iteration_mode=True, **kwargs):
    super().__init__(iteration_mode=iteration_mode, **kwargs)
    self.best_fraction_to_use_for_update = best_fraction_to_use_for_update
    self.update_best_jobs_to_take()
    self.with_restarts = with_restarts
    self.best_param_values = {}

  @classmethod
  def try_load_from_pickle(cls, file, optimized_params, metric_to_optimize, minimize,
                           report_hooks, **optimizer_settings):

    if not os.path.exists(file):
      return None

    best_fraction_to_use_for_update, with_restarts = optimizer_settings

    metaopt = pickle.load(open(file, 'rb'))
    if (metric_to_optimize, minimize) != (metaopt.metric_to_optimize, metaopt.minimize):
      raise ValueError('Attempted to continue but optimizes a different metric!')
    current_best_params = metaopt.get_best_params()
    for distr, meta_distr in zip(optimized_params, metaopt.optimized_params):
      if distr.param_name in metaopt.params:
        distr.fit(current_best_params[distr.param_name])

    metaopt.update_best_jobs_to_take()
    metaopt.optimized_params = optimized_params
    setattr(metaopt, 'with_restarts', with_restarts)
    metaopt.params = [distr.param_name for distr in metaopt.optimized_params]
    metaopt.report_hooks = report_hooks or []
    if not metaopt is None:
      print('Loaded HP optimizer from pickle!')
    return metaopt

  def update_best_jobs_to_take(self):
    if not self.iteration_mode:
      best_jobs_to_take = int(self.full_df.shape[0] * self.best_fraction_to_use_for_update)
    else:
      best_jobs_to_take = int(self.number_of_samples * self.best_fraction_to_use_for_update)
    if best_jobs_to_take < 10:
      warn('Less than 10 jobs would be taken for distribution update. '
           'Resorting to taking exactly 10 best jobs. '
           'Perhaps choose higher \'best_fraction_to_use_for_update\' ')
      best_jobs_to_take = 10
    self.best_jobs_to_take = best_jobs_to_take

  def ask(self, num_samples):
    if self.iteration_mode:
      extra_settings = self.settings_to_restart
      if extra_settings is not None:
        num_samples = num_samples - self.best_jobs_to_take
        sampled_settings = self.distribution_list_sampler(num_samples)
        return_settings = itertools.chain(extra_settings, sampled_settings)
      else:
        sampled_settings = self.distribution_list_sampler(num_samples)
        return_settings = sampled_settings
    else:
        return_settings = self.distribution_list_sampler(num_samples)
    for setting in return_settings:
      yield None, setting

  def tell(self, jobs):
    iteration_df = None
    if not isinstance(jobs, list):
      jobs = [jobs]
    for job in jobs:
      result = job.get_results()
      if result is not None:
        df, _, _ = result
      if iteration_df is not None:
        iteration_df = pd.concat((iteration_df, df), axis=0)
      else:
        iteration_df = df
    if iteration_df is None:
      return
    super().tell(iteration_df, jobs)
    current_best_params = self.get_best_params()
    for distr in self.optimized_params:
      distr.fit(current_best_params[distr.param_name])

  def get_best_params(self):
    self.update_best_jobs_to_take()
    return best_params(self.minimal_df, params=self.params, metric=self.metric_to_optimize,
                       minimum=self.minimize, how_many=self.best_jobs_to_take)

  @property
  def settings_to_restart(self):
    if not self.with_restarts:
      return None
    if not len(self.minimal_df):
      return None

    best_ones = self.get_best_params()
    repeats = 1 + self.iteration // 4

    def restart_setting_generator():
      length = min(len(val) for val in best_ones.values())
      job_budget = self.best_jobs_to_take
      for i in range(length):
        nested_items = [(key.split('.'), val[i]) for key, val in best_ones.items()]
        for j in range(repeats):
          job_budget = job_budget - 1
          to_restart = nested_to_dict(nested_items)
          yield to_restart
          if job_budget == 0:
            return

    return restart_setting_generator()

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
      nested_items = [(distr.param_name.split(OBJECT_SEPARATOR), distr.sample()) for distr in self.optimized_params]
      yield nested_to_dict(nested_items)

  def min_fraction_to_finish(self):
    return self.best_fraction_to_use_for_update

  def save_data_and_self(self, directory):
    self.full_df.to_csv(os.path.join(directory, FULL_DF_FILE))
    self.minimal_df.to_csv(os.path.join(directory, REDUCED_DF_FILE))
    self_file = os.path.join(directory, STATUS_PICKLE_FILE)
    with open(self_file, 'wb') as f:
      pickle.dump(self, f)


ng_optimizer_dict = {'twopointsde': ng.optimizers.TwoPointsDE,
                     'oneplusone': ng.optimizers.OnePlusOne,
                     'cma': ng.optimizers.CMA,
                     'tbpsa': ng.optimizers.TBPSA,
                     'pso': ng.optimizers.PSO,
                     'randomsearch': ng.optimizers.RandomSearch}


class NGOptimizer(Optimizer):
  def __init__(self, *, opt_alg, iteration_mode=True, **kwargs):
    super().__init__(iteration_mode=iteration_mode, **kwargs)
    assert opt_alg in ng_optimizer_dict.keys()
    # TODO: Adjust for arbitrary types
    self.instrumentation = {param.param_name: self.get_ng_instrumentation(param) for
                            param in self.optimized_params}
    self.instrumentation = ng.Instrumentation(**self.instrumentation)
    self.optimizer = ng_optimizer_dict[opt_alg](instrumentation=self.instrumentation)
    self.with_restarts = False

  def get_ng_instrumentation(self, param):
    if type(param) == TruncatedLogNormal:
      return ng.var.Log(param.lower, param.upper, width=2.0)
    if type(param) == TruncatedNormal:
      return ng.var.Scalar().bounded(param.lower, param.upper)
    if type(param) == IntLogNormal:
      return ng.var.Log(param.lower, param.upper, width=2.0, dtype=int)
    if type(param) == IntNormal:
      return ng.var.Scalar(int).bounded(param.lower, param.upper)
    if type(param) == NumericalDistribution:
      return ng.var.Scalar()
    if type(param) == Discrete:
      return ng.var.OrderedDiscrete(param.option_list)
    raise ValueError('Invalid Distribution')

  def ask(self, num_samples):
    for _ in range(num_samples):
      candidate = self.optimizer.ask()
      nested_items = [(param_name.split(OBJECT_SEPARATOR), value) for param_name, value in candidate.kwargs.items()]
      yield candidate, nested_to_dict(nested_items)

  def tell(self, jobs):
    for job in jobs:
      results = job.get_results()
      if results is not None:
        df, params, metrics = results
      else:
        return
      super().tell(df, jobs)
      if self.minimize:
        self.optimizer.tell(job.candidate, df.iloc[0][self.metric_to_optimize])
      else:
        self.optimizer.tell(job.candidate, -df.iloc[0][self.metric_to_optimize])

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
    self.full_df.to_csv(os.path.join(directory, FULL_DF_FILE))
    self.minimal_df.to_csv(os.path.join(directory, REDUCED_DF_FILE))
    self_file = os.path.join(directory, STATUS_PICKLE_FILE)
    with open(self_file, 'wb') as f:
      pickle.dump(self, f)


class GridSearchOptimizer(Optimizer):
  def __init__(self, *, restarts, **kwargs):
    super().__init__(iteration_mode=True, **kwargs)
    self.parameter_dicts = {param.param_name: param.values for param in self.optimized_params}
    self.set_setting_generator()
    self.restarts = restarts
    self.iteration = 0

  def set_setting_generator(self):
    self.setting_generator = get_sample_generator(None, self.parameter_dicts, None, None)

  def ask(self, num_samples):
    settings = next(self.setting_generator, None)
    if settings is None:
      self.iteration += 1
      if self.iteration == self.restarts:
        return None, None
      self.set_setting_generator()
      settings = next(self.setting_generator)
      assert settings is not None
      return (None, settings)
    return (None, settings)

  def ask_all(self):
    _, settings = self.ask(1)
    while not settings is None:
      yield (None, settings)
      _, settings = self.ask(1)
    raise StopIteration()

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
