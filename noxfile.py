"""Test and lint setup."""

import tempfile

import nox

PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11", "3.12"]

LOCATIONS = (
    "cluster_utils/",
    "cluster/",
    "examples/",
    "tests/",
    "noxfile.py",
    "setup.py",
)


@nox.session(python=PYTHON_VERSIONS, tags=["lint"])
def lint(session):
    session.install(".[lint]")
    session.run("black", "--check", *LOCATIONS)
    session.run("ruff", ".")


@nox.session(python=PYTHON_VERSIONS, tags=["lint"])
def mypy(session):
    """Run mypy"""
    # all required packages should be provided through the optional "mypy" dependency
    session.install(".[mypy]")
    session.run("mypy", ".")


@nox.session(python=PYTHON_VERSIONS, tags=["test"])
def pytest(session):
    session.install(".[all]")
    session.install("pytest")
    session.run("pytest")


@nox.session(python=PYTHON_VERSIONS, tags=["test"])
def integration_tests(session):
    session.install(".")

    with tempfile.TemporaryDirectory() as test_dir:
        session.run("bash", "tests/run_integration_tests.sh", test_dir, external=True)
        session.run(
            "bash",
            "tests/test_main_no_save_metrics.sh",
            test_dir,
            external=True,
            success_codes=[1],
        )


@nox.session(python=PYTHON_VERSIONS, tags=["test"])
def integration_tests_with_report_generation(session):
    session.install(".[report]")

    with tempfile.TemporaryDirectory() as test_dir:
        session.run(
            "bash",
            "tests/run_integration_tests_with_report.sh",
            test_dir,
            external=True,
        )


@nox.session(python=PYTHON_VERSIONS, tags=["test"])
def integration_tests_with_nevergrad(session):
    session.install(".[nevergrad]")

    with tempfile.TemporaryDirectory() as test_dir:
        session.run(
            "bash",
            "tests/run_integration_tests_with_nevergrad.sh",
            test_dir,
            external=True,
        )
