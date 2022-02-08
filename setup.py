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
        "sklearn",
        "numpy",
        "nevergrad",
        "tqdm",
        "colorama",
        "pyuv",
        "cloudpickle",
        "smart_settings @ git+https://github.com/martius-lab/smart-settings.git",
    ],
    extras_require={
        "dev": [
            "absolufy-imports",
            "flake8",
            "flake8-bugbear",
            "flake8-isort",
            "nox",
            "pre-commit",
        ]
    },
    zip_safe=False,
)
