#!/bin/bash
set -e

test_dir="$1"


(
    set -x
    python -m cluster.grid_search tests/grid_search.json \
        "no_user_interaction=True" \
        "results_dir=\"$test_dir\"" \
        "generate_report=\"when_finished\"" \
        <<EOF
y
y
EOF
)
# ^This is a temporary crutch because we need to say Yes to the questions cluster_utils asks

# verify that report got created
report_file="${test_dir}/test_grid_search/test_grid_search_report.pdf"
if [[ ! -e "${report_file}" ]]; then
    echo "FAIL: Missing file ${report_file}"
    echo "FAIL: No report has been created for grid_search"
    exit 1
fi


(
    set -x
    python -m cluster.hp_optimization tests/hp_opt.json \
        "no_user_interaction=True" \
        "results_dir=\"$test_dir\"" \
        "generate_report=\"every_iteration\"" \
        <<EOF
y
y
EOF
)

# verify that report got created
report_file="${test_dir}/test_hp_opt/result.pdf"
if [[ ! -e "${report_file}" ]]; then
    echo "FAIL: Missing file ${report_file}"
    echo "FAIL: No report has been created for hp_optimization"
    exit 1
fi
