"""Test and lint setup."""

import tempfile

import nox

PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11", "3.12"]

nox.options.sessions = ("lint", "mypy", "tests", "pytest")
LOCATIONS = ("cluster/", "examples/", "tests/", "noxfile.py", "setup.py")


@nox.session(python=PYTHON_VERSIONS)
def lint(session):
    session.install("black")
    session.install("ruff")
    session.run("black", "--check", *LOCATIONS)
    session.run("ruff", ".")


@nox.session(python=PYTHON_VERSIONS)
def mypy(session):
    """Run mypy"""
    # all required packages should be provided through the optional "mypy" dependency
    session.install(".[mypy]")
    session.run("mypy", ".")


@nox.session(python=PYTHON_VERSIONS)
def black(session):
    session.install("black")
    session.run("black", *LOCATIONS)


@nox.session(python=PYTHON_VERSIONS)
def pytest(session):
    session.install(".")
    session.install("pytest")
    session.run("pytest")


@nox.session(python=PYTHON_VERSIONS)
def tests(session):
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
