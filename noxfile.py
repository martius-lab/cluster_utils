import tempfile

import nox

LOCATIONS = ('cluster/', 'examples/', 'noxfile.py', 'setup.py')


@nox.session(python=['3.6'])
def lint(session):
    session.install('flake8')
    session.install('flake8-bugbear')
    session.install('flake8-isort')
    session.run('flake8', *LOCATIONS)


@nox.session(python=['3.6'])
def tests(session):
    session.install('.')

    with tempfile.TemporaryDirectory() as test_dir:
        session.run('bash', 'tests/run_integration_tests.sh', test_dir,
                    external=True)
