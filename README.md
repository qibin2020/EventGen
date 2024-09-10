# EventGenDelphes
This is for running Pythia + Delphes on Perlmutter.

## Setup
Before working do `source setup.sh`.
When not done yet, this command installs the necessary software environment, pythia, and delphes.
Also it activates the software environment and sets the necessary environment variables.

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