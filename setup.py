from setuptools import setup

setup(name='cluster',
      version='2.1',
      description='Cluster utilities',
      url='https://github.com/martius-lab',
      author='Michal Rolinek, MPI-IS Tuebingen, Autonomous Learning',
      author_email='michalrolinek@gmail.com',
      license='MIT',
      packages=['cluster'],
      python_requires='>=3.6',
      install_requires=['gitpython>=3.0.5', 'seaborn', 'pandas', 'matplotlib', 'sklearn', 'numpy',
                        'nevergrad @ git+https://github.com/facebookresearch/nevergrad.git', 'tqdm', 'colorama',
                        'pyuv', 'cloudpickle',
                        'smart_settings @ git+ssh://git@gitlab.tuebingen.mpg.de/mrolinek/smart-json.git'],
      zip_safe=False)
