#!/bin/bash
#
# This is a dummy drop-in replacement for pdflatex that can be used for
# integration tests in the GitLab CI pipeline.  It will not actually render a
# report but will
# - verify that the given input latex file actually exists
# - create a fake PDF file with the expected name
#
# This is tailored specifically for how pdflatex is used in this package.  It
# is expected to be called like this:
#
#     pdflatex -interaction=nonstopmode path/to/latex.tex
#
# If the usage of pdflatex changes, this file may need to be adapted.

set -e

# Parse arguments.  They are expected to all be options (starting with "-")
# except for one which is the input latex file.
input_file=
while [[ $# -gt 0 ]]; do
    case $1 in
        -*)
            echo "Got option $1 (will be ignored in this test)"
            shift
            ;;
        *)
            if [[ -n "${input_file}" ]]; then
                1>&2 echo "ERROR [$0]: Got more than one positional arguments.  Expected only one for the input filename."
                exit 1
            fi
            input_file="$1"
            shift
            ;;
    esac
done


if [[ -z "${input_file}" ]]; then
    1>&2 echo "ERROR [$0]: No input filename was given."
    exit 1
fi

if [[ ! -f "${input_file}" ]]; then
    1>&2 echo "ERROR [$0]: Input file '${input_file}' does not exist or is not a file."
    exit 1
fi

if [[ "${input_file}" != *.tex ]]; then
    1>&2 echo "ERROR [$0]: Input file '${input_file}' is not a tex file."
    exit 1
fi

# If we reach here, the input is okay.  Create a dummy output file.
output_file="${input_file%.tex}.pdf"

# Just be sure we do not accidentally overwrite something important.  This
# should not be the case in the test setup, so better fail if it happens.
if [[ -e "${output_file}" ]]; then
    1>&2 echo "ERROR [$0]: Output file '${input_file}' already exists."
    exit 1
fi

1>&2 echo "INFO [$0]: Create file ${output_file}"
echo "This is a fake PDF" > "${output_file}"
