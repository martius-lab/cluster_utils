#!/bin/bash
set -e

test_dir=$1

# create venv for the jobs in temporary directory
venv_dir="${test_dir}/venv"
python -m venv "$venv_dir"
source "${venv_dir}/bin/activate"
# upgrade pip to avoid potential installation issues
pip install -U pip
# install cluster_utils in the venv
pip install .
# install dependencies of the test script itself
pip install numpy
deactivate

# The config doesn't contain the actual path to the venv, so we need to pass it
# here.
python -m cluster_utils.grid_search "tests/grid_search_with_venv.toml" \
    "no_user_interaction=True" \
    "results_dir='$test_dir'" \
    "environment_setup.virtual_env_path='${venv_dir}'" \
    <<EOF
y
y
EOF
# ^This is a temporary crutch because we need to say Yes to the questions cluster_utils asks
