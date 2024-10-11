# EventGenDelphes
This is for running Pythia + Delphes on Perlmutter.

## Setup
Before working do `source setup.sh`.
When not done yet, this command installs the necessary software environment, pythia, and delphes.
Also it activates the software environment and sets the necessary environment variables.

## Configs
The process configurations are done in the `config` directory.
To add a process, add a new directory with the process name.
In the new directory you might add a madgraph configuration `madgraph.dat` and a pythia configuration `pythia.cmnd`.

If a madgraph configuration exist, the workflow will produce an LHE file with madgraph and feed this file to pythia and delphes.
If only a pythia configuration exists, the workflow will generate the events with pythia only.

You should use the following placeholders for the number of events and the output directories:

### In `madgraph.dat`
Use:
```
output OUTPUT_PLACEHOLDER
launch
set nevents NEVENTS_PLACEHOLDER
```

### In `pythia.cmnd`
Use:
```
Beams:frameType = 4
Beams:LHEF = LHEF_PLACEHOLDER
```
to import the correct madgraph produces LHE files.

## Workflow
The workflow is run with `law`.

To index the current available tasks and make them and their parameters usable in the command line please do:
```
law index
```

Then you may run the workflow with executing e.g.:
```
law run SkimEvents
```