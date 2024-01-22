#!/bin/bash

set -x
test_dir=$1

python -m cluster_utils.grid_search tests/main_no_save_metrics.json \
    "no_user_interaction=True" \
    "results_dir=\"$test_dir\"" \
    <<EOF
y
y
EOF
