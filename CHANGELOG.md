# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[//]: # (Note: {ref}/{doc} roles are used for references to the documentation)

## Unreleased

## [3.0.0] - 2024-08-19

### Changed
- **Breaking:** Drop support for Python versions < 3.8
- **Breaking:** PDF reports are not generated anymore by default.  Add
  `generate_report = "every_iteration"` in the settings to restore behaviour of previous
  versions.
- **Breaking:** `Optimizer.save_pdf_report()` is moved out of the `Optimizer` class to
  `report.produce_optimization_report()`.
- **Breaking:** Renamed the package from "cluster" to "cluster_utils".  Imports will
  still work for now (see Deprecated section) but in commands for running
  hp_optimization/grid_search need to be changed accordingly (e.g. `python3 -m
  cluster_utils.grid_search ...`)
- **Breaking:** All exit codes other than 0 or 3 (the magic "restart for resume" code)
  are now considered as failures.  Previously only 1 was considered as failure.
- **Breaking:** Changed the parsing of arguments in `read_params_from_cmdline()`:
  1. Server information is now passed using named arguments `--cluster-utils-server` and
     `--job_id` instead of a positional dictionary string.
  2. There is no automatic detection anymore, whether the parameters are passed as file
     or as dictionary string.  By default a path to a file is expected now.  When using
     a dictionary instead, the new argument `--parameter-dict` has to be set now.

  That is, instead of
  ```
  script.py "{'_id': 42, 'ip': '127.0.0.1', 'port': 12345}" "{'param1': 1, 'param2': 2, ...}"
  ```
  use this now:
  ```
  script.py --job-id=42 --cluster-utils-server=127.0.0.1:12345 --parameter-dict \
      "{'param1': 1, 'param2': 2, ...}"
  ```

  Running a job script manually using a parameter file still works like before:
  ```
  script.py path/to/settings.json
  ```

  Likewise, arguments are passed to job scripts using the new format now, when they are
  executed by cluster_utils.  So if you use non-python scripts that process the
  arguments, they may need to be updated accordingly.
- The raw data of `grid_search` is saved to a file "all_data.csv" instead of
  "results_raw.csv" to be consistent with `hp_optimization` (the format of the file
  didn't change, only the name).
- Dependencies for report generation and nevergrad are not installed by default
  anymore.  Install the optional dependency groups "report" and "nevergrad" if
  needed (see {ref}`optional_dependencies`)
- Local submissions now store stdout and stderr to log files, like they would do on the cluster.
  This should be useful for debugging scripts to work with the cluster locally, as previously,
  there was no way to access the outputs of locally running jobs.
- Renamed `read_params_from_cmdline` to `initialize_job`.  An alias with the old name is
  available but will raise a FutureWarning.
- Renamed `save_metrics_params` to `finalize_job`.  An alias with the old name is
  available but will raise a FutureWarning.
- *Relevant for Dev's only:* Use ruff instead of flake8 for linting.
- Internal modules have been moved to sub-packages.  This should not affect normal users
  which just run cluster_utils via the provided scripts but in cause you have some
  custom scripts, running cluster_utils, you may need to update them.
- Base dependencies cover only needs of `client` and `base` sub-packages.  For the
  `server` sub-package (needed to run the cluster_utils applications), install the
  optional-dependencies group "runner".

### Removed
- Removed option `save_params` from `read_params_from_cmdline`.  They will always be
  saved now.
- Removed option `make_immutable` from `read_params_from_cmdline`.  Returned parameters
  are always immutable now.  If needed, a mutable copy can be created with
  `smart_settings.param_classes.AttributeDict(params)`.
- Removed imports of `grid_search()` and `hp_optimization()` functions directly from
  `cluster_utils`.  They can still be imported from `cluster_utils.server.job_manager`
  if needed (though regular users shouldn't need to call them directly).

### Added
- Setting `generate_report` to control automatic report generation (See
  {ref}`config.general_settings`).
- Command `python3 -m cluster.scripts.generate_report` to manually generate the report
  based on saved files (see {doc}`report`).
- Support settings files in TOML format.
- Control logger level via environment variable `CLUSTER_UTILS_LOG_LEVEL` (most relevant
  use-case is to enable debug output via `export CLUSTER_UTILS_LOG_LEVEL=debug`.
- Option to run jobs in Singularity/Apptainer containers (see
  {ref}`config_singularity`).
- Basic Slurm support (Note supported options in `cluster_requirements` differs a bit
  from HTCondor, see {ref}`config_cluster_requirements`).
- `grid_search` and `hp_optimization` now provide some help when called with `--help`.

### Fixed
- Make it work with Python >=3.10
- Fix not counting some jobs as successfully concluded. This happened if the server registered a
  job as finished before its results arrived, incorrectly counting such a job as failed.
  This might have been in particular the case if a job sent a larger amount of metric information
  at once.
- Fix `exit_for_resume` not working on local submissions. If a job called `exit_for_resume`,
  the job would just exit, not restart, and `cluster_utils` would indefinitely hang waiting for the
  job to fully finish. Now, local submissions restart the job if the job instructs them too.


### Deprecated
- The package has been renamed from "cluster" to "cluster_utils", please update your
  imports accordingly.  There is still a wrapper package with the old name (so existing
  code should still work) but it will be removed in the next major release.
- `read_params_from_cmdline` is deprecated.  Use `initialize_job` instead.
- `save_metrics_params` is deprecated.  Use `finalize_job` instead.


## [2.5] - 2023-10-05

**Last version supporting Python 3.6.**


## 2.4 - 2022-02-08

## [2.1] - 2020-06-20

## [2.0] - 2020-03-25

---

[Unreleased]: https://github.com/martius-lab/cluster_utils/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/martius-lab/cluster_utils/compare/v2.5...v3.0.0
[2.5]: https://github.com/martius-lab/cluster_utils/compare/v2.1...v2.5
[2.1]: https://github.com/martius-lab/cluster_utils/compare/v2.0...v2.1
[2.0]: https://github.com/martius-lab/cluster_utils/releases/tag/v2.0
