import datetime
import pathlib

import pytest  # type: ignore

from cluster_utils.scripts.plot_job_timeline import JobStatus, parse_cluster_run_log


@pytest.fixture()
def cluster_run_logfile():
    this_dir = pathlib.PurePath(__file__).parent
    return this_dir / "cluster_run.log"


def test_parse_cluster_run_log(cluster_run_logfile):
    log = parse_cluster_run_log(cluster_run_logfile, cap_running_jobs_length=True)

    dt = datetime.datetime
    expected_log = {
        0: [
            (
                dt(2022, 4, 20, 17, 14, 8, 442000),
                dt(2022, 4, 20, 17, 14, 8, 442000),
                JobStatus.SUBMITTED,
            ),
            (
                dt(2022, 4, 20, 17, 14, 26, 961000),
                dt(2022, 4, 20, 17, 56, 44, 141000),
                JobStatus.EXIT_FOR_RESUME,
            ),
            (
                dt(2022, 4, 20, 17, 57, 36, 341000),
                dt(2022, 4, 20, 18, 46, 28, 808000),
                JobStatus.EXIT_FOR_RESUME,
            ),
            (
                dt(2022, 4, 20, 18, 47, 43, 30000),
                dt(2022, 4, 20, 19, 29, 45, 364000),
                JobStatus.FINISHED,
            ),
        ],
        1: [
            (
                dt(2022, 4, 20, 17, 14, 8, 863000),
                dt(2022, 4, 20, 17, 14, 8, 863000),
                JobStatus.SUBMITTED,
            ),
            (
                dt(2022, 4, 20, 17, 14, 28, 503000),
                dt(2022, 4, 20, 18, 4, 36, 28000),
                JobStatus.EXIT_FOR_RESUME,
            ),
            (
                dt(2022, 4, 20, 18, 5, 32, 693000),
                dt(2022, 4, 20, 18, 47, 4, 790000),
                JobStatus.EXIT_FOR_RESUME,
            ),
            (
                dt(2022, 4, 20, 18, 47, 44, 598000),
                dt(2022, 4, 20, 19, 41, 52, 446000),
                JobStatus.FINISHED,
            ),
        ],
        2: [
            (
                dt(2022, 4, 20, 17, 14, 9, 513000),
                dt(2022, 4, 20, 17, 14, 9, 513000),
                JobStatus.SUBMITTED,
            ),
            (
                dt(2022, 4, 20, 17, 14, 32, 215000),
                dt(2022, 4, 20, 18, 12, 50, 330000),
                JobStatus.EXIT_FOR_RESUME,
            ),
            (
                dt(2022, 4, 20, 18, 13, 34, 271000),
                dt(2022, 4, 20, 19, 21, 47, 810000),
                JobStatus.EXIT_FOR_RESUME,
            ),
            (
                dt(2022, 4, 20, 19, 22, 51, 599000),
                # end time of this is end_of_log + 0.4*log_duration
                dt(2022, 4, 20, 20, 42, 13, 16000),
                JobStatus.RUNNING,
            ),
        ],
        3: [
            (
                dt(2022, 4, 20, 17, 14, 9, 936000),
                dt(2022, 4, 20, 17, 14, 9, 936000),
                JobStatus.SUBMITTED,
            ),
            (
                dt(2022, 4, 20, 17, 14, 29, 650000),
                dt(2022, 4, 20, 18, 6, 57, 448000),
                JobStatus.EXIT_FOR_RESUME,
            ),
            (
                dt(2022, 4, 20, 18, 7, 31, 944000),
                dt(2022, 4, 20, 18, 57, 24, 666000),
                JobStatus.EXIT_FOR_RESUME,
            ),
            (
                dt(2022, 4, 20, 18, 57, 43, 862000),
                dt(2022, 4, 20, 19, 42, 51, 286000),
                JobStatus.FINISHED,
            ),
        ],
        4: [
            (
                dt(2022, 4, 20, 17, 14, 10, 609000),
                dt(2022, 4, 20, 17, 14, 10, 609000),
                JobStatus.SUBMITTED,
            ),
            (
                dt(2022, 4, 20, 17, 14, 28, 503000),
                dt(2022, 4, 20, 17, 15, 43, 695000),
                JobStatus.EXIT_FOR_RESUME,
            ),
            (
                dt(2022, 4, 20, 17, 16, 33, 933000),
                dt(2022, 4, 20, 17, 17, 49, 105000),
                JobStatus.FAILED,
            ),
        ],
        5: [
            (
                dt(2022, 4, 20, 17, 14, 11, 149000),
                dt(2022, 4, 20, 17, 14, 11, 149000),
                JobStatus.SUBMITTED,
            )
        ],
    }

    assert log[0] == expected_log[0]
    assert log[1] == expected_log[1]
    assert log[2] == expected_log[2]
    assert log[3] == expected_log[3]
    assert log[4] == expected_log[4]
    assert log[5] == expected_log[5]
