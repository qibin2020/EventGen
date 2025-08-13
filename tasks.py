import os
import importlib
import subprocess

import luigi
import law
import pandas as pd
from coffea.nanoevents import DelphesSchema
from coffea.dataset_tools import (
    apply_to_fileset,
    preprocess,
)
from matplotlib import pyplot as plt
import dask
from dask.distributed import Client
from dask import delayed

from utils.numpy import NumpyEncoder
from utils.infrastructure import ClusterMixin


class BaseTask(law.Task):
    """
    Base task which provides some convenience methods
    """

    version = law.Parameter(default="dev")

    def store_parts(self):
        task_name = self.__class__.__name__
        return (
            os.getenv("GEN_OUT"),
            f"version_{self.version}",
            task_name,
        )

    def local_path(self, *path):
        sp = self.store_parts()
        sp += path
        return os.path.join(*(str(p) for p in sp))

    def local_target(self, *path, **kwargs):
        return law.LocalFileTarget(self.local_path(*path), **kwargs)

    def local_directory_target(self, *path, **kwargs):
        return law.LocalDirectoryTarget(self.local_path(*path), **kwargs)


class ProcessMixin:
    process = law.Parameter(default="test")

    def store_parts(self):
        sp = super().store_parts()
        return sp + (self.process,)

    @property
    def process_config_dir(self):
        return f"{os.getenv('GEN_CODE')}/config/{self.process}"
    
    @property
    def common_model_dir(self): # used to load common UFO models -- no need to copy every time
        return f"{os.getenv('GEN_CODE')}/model"
    
    @property
    def common_param_dir(self): # used to load common param_card (e.g. decay width) -- no need to copy every time
        return f"{os.getenv('GEN_CODE')}/param"

    @property
    def madgraph_config_file(self):
        return f"{self.process_config_dir}/madgraph.dat"

    @property
    def pythia_config_file(self):
        return f"{self.process_config_dir}/pythia.cmnd"

    @property
    def has_madgraph_config(self):
        return os.path.isfile(self.madgraph_config_file)


class DetectorMixin:
    detector = law.Parameter(default="ATLAS")

    def store_parts(self):
        sp = super().store_parts()
        return sp + (self.detector,)

    @property
    def detector_config_dir(self):
        return f"{os.getenv('DELPHES_DIR')}/cards"

    @property
    def detector_config_file(self):
        return f"delphes_card_{self.detector}.tcl"

    @property
    def detector_config(self):
        return f"{self.detector_config_dir}/{self.detector_config_file}"


class ProcessorMixin:
    processor = law.Parameter(default="test")

    def store_parts(self):
        sp = super().store_parts()
        return sp + (self.processor,)

    @property
    def processor_module(self):
        return importlib.import_module(f"processors.{self.processor}")

    @property
    def processor_class(self):
        return getattr(self.processor_module, "Processor")


class NEventsMixin:
    n_events = luigi.IntParameter(default=1000)


class MadgraphConfig(ProcessMixin, law.ExternalTask):
    def output(self):
        return law.LocalFileTarget(self.madgraph_config_file)


class PythiaConfig(ProcessMixin, law.ExternalTask):
    def output(self):
        return law.LocalFileTarget(self.pythia_config_file)


class ChunkedEventsTask(NEventsMixin):
    n_max = luigi.IntParameter(default=1000000)

    @property
    def brakets(self):
        n_events = int(self.n_events)
        starts = range(0, n_events, self.n_max)
        stops = list(starts)[1:] + [n_events]
        brakets = zip(starts, stops)
        return list(brakets)

    @property
    def n_brakets(self):
        return len(self.brakets)

    @property
    def identifiers(self):
        return list(f"{i}_with_{int(self.n_max)}" for i in range(self.n_brakets))


class Madgraph(
    ChunkedEventsTask,
    ProcessMixin,
    ClusterMixin,
    BaseTask,
):
    # SLURM Configuration
    # Adjusted to 1Mio events of nonres_yy_jjj process
    cores = 1
    memory = "64GB"
    walltime = "24:00:00"
    qos = "shared"

    def requires(self):
        return MadgraphConfig.req(self)

    @property
    def executable(self):
        return f"{os.getenv('MADGRAPH_DIR')}/bin/mg5_aMC"

    def output(self):
        return {
            identifier: {
                "config": self.local_target(f"{identifier}/config.dat"),
                "madgraph_dir": self.local_directory_target(f"{identifier}/out"),
                "events": self.local_target(
                    f"{identifier}/out/Events/run_01/unweighted_events.lhe.gz"
                ),
            }
            for identifier in self.identifiers
        }

    def run(self):
        madgraph_config_base = self.input().load(formatter="text")
        # Set up the tasks to compute
        cmds = []
        for identifier, (start, stop) in zip(self.identifiers, self.brakets):
            config_target = self.output()[identifier]["config"]
            madgraph_target = self.output()[identifier]["madgraph_dir"]
            events_target = self.output()[identifier]["events"]
            # In case the task already successfully finished an identifier
            if events_target.exists():
                continue

            n_events = stop - start
            madgraph_config = str(madgraph_config_base)
            madgraph_config = madgraph_config.replace(
                "NEVENTS_PLACEHOLDER", str(int(n_events))
            )
            madgraph_config = madgraph_config.replace(
                "OUTPUT_PLACEHOLDER", madgraph_target.path
            )
            madgraph_config = madgraph_config.replace(
                "MODEL_PLACEHOLDER", self.common_model_dir
            )
            madgraph_config = madgraph_config.replace(
                "PARAM_PLACEHOLDER", self.common_param_dir
            )
            config_target.dump(madgraph_config, formatter="text")
            cmd = [self.executable, "-f", config_target.path]
            cmds.append(cmd)

        # Connect to the cluster
        cluster = self.start_cluster(len(cmds))
        client = Client(cluster)

        # Submit tasks
        tasks = [delayed(subprocess.call)(cmd) for cmd in cmds]
        results = client.compute(tasks)

        # Gather the results
        results = client.gather(results)

        # Scale down and close the cluster
        cluster.scale(0)
        client.close()
        cluster.close()


class DelphesPythia8(
    DetectorMixin,
    ChunkedEventsTask,
    ProcessMixin,
    ClusterMixin,
    BaseTask,
):
    # SLURM Configuration
    cores = 1
    memory = "1GB"
    walltime = "24:00:00"
    qos = "shared"

    def output(self):
        return {
            identifier: {
                "config": self.local_target(f"{identifier}/config.txt"),
                "events": self.local_target(f"{identifier}/events.root"),
                "out": self.local_target(f"{identifier}/out.txt"),
            }
            for identifier in self.identifiers
        }

    def requires(self):
        if self.has_madgraph_config:
            return {
                "madgraph": Madgraph.req(self),
                "pythia_config": PythiaConfig.req(self),
            }
        else:
            return {"pythia_config": PythiaConfig.req(self)}

    @property
    def executable(self):
        return f"DelphesPythia8"

    @staticmethod
    def call_with_output(cmd, out_path):
        with open(out_path, "w") as out_file:
            result = subprocess.call(cmd, stdout=out_file, stderr=out_file)
        return result

    @law.decorator.safe_output
    def run(self):
        detector_config = self.detector_config
        pythia_config = self.input()["pythia_config"].load(formatter="text")

        # Set up the tasks to compute
        cmds = []
        for identifier, (start, stop) in zip(self.identifiers, self.brakets):
            config_target = self.output()[identifier]["config"]
            events_target = self.output()[identifier]["events"]
            out_target = self.output()[identifier]["out"]
            # In case the task already successfully finished an identifier
            if events_target.exists():
                continue

            config_target.parent.touch()
            events_target.parent.touch()
            out_target.parent.touch()

            n_events = stop - start
            pythia_config = pythia_config.replace(
                "NEVENTS_PLACEHOLDER", str(int(n_events))
            )

            if self.has_madgraph_config:
                madgraph_events = self.input()["madgraph"][identifier]["events"].path
                pythia_config = pythia_config.replace(
                    "INPUT_PLACEHOLDER", madgraph_events
                )

            config_target.dump(pythia_config, formatter="text")

            cmd = [
                self.executable,
                detector_config,
                config_target.path,
                events_target.path,
            ]
            cmds.append((cmd, out_target.path))

        # Connect to the cluster
        cluster = self.start_cluster(len(cmds))
        client = Client(cluster)

        # Submit tasks
        tasks = [delayed(self.call_with_output)(cmd, out) for (cmd, out) in cmds]
        results = client.compute(tasks)

        # Gather the results
        results = client.gather(results)

        # Scale down and close the cluster
        cluster.scale(0)
        client.close()
        cluster.close()


class SkimEvents(
    ProcessorMixin,
    DetectorMixin,
    NEventsMixin,
    ProcessMixin,
    ClusterMixin,
    BaseTask,
):
    # SLURM Configuration
    # Using only one core as task will be IO limited
    cores = 1
    memory = "5GB"
    walltime = "00:05:00"
    qos = "shared"
    arch = "cpu"

    def requires(self):
        return DelphesPythia8.req(self)

    def output(self):
        return {
            "cutflow": self.local_target("cutflow.json"),
            "events": self.local_target("skimmed.h5"),
        }

    @law.decorator.safe_output
    def run(self):
        inputs = self.input()
        # Get FSet
        fset = {
            "all": {
                "files": {inp["events"].path: "Delphes" for inp in inputs.values()}
            }
        }

        # Start Preprocessing
        dataset_runnable, _ = preprocess(fset)

        # Apply to Fileset
        to_compute = apply_to_fileset(
            self.processor_class(),
            dataset_runnable,
            schemaclass=DelphesSchema,
        )

        # Compute Payload
        cluster = self.start_cluster(len(inputs))
        with Client(cluster) as client:
            (output,) = dask.compute(to_compute)
        
        output = output["all"]

        # Write cutflow to json
        cutflow = output["cutflow"]
        self.output()["cutflow"].dump(cutflow, cls=NumpyEncoder)

        # Write events to h5
        events = output["events"]
        df = pd.DataFrame(events.to_numpy().data)

        # add efficiencies
        eff = cutflow["good"] / cutflow["total"]
        df["selection_efficiency"] = eff

        df.to_hdf(self.output()["events"].path, key="events")


class PlotEvents(SkimEvents):
    def requires(self):
        return SkimEvents.req(self)

    def output(self):
        return self.local_directory_target("plots.pdf")

    def run(self):
        # Read the DataFrame from the HDF5 file
        df = pd.read_hdf(self.input()["events"].path, key="events")

        # Plot the Dataframe
        df.hist(figsize=(15, 8), log=True)
        plt.suptitle(
            f"Process {self.process} @ {self.detector} using {self.processor} processor"
        )
        plt.tight_layout()

        # Save plot
        self.output().parent.touch()
        plt.savefig(self.output().path)


class PlotEventsWrapper(BaseTask, law.WrapperTask):
    def requires(self):
        return [
            PlotEvents.req(self, process="nonres_yy_jjj", processor="yy", n_events=3e7),
            PlotEvents.req(self, process="ggh_yy", processor="yy", n_events=2e6),
            PlotEvents.req(self, process="ttH_yy", processor="yy", n_events=2e6),
            PlotEvents.req(self, process="vbf_yy", processor="yy", n_events=2e6),
            PlotEvents.req(self, process="vh_yy", processor="yy", n_events=2e6),
            PlotEvents.req(self, process="WN_HyyN_150", processor="yy", n_events=1e6),
            PlotEvents.req(self, process="WN_HyyN_200", processor="yy", n_events=1e7),
            PlotEvents.req(self, process="WN_HyyN_300", processor="yy", n_events=1e6),
            PlotEvents.req(self, process="WN_HyyN_600", processor="yy", n_events=1e6),
            PlotEvents.req(self, process="TT_tZNtHyyN", processor="yy", n_events=1e6),
        ]
