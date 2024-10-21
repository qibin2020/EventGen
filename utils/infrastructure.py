import os
import warnings
import functools
from typing import Callable, TypeVar, Any

import law
from dask.distributed import Client, LocalCluster
from dask_jobqueue import SLURMCluster
from dask import delayed, compute


# Filter dask warnings about used port
warnings.filterwarnings(
    "ignore",
    message=r"Port \d+ is already in use",
    category=UserWarning,
    module="distributed.node",
)

log_dir = [
    f'-o {os.getenv("GEN_SLURM")}/slurm-%j.out',
    f'-e {os.getenv("GEN_SLURM")}/slurm-%j.err',
]

configs = {
    "perlmutter_debug": dict(
        cores=1,
        memory="16GB",
        walltime="00:30:00",
        job_extra_directives=["--qos=debug", "-C cpu"] + log_dir,
    ),
    "perlmutter_small": dict(
        cores=1,
        memory="16GB",
        walltime="01:00:00",
        job_extra_directives=["--qos=regular", "-C cpu"] + log_dir,
    ),
    "perlmutter_medium": dict(
        cores=1,
        memory="64GB",
        walltime="08:00:00",
        job_extra_directives=["--qos=regular", "-C cpu"] + log_dir,
    ),
}

class ClusterMixin:
    cluster_mode = law.Parameter(default="local")

    def start_cluster(self, n_workers=1):
        # Set up the SLURM cluster
        if self.cluster_mode == "local":
            cluster = LocalCluster()
        elif self.cluster_mode == "slurm":
            cluster = SLURMCluster(**configs["perlmutter_debug"])
        else:
            raise ValueError(f"Unknown cluster mode {self.cluster}")
        cluster.scale(n_workers)
        return cluster