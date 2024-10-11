# EventGenDelphes
Minimal python-based workflow to run particle physics simulations on the Perlmutter cluster using Madgraph, Pythia, and Delphes.
It also includes software to skim and plot key features of the events.

## Setup
To setup your working area do:
```bash
source setup.sh
```

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
```bash
output OUTPUT_PLACEHOLDER
launch
set nevents NEVENTS_PLACEHOLDER
```

### In `pythia.cmnd`
Use:
```bash
Beams:frameType = 4
Beams:LHEF = LHEF_PLACEHOLDER
```
to import the correct madgraph produces LHE files.

## Workflow
The workflow is run with `law`.

To index the current available tasks and make them and their parameters usable in the command line please do:
```bash
law index
```

Then you may run the workflow with executing e.g.:
```bash
law run PlotEvents --process test
```

We can see, that the workflow executed all necessary steps, such as using madgraph to produce `LHE` files, using pythia and delphes to produce `root` files, skimming the events, and finally plotting some key features.