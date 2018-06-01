## Run to install:

python3 -m pip install git+https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git

or 

python3 -m pip install git+https://gitlab.tuebingen.mpg.de/mrolinek/cluster_utils.git --upgrade

to upgrade

## High priority TODO:

pdf output

keep best runs

add adaptive distributions

warm restarts

choose between minimize/maximize

output also std over restarts

some way of testing


## Low priority TODO:

reuse previous best jobs

Add more examples

Write better readme

## Done

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
