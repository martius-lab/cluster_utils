from setuptools import setup

setup(
    name="cluster",
    version="2.4",
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
        "pandas",
        "matplotlib",
        "scikit-learn",
        "numpy",
        "nevergrad",
        "tqdm",
        "colorama",
        "pyuv",
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
        ]
    },
    entry_points={
        "console_scripts": [
            "cluster_utils_plot_timeline=cluster.scripts.plot_job_timeline:main",
        ]
    },
    zip_safe=False,
)
