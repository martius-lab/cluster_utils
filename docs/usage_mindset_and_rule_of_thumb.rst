********************************
Usage Mindset and Rules of Thumb
********************************

Generally, the usage mindset should be *"obtain some interpretable understanding
of the influence of the hyperparameters"* rather than *"blackbox optimizer just
tells me the best setting"*.  Usually, early in the project many of the
hyperparameters are more like ideas, or strategies.  Cluster utils can then tell
you which ideas (or their combinations) make sense.  Later in a project, there
only tend to be actual hyperparameters (i.e. transferring a working architecture
to a new dataset), which can then be fit to this specific setting using cluster
utils.

Here are some rules of thumbs to set the configuration values that can help you
to get started. Keep in mind that following these does not necessarily lead to
optimal results on your specific problem.

**Which optimizer should I use for optimizing hyperparameters of neural networks
(depth, width, learning rate, etc.)?**

    ``cem_metaoptimizer`` is a good default recommendation for this case.

**How many jobs should I run? How many concurrently?**

    It depends. The number of concurrent jobs (``n_jobs_per_iteration``) should
    be as high as achievable with the current load on the cluster.  For CPU
    jobs, this could be 100 concurrent jobs; for GPU jobs, maybe around 40.  The
    total number of jobs (``number_of_samples``) can be lower if you only want
    to get an initial impression of the behaviour of the hyperparameter; in this
    case, 3-5 times the number of jobs per iteration is a good number.  If you
    want to get a more precise result, or if you have a high number of
    hyperparameters, up to 10 times the number of jobs per iteration can be
    used.

**How many hyperparameters can I optimize over at the same time?**

    This depends on the number of jobs and number of parallely running jobs. For
    5x100 jobs, 5-6 hyperparameters are okay to be optimized. For 5x40 jobs, 3-4
    are okay. For a larger scale, e.g. 10x200 jobs, it might be reasonable to
    optimize up to 10 hyperparameters at the same time.

**How to deal with overfitting?**

    You can keep the best validation error achieved over the epochs and report
    this instead of the error achieved in the last epoch.
