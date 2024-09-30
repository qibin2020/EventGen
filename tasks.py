import os
import importlib

import luigi
import law
import pandas as pd
import awkward as ak
from coffea.nanoevents import NanoEventsFactory, DelphesSchema
from matplotlib import pyplot as plt
from dask_jobqueue import SLURMCluster
from dask.distributed import Client
from dask import delayed

from utils.pythia import replace_in_config, replacements
from utils.infrastructure import configs


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
    process = law.Parameter(default="ttbar")

    def store_parts(self):
        sp = super().store_parts()
        return sp + (self.process,)

    @property
    def process_config_dir(self):
        return f"{os.getenv('GEN_CODE')}/config"

    @property
    def process_config_file(self):
        return f"pythia_{self.process}.cmnd"

    @property
    def process_config(self):
        return f"{self.process_config_dir}/{self.process_config_file}"


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
    processor = law.Parameter(default="yy")

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
    n_events = luigi.IntParameter(default=1)

    def store_parts(self):
        sp = super().store_parts()
        return sp + (f"n_events_{int(self.n_events)}",)


class OriginalProcessConfig(ProcessMixin, law.ExternalTask):
    def output(self):
        return law.LocalFileTarget(self.process_config)


class DelphesPythia8(
    DetectorMixin,
    NEventsMixin,
    ProcessMixin,
    BaseTask,
):
    n_max = luigi.IntParameter(default=100000)

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

    def output(self):
        return {
            identifier: {
                "config": self.local_target(f"config_{identifier}.txt"),
                "events": self.local_target(f"events_{identifier}.root"),
            }
            for identifier in self.identifiers
        }

    def requires(self):
        return OriginalProcessConfig.req(self)

    @property
    def executable(self):
        return f"{os.getenv('DELPHES_DIR')}/DelphesPythia8"

    @law.decorator.safe_output
    def run(self):
        detector_config = self.detector_config
        process_config_base = self.input().load(formatter="text")

        # Set up the tasks to compute
        cmds = []
        for identifier, (start, stop) in zip(self.identifiers, self.brakets):
            config_target = self.output()[identifier]["config"]
            events_target = self.output()[identifier]["events"]

            config_target.parent.touch()
            events_target.parent.touch()

            n_events = stop - start
            process_config = replace_in_config(
                process_config_base,
                replacements(n_events),
            )
            config_target.dump(process_config, formatter="text")

            cmd = f"{self.executable} {detector_config} {config_target.path} {events_target.path}"
            cmds.append(cmd)

        # Set up the SLURM cluster
        cluster = SLURMCluster(**configs["perlmutter_debug"])
        cluster.scale(len(self.brakets))

        # Connect to the cluster
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
        computed = out.compute()

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
            # PlotEvents.req(self, process="nonres_yy", n_events=6e6),
            PlotEvents.req(self, process="ggh_yy", n_events=6e4),
            PlotEvents.req(self, process="ttH_yy", n_events=4e3),
            PlotEvents.req(self, process="vbf_yy", n_events=4e3),
            PlotEvents.req(self, process="vh_yy", n_events=4e4),
        ]
