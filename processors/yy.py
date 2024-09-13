import numpy as np
import awkward as ak
import coffea.processor as processor
from coffea.nanoevents.methods import candidate


class Processor(processor.ProcessorABC):
    def postprocess(self, accumulator):
        pass

    def process(self, events):
        pad = lambda x, target: ak.pad_none(x, target=target, clip=True)
        photons = pad(events.Photon, 2)
        hgamma = ak.zip(
            {
                "pt": photons.pt,
                "eta": photons.eta,
                "phi": photons.phi,
                "mass": ak.zeros_like(photons.pt),
                "charge": ak.zeros_like(photons.pt),
            },
            with_name="PtEtaPhiMCandidate",
            behavior=candidate.behavior,
        )

        diphoton_mass = (hgamma[:, 0] + hgamma[:, 1]).mass
        diphoton_delta_r = hgamma[:, 0].delta_r(hgamma[:, 1])
        gamma_pt_rel = photons.pt / diphoton_mass[:, None]
        photon1_pt_rel, photon2_pt_rel = gamma_pt_rel[:, 0], gamma_pt_rel[:, 1]

        jets = pad(events.Jet, 2)
        jets = ak.zip(
            {
                "pt": jets.pt,
                "eta": jets.eta,
                "phi": jets.phi,
                "mass": ak.zeros_like(jets.pt),
                "charge": ak.zeros_like(jets.pt),
            },
            with_name="PtEtaPhiMCandidate",
            behavior=candidate.behavior,
        )

        dijet_mass = (jets[:, 0] + jets[:, 1]).m
        dijet_delta_r = jets[:, 0].delta_r(jets[:, 1])
        ht_30 = ak.sum(events.Jet.pt[events.Jet.pt > 30], axis=-1)

        has_lepton = (ak.num(events.Muon) > 0) | (ak.num(events.Electron) > 0)

        met_pt = events.MissingET.MET

        return ak.zip(
            {
                # photons
                "diphoton_mass": diphoton_mass,
                "photon1_pt_rel": photon1_pt_rel,
                "photon2_pt_rel": photon2_pt_rel,
                "diphoton_delta_r": diphoton_delta_r,
                # jets
                "jet1_pt": jets.pt[:, 0],
                "jet2_pt": jets.pt[:, 1],
                "dijet_mass": dijet_mass,
                "dijet_delta_r": dijet_delta_r,
                "ht_30": ht_30,
                # leptons
                "has_lepton": has_lepton,
                # met
                "met_pt": met_pt,
                # misc features
                "n_photon": ak.num(events.Photon),
                "n_jet": ak.num(events.Jet),
            }
        )