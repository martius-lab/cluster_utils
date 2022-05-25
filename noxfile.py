import tempfile

import nox

nox.options.sessions = ("lint", "tests", "pytest")
LOCATIONS = ("cluster/", "examples/", "tests/", "noxfile.py", "setup.py")


@nox.session(python=["3.6"])
def lint(session):
    session.install("black")
    session.install("flake8")
    session.install("flake8-bugbear")
    session.install("flake8-isort")
    session.run("black", "--check", *LOCATIONS)
    session.run("flake8", *LOCATIONS)


@nox.session(python="3.6")
def black(session):
    session.install("black")
    session.run("black", *LOCATIONS)


@nox.session(python="3.6")
def pytest(session):
    session.install(".")
    session.install("pytest")
    session.run("pytest")


@nox.session(python=["3.6"])
def tests(session):
    session.install(".")

    with tempfile.TemporaryDirectory() as test_dir:
        session.run("bash", "tests/run_integration_tests.sh", test_dir, external=True)
