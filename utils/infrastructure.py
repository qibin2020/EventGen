import functools
from dask_jobqueue import SLURMCluster
from dask.distributed import Client
from dask import delayed, compute

from functools import wraps


class SlurmFactory:
    def __init__(
        self,
        jobs=1,
        queue="interactive",
        cores=1,
        memory="1GB",
        walltime="00:30:00",
        job_extra_directives=["-C cpu"],
        *args,
        **kwargs
    ) -> None:
        # Start SLURM Cluster
        self.cluster = SLURMCluster(
            queue=queue,
            cores=cores,
            memory=memory,
            walltime=walltime,
            job_extra_directives=job_extra_directives,
            *args,
            **kwargs
        )

        # Adjust the number of jobs as needed
        self.cluster.scale(jobs=jobs)

    def __del__(self):
        self.cluster.close()

    def slurm(self, f):
        @functools.wraps(f)
        def decor(*args, **kwargs):
            # Connect a Dask client to the cluster
            client = Client(self.cluster)

            # Wrap the function call in a Dask delayed object
            delayed_task = delayed(f)(*args, **kwargs)

            # Execute the task using Dask
            result = compute(delayed_task)

            # Close the client and cluster when done
            client.close()

            # Return result of task
            return result

        return decor

slurm_factory = SlurmFactory()