import os
import importlib
import subprocess

import luigi
import law
import pandas as pd
from coffea.nanoevents import NanoEventsFactory, DelphesSchema
from matplotlib import pyplot as plt
import dask
from dask.distributed import Client
from dask import delayed

from utils.pythia import replace_in_config, replacements
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
    def madgraph_config_file(self):
        return f"{self.process_config_dir}/madgraph.dat"

    @property
    def pythia_config_file(self):
        return f"{self.process_config_dir}/pythia.cmnd"

    @property
    def has_madgraph_config(self):
        return os.path.isfile(self.madgraph_config_file)


class DetectorMixin:
    detector = law.Parameter(default="CMS")

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

    def store_parts(self):
        sp = super().store_parts()
        return sp + (f"n_events_{int(self.n_events)}",)


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
    def identifiers(self):
        return list(str(i) for i in range(len(self.brakets)))



class Madgraph(
    ChunkedEventsTask,
    ProcessMixin,
    BaseTask,
):
    def requires(self):
        return MadgraphConfig.req(self)

    @property
    def executable(self):
        return f"{os.getenv('MADGRAPH_DIR')}/bin/mg5_aMC"

    def output(self):
        return {
            identifier: {
                "config": self.local_target(f"config_{identifier}.dat"),
                "madgraph_dir": self.local_directory_target(f"out_{identifier}"),
                "events": self.local_target(
                    f"out_{identifier}/Events/run_01/unweighted_events.lhe.gz"
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

            n_events = stop - start
            madgraph_config = str(madgraph_config_base)
            madgraph_config = madgraph_config.replace(
                "NEVENTS_PLACEHOLDER", str(int(n_events))
            )
            madgraph_config = madgraph_config.replace(
                "OUTPUT_PLACEHOLDER", madgraph_target.path
            )
            config_target.dump(madgraph_config, formatter="text")
            cmd = [self.executable, "-f", config_target.path]
            cmds.append(cmd)

        for cmd in cmds:
            subprocess.run(cmd)


class DelphesPythia8(
    DetectorMixin,
    ChunkedEventsTask,
    ProcessMixin,
    ClusterMixin,
    BaseTask,
):
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
        return f"{os.getenv('DELPHES_DIR')}/DelphesPythia8"

    @law.decorator.safe_output
    def run(self):
        detector_config = self.detector_config
        pythia_config_base = self.input()["pythia_config"].load(formatter="text")

        # Set up the tasks to compute
        cmds = []
        for identifier, (start, stop) in zip(self.identifiers, self.brakets):
            config_target = self.output()[identifier]["config"]
            events_target = self.output()[identifier]["events"]

            config_target.parent.touch()
            events_target.parent.touch()

            n_events = stop - start
            _replacements = dict(n_events=n_events)
            if self.has_madgraph_config:
                _replacements["beams_lhef"] = self.input()["madgraph"][identifier][
                    "events"
                ].path

            pythia_config = replace_in_config(
                pythia_config_base, replacements(**_replacements)
            )
            config_target.dump(pythia_config, formatter="text")

            cmd = f"{self.executable} {detector_config} {config_target.path} {events_target.path}"
            cmds.append(cmd)

        # Set up the SLURM cluster
        cluster = SLURMCluster(**configs["perlmutter_debug"])
        cluster.scale(len(self.brakets))

        # Connect to the cluster
        cluster = self.start_cluster(n_workers=len(self.brakets))
        client = Client(cluster)

        # Submit tasks
        tasks = [delayed(os.system)(cmd) for cmd in cmds]
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
    def requires(self):
        return DelphesPythia8.req(self)

    def output(self):
        return self.local_target("skimmed.h5")

    @law.decorator.safe_output
    def run(self):
        inputs = self.input()
        events = NanoEventsFactory.from_root(
            {inp["events"].path: "Delphes" for inp in inputs.values()},
            schemaclass=DelphesSchema,
        ).events()

        processor = self.processor_class()
        out = processor.process(events)

        cluster = self.start_cluster()
        client = Client(cluster)
        (computed,) = dask.compute(out)

        df = pd.DataFrame(computed.to_numpy().data)

        # Write file to h5
        self.output().parent.touch()
        df.to_hdf(self.output().path, key="events")


class PlotEvents(SkimEvents):
    def requires(self):
        return SkimEvents.req(self)

    def output(self):
        return self.local_directory_target("plots.pdf")

    def run(self):
        # Read the DataFrame from the HDF5 file
        df = pd.read_hdf(self.input().path, key="events")

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
            PlotEvents.req(self, process="nonres_yy", n_events=1e8),
            PlotEvents.req(self, process="ggh_yy", n_events=1e6),
            PlotEvents.req(self, process="ttH_yy", n_events=1e6),
            PlotEvents.req(self, process="vbf_yy", n_events=1e6),
            PlotEvents.req(self, process="vh_yy", n_events=1e6),
            PlotEvents.req(self, process="chihchiw", n_events=1e6),
        ]
