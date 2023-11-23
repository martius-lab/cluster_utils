# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[//]: # (Note: {ref}/{doc} roles are used for references to the documentation)

## Unreleased (3.0.0)

### Changed
- **Breaking:** Drop support for Python versions < 3.8
- **Breaking:** PDF reports are not generated anymore by default.  Add
  `generate_report = "every_iteration"` in the settings to restore behaviour of previous
  versions.
- **Breaking:** `Optimizer.save_pdf_report()` is moved out of the `Optimizer` class to
  `report.produce_optimization_report()`.
- The raw data of `grid_search` is saved to a file "all_data.csv" instead of
  "results_raw.csv" to be consistent with `hp_optimization` (the format of the file
  didn't change, only the name).
- Dependencies for report generation and nevergrad are not installed by default
  anymore.  Install the optional dependency groups "report" and "nevergrad" if
  needed (see {ref}`optional_dependencies`)
- *Relevant for Dev's only:* Use ruff instead of flake8 for linting.

### Added
- Setting `generate_report` to control automatic report generation (See
  {ref}`config.general_settings`).
- Command `python3 -m cluster.scripts.generate_report` to manually generate the report
  based on saved files (see {doc}`report`).
- Support settings files in TOML format.
- Control logger level via environment variable `LOG_LEVEL` (most relevant
  use-case is to enable debug output via `export LOG_LEVEL=debug`.
- Option to run jobs in Singularity/Apptainer containers (see
  {ref}`config_singularity`).

### Fixed
- Make it work with Python >=3.10
- Fix not counting some jobs as successfully concluded. This happened if the server registered a
  job as finished before its results arrived, incorrectly counting such a job as failed.
  This might have been in particular the case if a job sent a larger amount of metric information
  at once.


## 2.5 - 2023-10-05

**Last version supporting Python 3.6.**


## 2.4 - 2022-02-08

## 2.1 - 2020-06-20

## 2.0 - 2020-03-25