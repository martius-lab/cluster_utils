#!/bin/bash
set -e

test_dir="$1"


# verify that report got created
function assert_report_exists {
    title="$1"
    report_file="$2"
    if [[ ! -e "${report_file}" ]]; then
        echo -e "\e[31m"  # colour red
        echo "FAIL: Missing file ${report_file}"
        echo "FAIL: No report has been created for ${title}"
        echo -e "\e[0m"  # reset colour

        # for debugging
        cluster_run_log="${report_file%/*}/cluster_run.log"
        echo "cluster_run.log:"
        if command -v boxes &> /dev/null; then
            boxes -d parchment "${cluster_run_log}"
        else
            echo "------------------------------------------------------------"
            cat "${cluster_run_log}"
            echo "------------------------------------------------------------"
        fi

        exit 1
    else
        echo -e "\e[32m"  # colour green
        echo "PASS: ${report_file} was generated."
        echo -e "\e[0m"  # reset colour
    fi
}

#
# grid_search
#
(
    set -x
    python -m cluster_utils.grid_search tests/grid_search.json \
        "no_user_interaction=True" \
        "results_dir=\"$test_dir\"" \
        "generate_report=\"when_finished\"" \
        <<EOF
y
y
EOF
)
# ^This is a temporary crutch because we need to say Yes to the questions cluster_utils asks
assert_report_exists grid_search "${test_dir}/test_grid_search/test_grid_search_report.pdf"

# test manual report generation
(
    set -x
    python -m cluster_utils.scripts.generate_report \
        "${test_dir}/test_grid_search" \
        "${test_dir}/test_grid_search/offline_report.pdf"
)
assert_report_exists "generate_report (grid_search)" \
    "${test_dir}/test_grid_search/offline_report.pdf"


#
# hp_optimization
#
(
    set -x
    python -m cluster_utils.hp_optimization tests/hp_opt.json \
        "no_user_interaction=True" \
        "results_dir=\"$test_dir\"" \
        "generate_report=\"every_iteration\"" \
        <<EOF
y
y
EOF
)
assert_report_exists hp_optimization "${test_dir}/test_hp_opt/result.pdf"

# test manual report generation
(
    set -x
    python -m cluster_utils.scripts.generate_report \
        "${test_dir}/test_hp_opt" "${test_dir}/test_hp_opt/offline_report.pdf"
)
assert_report_exists "generate_report (hp_optimization)" \
    "${test_dir}/test_hp_opt/offline_report.pdf"
