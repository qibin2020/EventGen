import functools
from dask_jobqueue import SLURMCluster
from dask.distributed import Client
from dask import delayed, compute

from functools import wraps


def slurm_factory(
    jobs=1,
    queue="interactive",
    cores=1,
    memory="1GB",
    walltime="00:30:00",
    job_extra_directives=["-C cpu"],
    *args,
    **kwargs
):
    def slurm(f):
        @functools.wraps(f)
        def decor(*func_args, **func_kwargs):
            # Set up the SLURMCluster
            cluster = SLURMCluster(
                queue=queue,
                cores=cores,
                memory=memory,
                walltime=walltime,
                job_extra_directives=job_extra_directives,
                *args,
                **kwargs
            )

            # Scale the cluster to the desired number of workers
            cluster.scale(jobs=jobs)  # Adjust the number of jobs as needed

            # Connect a Dask client to the cluster
            client = Client(cluster)

            # Wrap the function call in a Dask delayed object
            delayed_task = delayed(f)(*func_args, **func_kwargs)

            # Execute the task using Dask
            result = compute(delayed_task)

            # Close the client and cluster when done
            client.close()
            cluster.close()

            return result

        return decor

    return slurm
