import os
import importlib

import luigi
import law
import pandas as pd
import awkward as ak
from coffea.nanoevents import NanoEventsFactory, DelphesSchema
from matplotlib import pyplot as plt

from utils.pythia import replace_in_config
from utils.infrastructure import slurm_factory


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


class ProcessConfig(NEventsMixin, ProcessMixin, BaseTask):
    def requires(self):
        return OriginalProcessConfig.req(self)

    def output(self):
        return self.local_target("config.cmnd")

    @property
    def replacements(self):
        return {"Main:numberOfEvents": self.n_events}

    def run(self):
        config = self.input().load(formatter="text")
        new_config = replace_in_config(config, self.replacements)
        self.output().dump(new_config, formatter="text")


class DelphesPythia8(
    DetectorMixin,
    NEventsMixin,
    ProcessMixin,
    BaseTask,
):
    def output(self):
        return self.local_target("events.root")

    def requires(self):
        return ProcessConfig.req(self)

    @property
    def executable(self):
        return f"{os.getenv('DELPHES_DIR')}/DelphesPythia8"

    @slurm_factory.execute
    @law.decorator.safe_output
    def run(self):
        detector_config = self.detector_config
        process_config = self.input().path

        self.output().parent.touch()
        out_path = self.output().path

        cmd = f"{self.executable} {detector_config} {process_config} {out_path}"
        os.system(cmd)


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
        input_file = self.input().path

        events = NanoEventsFactory.from_root(
            {input_file: "Delphes"},
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
            PlotEvents.req(self, process="nonres_yy", n_events=6e6),
            PlotEvents.req(self, process="ggh_yy", n_events=6e4),
            PlotEvents.req(self, process="ttH_yy", n_events=4e3),
            PlotEvents.req(self, process="vbf_yy", n_events=4e3),
            PlotEvents.req(self, process="vh_yy", n_events=4e4),
        ]
