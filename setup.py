from setuptools import setup

setup(name='cluster',
      version='1.2',
      description='Cluster utilities',
      url='https://github.com/martius-lab',
      author='Michal Rolinek, MPI-IS Tuebingen, Autonomous Learning',
      author_email='michalrolinek@gmail.com',
      license='MIT',
      packages=['cluster'],
      install_requires=['gitpython>=3.0.5', 'pathlib2', 'seaborn', 'pandas', 'matplotlib', 'sklearn', 'numpy',
                        'nevergrad @ git+https://github.com/facebookresearch/nevergrad.git', 'tqdm', 'colorama',
                        'pyuv', 'cloudpickle'],
      zip_safe=False)
