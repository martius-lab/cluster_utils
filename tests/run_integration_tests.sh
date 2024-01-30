#!/bin/bash

test_dir=$1

set -e
set -x


python -m cluster_utils.grid_search tests/grid_search.json \
    "no_user_interaction=True" \
    "results_dir=\"$test_dir\"" \
    <<EOF
y
y
EOF


python -m cluster_utils.hp_optimization tests/hp_opt.json \
    "no_user_interaction=True" \
    "results_dir=\"$test_dir\"" \
    <<EOF
y
y
EOF


python -m cluster_utils.grid_search tests/grid_search_main_w_decorator.json \
    "no_user_interaction=True" \
    "results_dir=\"$test_dir\"" \
    <<EOF
y
y
EOF


python -m cluster_utils.grid_search tests/grid_search_resume.json \
    "no_user_interaction=True" \
    "results_dir=\"$test_dir\"" \
    <<EOF
y
y
EOF

python -m cluster_utils.hp_optimization tests/hp_opt_resume.toml \
    "no_user_interaction=True" \
    "results_dir=\"$test_dir\"" \
    <<EOF
y
y
EOF
# ^This is a temporary crutch because we need to say Yes to the questions cluster_utils asks
