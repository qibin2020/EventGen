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


# Define a generic type for the decorator
F = TypeVar("F", bound=Callable[..., Any])


class SlurmFactory:
    """
    A factory class for managing a Dask cluster on a SLURM-based system and
    executing functions using Dask parallelization.

    This class facilitates the creation and management of a SLURMCluster for
    distributed computing, providing a simple interface to scale the number
    of jobs and execute tasks in parallel.

    Attributes:
        cluster (SLURMCluster): An instance of the SLURMCluster, representing
            the Dask cluster running on a SLURM scheduler.

    Methods:
        __init__(jobs=1, *args, **kwargs) -> None:
            Initializes the SLURM cluster with the specified number of jobs
            and additional configuration arguments.

        __del__() -> None:
            Closes the SLURM cluster upon object deletion to release resources.

        scale(*args, **kwargs) -> None:
            Scale SLURM cluster to specified configurations.

        execute(func: F) -> F:
            A decorator that wraps a function with Dask parallelization.

            The function is converted into a Dask delayed object and executed
            on the SLURM cluster. The results are computed and returned, and
            the Dask client is closed afterward.

    Usage Example:
        ```
        # Create a SLURM cluster with 4 jobs
        factory = SlurmFactory(jobs=4, queue='short', project='my_project')

        @factory.execute
        def process_data(data):
            # Function to be parallelized
            return [x**2 for x in data]

        # Execute the function using the SLURM cluster
        result = process_data([1, 2, 3, 4])
        print(result)  # Output: [1, 4, 9, 16]
        ```

    Parameters:
        jobs (int): The number of SLURM jobs to scale the cluster to. Default is 1.
        *args: Additional positional arguments to be passed to the SLURMCluster.
        **kwargs: Additional keyword arguments to configure the SLURMCluster.

    Note:
        - The SLURMCluster instance should be properly configured with the
          necessary SLURM parameters like `queue`, `project`, `cores`, etc.
        - The `execute` method requires the `dask` library with `distributed`
          and `jobqueue` modules to be installed.
        - You might want to use the configurations in the bottoms of this file.
    """

    def __init__(self, jobs=1, *args, **kwargs) -> None:
        # Start SLURM Cluster
        self.cluster = SLURMCluster(*args, **kwargs)

        # Adjust the number of jobs as needed
        self.scale(jobs=jobs)

    def __del__(self) -> None:
        self.cluster.close()

    def scale(self, *args, **kwargs) -> None:
        self.cluster.scale(*args, **kwargs)

    def execute(self, func: F) -> F:
        @functools.wraps(func)
        def decor(*args: Any, **kwargs: Any) -> Any:
            # Connect a Dask client to the cluster
            client = Client(self.cluster)

            # Wrap the function call in a Dask delayed object
            delayed_task = delayed(func)(*args, **kwargs)

            # Execute the task using Dask
            result = compute(delayed_task)

            # Close the client and cluster when done
            client.close()

            # Return result of task
            return result

        return decor


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