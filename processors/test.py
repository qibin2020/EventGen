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
        # jets = ak.zip(
        #     {
        #         "pt": jets.pt,
        #         "eta": jets.eta,
        #         "phi": jets.phi,
        #         "mass": ak.zeros_like(jets.pt),
        #         "charge": ak.zeros_like(jets.pt),
        #     },
        #     with_name="PtEtaPhiMCandidate",
        #     behavior=candidate.behavior,
        # )

        good = jets[:, 0].pt > 50
        good = ak.fill_none(good, False)

        return {
            "cutflow": {
                "total": ak.num(good, axis=0),
                "good": ak.sum(good),
            },
            "events": ak.zip(
                {
                    "jet1_pt": jets[:, 0].pt[good],
                    "jet2_pt": jets[:, 1].pt[good],
                }
            ),
        }
