import os

import law
import pandas as pd
import awkward as ak
from coffea.nanoevents import NanoEventsFactory, DelphesSchema
from matplotlib import pyplot as plt

from processor import Skimmer


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


class DelphesPythia8(
    DetectorMixin,
    ProcessMixin,
    BaseTask,
):
    def output(self):
        return self.local_target("events.root")

    @property
    def executable(self):
        return f"{os.getenv('DELPHES_DIR')}/DelphesPythia8"

    @law.decorator.safe_output
    def run(self):
        detector_config = self.detector_config
        process_config = self.process_config

        self.output().parent.touch()
        out_path = self.output().path

        cmd = f"{self.executable} {detector_config} {process_config} {out_path}"
        os.system(cmd)


class SkimEvents(
    DetectorMixin,
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
            metadata={"dataset": "ttbar"},
        ).events()

        skimmer = Skimmer()
        out = skimmer.process(events)
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
        df.hist()
        plt.savefig(self.output().path)