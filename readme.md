## Run to install:

``python3 -m pip install git+https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git --user``

or 

``python3 -m pip install git+https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git --upgrade --user``

to upgrade

Also recommended to add this line to your .bashrc (.zshrc) on the cluster

``export MPLBACKEND="agg"``


## News it version 1.2

In HP optimization, the best `k` jobs can optionally have their output dirs preserved. See `example1` (last lines)

Every submission creates a `job_info.csv` in the result directory which matches parameter combinations to cluster job ids

The wait for the first informative cluster status cut down to 10 seconds

Explicit support for virtual environments (`virtual_env_path` is accepted in `paths_and_files`)

The `job_requirements` now accept `gpu_memory_mb` to specify gpu memory requirement.  


## News in version 1.1

Git support -- see example 1 to get the idea (thanks Sebastian)

Better handling of restarts -> more reliable results

JSON sections supported in LatexFile

Improved optimization algorithm


