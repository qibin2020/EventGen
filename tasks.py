import os

import law
import pandas as pd
import awkward as ak
from coffea.nanoevents import NanoEventsFactory, DelphesSchema

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

class DetectorConfig:
    pass

class ProcessConfig:
    pass

class ProcessMixin:
    process = law.Parameter("ttbar")
    
class DetectorMixin:
    detector = law.Parameter("CMS")

class PrepareConfigs(
        DetectorMixin,
        ProcessMixin,
        BaseTask,
        law.ExternalTask,
    ):


    def output(self):
        return {
            "detector": self.local_target(f"{self.detector}.tcl"),
            "process": self.local_target(f"{self.process}.cmnd"),
        }

class DelphesPythia8(BaseTask):
    def requires(self):
        return PrepareConfigs.req(self)
    
    def output(self):
        return self.local_target("events.root")
    
    @property
    def executable(self):
        return f"{os.getenv('DELPHES_DIR')}/DelphesPythia8"

    def run(self):
        detector_config = self.input()["detector"].path
        process_config = self.input()["process"].path

        self.output.parent.touch()
        out_path = self.output().path
        
        cmd = f"{self.executable} {detector_config} {process_config} {out_path}"
        os.system(cmd)


class SkimEvents(BaseTask):
    def requires(self):
        return DelphesPythia8.req(self)
    
    def output(self):
        return self.local_target("skimmed.h5")
    
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
        self.output.parent.touch()
        df.to_hdf(self.output.path)