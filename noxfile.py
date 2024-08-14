"""Test and lint setup."""

import tempfile

import nox

PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11", "3.12"]


@nox.session(python=PYTHON_VERSIONS, tags=["lint"])
def lint(session):
    session.install(".[lint]")
    session.run("black", "--check", ".")
    session.run("ruff", "check", ".")


@nox.session(python=PYTHON_VERSIONS, tags=["lint"])
def mypy(session):
    """Run mypy"""
    # all required packages should be provided through the optional "mypy" dependency
    session.install(".[mypy]")
    session.run("mypy", ".")


@nox.session(python=PYTHON_VERSIONS, tags=["test"])
def pytest(session):
    session.install(".[all,test]")
    session.run("pytest")


@nox.session(python=PYTHON_VERSIONS, tags=["test"])
def integration_tests(session):
    session.install(".[runner]")

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
    session.install(".[runner,report]")

    with tempfile.TemporaryDirectory() as test_dir:
        session.run(
            "bash",
            "tests/run_integration_tests_with_report.sh",
            test_dir,
            external=True,
        )


@nox.session(python=PYTHON_VERSIONS, tags=["test"])
def integration_tests_with_nevergrad(session):
    session.install(".[runner,nevergrad]")

    with tempfile.TemporaryDirectory() as test_dir:
        session.run(
            "bash",
            "tests/run_integration_tests_with_nevergrad.sh",
            test_dir,
            external=True,
        )


@nox.session(python=PYTHON_VERSIONS, tags=["test"])
def integration_tests_with_venv(session):
    session.install(".[runner]")

    with tempfile.TemporaryDirectory() as test_dir:
        session.run(
            "bash",
            "tests/run_integration_tests_with_venv.sh",
            test_dir,
            external=True,
        )
