import numpy as np
import awkward as ak
import coffea.processor as processor
from coffea.nanoevents.methods import candidate


class Processor(processor.ProcessorABC):
    def postprocess(self, accumulator):
        pass

    def process(self, events):
        pad = lambda x, target: ak.pad_none(x, target=target, clip=True)
        jets = pad(events.Jet, 2)
        photons = pad(events.Photon, 2)
        from IPython import embed;embed()  # fmt: skip
        return ak.zip(
            {
                # photons
                "photon1_pt": photons.pt[:, 0],
                "photon2_pt": photons.pt[:, 1],
                # jets
                "jet1_pt": jets.pt[:, 0],
                "jet2_pt": jets.pt[:, 1],
            }
        )