from setuptools import setup

setup(
    name="cluster",
    version="2.5",
    description="Cluster utilities",
    url="https://github.com/martius-lab",
    author="Michal Rolinek, MPI-IS Tuebingen, Autonomous Learning",
    author_email="michalrolinek@gmail.com",
    license="MIT",
    packages=["cluster"],
    python_requires=">=3.6",
    install_requires=[
        "gitpython>=3.0.5",
        "seaborn>=0.11.0",
        "pandas[output-formatting]",
        # TODO: Temporary workaround.  Jinja is included in the "output-formatting"
        # optional dependencies of pandas but there is currently a problem with the
        # dependencies that should be fixed in pandas 2.1.2
        # (https://github.com/pandas-dev/pandas/pull/55275).  So once 2.1.2 is released,
        # the explicit dependency on jinja2 can be removed.
        "jinja2",
        "matplotlib",
        "scikit-learn",
        "numpy",
        "nevergrad",
        "tqdm",
        "colorama",
        # master of pyuv contains fix needed for Python 3.10
        "pyuv @ git+https://github.com/saghul/pyuv.git@master",
        "cloudpickle",
        "smart_settings @ git+https://github.com/martius-lab/smart-settings.git",
        "python-dateutil",
    ],
    extras_require={
        "dev": [
            "absolufy-imports",
            "black",
            "flake8",
            "flake8-bugbear",
            "flake8-isort",
            "nox",
            "pre-commit",
            "pytest",
        ],
        "mypy": [
            "mypy",
            "pandas-stubs",
            "types-colorama",
            "types-python-dateutil",
            "types-tqdm",
        ],
    },
    entry_points={
        "console_scripts": [
            "cluster_utils_plot_timeline=cluster.scripts.plot_job_timeline:main",
        ]
    },
    zip_safe=False,
)
