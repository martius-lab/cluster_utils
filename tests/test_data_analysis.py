import pandas as pd
import pytest

from cluster import data_analysis


@pytest.fixture()
def dataframe():
    # rows 1 and 2 have same hyperparams, row 0 is different
    return pd.DataFrame(
        {
            "_id": {0: 1, 1: 2, 2: 3},
            "_iteration": {0: 1, 1: 1, 2: 1},
            "fn_args.bool": {0: False, 1: True, 2: True},
            "fn_args.float": {0: 0.6, 1: -0.6, 2: -0.6},
            "fn_args.int": {0: 2, 1: 40, 2: 40},
            "id": {0: 1, 1: 2, 2: 3},
            "noiseless_result": {
                0: 12.5968933347,
                1: 33.3542941387,
                2: 16.4773746778,
            },
            "result": {0: 12.4721423596, 1: 33.0832478035, 2: 16.628410918},
            "test_resume": {0: False, 1: False, 2: False},
            "time_elapsed": {
                0: 16.0243828297,
                1: 27.0289058685,
                2: 16.0180177689,
            },
            "working_dir": {
                0: "/test/working_directories/1",
                1: "/test/working_directories/2",
                2: "/test/working_directories/6",
            },
        }
    )


def test_average_out(dataframe):
    metrics = ["result"]
    params_to_keep = [
        "fn_args.bool",
        "fn_args.float",
        "fn_args.int",
    ]
    result = data_analysis.average_out(dataframe, metrics, params_to_keep)

    # sort by some column, so we are sure on the order
    result = result.sort_values(by=["fn_args.int"])

    expected = pd.DataFrame(
        {
            "fn_args.bool": {
                0: False,
                1: True,
            },
            "fn_args.float": {
                0: 0.6,
                1: -0.6,
            },
            "fn_args.int": {
                0: 2,
                1: 40,
            },
            "result": {
                0: 12.4721423596,
                1: 24.85582936075,
            },
            "job_restarts": {0: 1, 1: 2},
            "result__std": {0: None, 1: 11.6353267451},
        }
    )

    pd.testing.assert_frame_equal(result, expected)
