/*
This macro shows how to compute jet energy scale.
root -l examples/Example4.C'("delphes_output.root", "plots.root")'
*/

#ifdef __CLING__
R__LOAD_LIBRARY(libDelphes)
#include "classes/DelphesClasses.h"
#include "external/ExRootAnalysis/ExRootTreeReader.h"
#include "external/ExRootAnalysis/ExRootResult.h"
#else
class ExRootTreeReader;
class ExRootResult;
#endif

class ExRootResult;
class ExRootTreeReader;

//------------------------------------------------------------------------------

void AnalyseEvents(ExRootTreeReader *treeReader,  const char *outputFile_part)
{
  TClonesArray *branchGenJet = treeReader->UseBranch("GenJet");
  TClonesArray *branchParticle = treeReader->UseBranch("Particle");
  TClonesArray *branchEvent = treeReader->UseBranch("Event");
  TClonesArray *branchJet = treeReader->UseBranch("Jet");
  TClonesArray *branchEFlowTrack = treeReader->UseBranch("EFlowTrack");
  TClonesArray *branchEFlowPhoton = treeReader->UseBranch("EFlowPhoton");
  TClonesArray *branchEFlowNeutralHadron = treeReader->UseBranch("EFlowNeutralHadron");
  TClonesArray *branchElectron = treeReader->UseBranch("Electron");
  TClonesArray *branchPhoton = treeReader->UseBranch("Photon");
  TClonesArray *branchMuon = treeReader->UseBranch("Muon");
  
  Long64_t allEntries = treeReader->GetEntries();
  ofstream myfile_det;
  ofstream myfile_part;

  cout << "** Chain contains " << allEntries << " events" << endl;

  Jet  *genjet;
  Jet *jet;
  GenParticle *particle;
  GenParticle *muparticle;
  GenParticle *genparticle;
  GenParticle *motherparticle;
  TObject *object;
  Photon *photon;
  Track *track;
  Tower *tower;
  Muon *muon;
  
  TLorentzVector genJetMomentum;
  TLorentzVector jetMomentum;
  TLorentzVector myMomentum;
  
  TLorentzVector incomingelectron;
  TLorentzVector incomingpositron;
  TLorentzVector outgoingphoton;
  
  Long64_t entry;

  Int_t i, j;

  myfile_part.open (outputFile_part);

  // Loop over all events
  for(entry = 0; entry < allEntries; ++entry)
  {
    //if (entry > 10000) break;
    // Load selected branches with data from specified event
    treeReader->ReadEntry(entry);
    HepMCEvent *event = (HepMCEvent*) branchEvent -> At(0);
    //std::cout << "weight : " << event->Weight << std::endl;
    
    if(entry%500 == 0) cout << "Event number: "<< entry <<endl;

    //myfile_part << event->Weight << " ";
    
    int countjets = 0;
    for(i = 0; i < branchJet->GetEntriesFast(); ++i){
      jet = (Jet*) branchJet->At(i);
      if (jet->PT > 25 && fabs(jet->Eta) < 2.5) countjets++;
    }
    int countGjets = 0;
    for(i = 0; i < branchGenJet->GetEntriesFast(); ++i){
      genjet = (Jet*) branchGenJet->At(i);
      if (genjet->PT > 25 && fabs(jet->Eta) < 2.5) countGjets++;
    }
    int countmuons = 0;
    for(i=0; i< branchMuon->GetEntriesFast(); ++i){
      muon = (Muon*) branchMuon->At(i);
      if (muon->PT > 25 && fabs(muon->Eta) < 2.5) countmuons++;
    }
    myfile_part << countmuons << " " << countjets << " " << countGjets;
    myfile_part << std::endl;
    
  }
}
//------------------------------------------------------------------------------

void myprocess_ttbar(const char *inputFile, const char *outputFile_part)
{
  gSystem->Load("libDelphes");

  TChain *chain = new TChain("Delphes");
  chain->Add(inputFile);

  ExRootTreeReader *treeReader = new ExRootTreeReader(chain);
  ExRootResult *result = new ExRootResult();

  AnalyseEvents(treeReader,outputFile_part);

  cout << "** Exiting..." << endl;

  delete result;
  delete treeReader;
  delete chain;
}

//------------------------------------------------------------------------------
