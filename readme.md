## Run to install:

python3 -m pip install git+https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git

or 

python3 -m pip install git+https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git --upgrade

to upgrade

Also recommended to add this line to your .bashrc (.zshrc) on the cluster

export MPLBACKEND="agg"


## Low priority TODO:

add histogram based distribution distributions

some way of testing

Add more examples

Write better readme

## Done

warm restarts ... done

pdf output ... done

reuse previous best jobs ... Done

output also std over restarts ... Done

choose between minimize/maximize ... Done

expose manage_submission as api ... Done

reuse submission code for both main scripts ... Done

save dataframes ... Done

hide hyperparameter optimize code ... Done

separate cluster operating code ... Done

separate setting code, write easier interface ... Done

erase only correct jobs ... Done

make nested dicts and distributions compatible... Done

support list as discrete choices ... Done (tuples supported instead)

add +1 to discrete distributions ... Done

shuffle jobs for submission ... Done

change all paths to absolute ... Done

change object access symbol from ':' to '.' ... Done

rounding interface change ... Done

factor out error handling ... Done

factor out submission status ... Done

sanitize smart naming ... Done

regexp sanitizing ... Done

hyperparam dicts switch to 'object.param' format (no longer nested) ... Done
