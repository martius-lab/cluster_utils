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
    python_requires=">=3.8",
    install_requires=[
        "gitpython>=3.0.5",
        # pandas 2.0.3 is the last version that works with Python 3.8
        # Note: on newer versions it should be "output-formatting" but on this one it
        # seems it still has to be "output_formatting" to work.
        "pandas[output_formatting]==2.0.3",
        "numpy",
        "scipy",
        "tqdm",
        "colorama",
        # master of pyuv contains fix needed for Python 3.10
        (
            "pyuv @ "
            "git+https://github.com/saghul/pyuv.git"
            "@2a3d42d44c6315ebd73899a35118380d2d5979b5"
        ),
        (
            "smart_settings @ "
            "git+https://github.com/martius-lab/smart-settings.git"
            "@eb7331fdcad58d314a842087bbf136735e890013"
        ),
    ],
    extras_require={
        # all optional dependencies, excluding the ones only needed for development
        "all": [
            "cluster[report]",
            "cluster[nevergrad]",
        ],
        # really all optional dependencies
        "all-dev": [
            "cluster[all]",
            "cluster[dev]",
            "cluster[mypy]",
            "cluster[docs]",
        ],
        # optional dependencies required for generating the report
        "report": [
            "seaborn>=0.11.0",
            "matplotlib",
            "scikit-learn",
        ],
        "nevergrad": [
            "nevergrad",
        ],
        "dev": [
            "absolufy-imports",
            "black",
            "ruff",
            "nox>=2022.8.7",
            "pre-commit",
            "pytest",
        ],
        "mypy": [
            "mypy",
            "pandas-stubs",
            "types-colorama",
            "types-tqdm",
        ],
        "docs": [
            "sphinx",
            "myst-parser",
        ],
    },
    entry_points={
        "console_scripts": [
            "cluster_utils_plot_timeline=cluster.scripts.plot_job_timeline:main",
        ]
    },
    zip_safe=False,
)
