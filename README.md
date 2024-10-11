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

You can look at all outputs of the workflow with
```bash
law run PlotEvents --process test --print-status 4
```

which produces the following output:
```bash
print task status with max_depth 4 and target_depth 0

0 > PlotEvents(version=dev, process=test, detector=CMS, processor=yy, n_events=1000)
│     LocalDirectoryTarget(fs=local_fs, path=output/version_dev/PlotEvents/test/n_events_1000/CMS/yy/plots.pdf)
│       existent
│
└──1 > SkimEvents(version=dev, process=test, detector=CMS, processor=yy, n_events=1000)
   │     LocalFileTarget(fs=local_fs, path=output/version_dev/SkimEvents/test/n_events_1000/CMS/yy/skimmed.h5)
   │       existent
   │
   └──2 > DelphesPythia8(version=dev, process=test, detector=CMS, n_events=1000, n_max=1000000)
      │     0:
      │       config: LocalFileTarget(fs=local_fs, path=output/version_dev/DelphesPythia8/test/n_events_1000/CMS/config_0.txt)
      │         existent
      │       events: LocalFileTarget(fs=local_fs, path=output/version_dev/DelphesPythia8/test/n_events_1000/CMS/events_0.root)
      │         existent
      │
      ├──3 > Madgraph(version=dev, process=test, n_events=1000, n_max=1000000)
      │  │     0:
      │  │       config: LocalFileTarget(fs=local_fs, path=output/version_dev/Madgraph/test/n_events_1000/config_0.dat)
      │  │         existent
      │  │       generation: LocalDirectoryTarget(fs=local_fs, path=output/version_dev/Madgraph/test/n_events_1000/out_0)
      │  │         existent
      │  │       events: LocalDirectoryTarget(fs=local_fs, path=output/version_dev/Madgraph/test/n_events_1000/out_0/Events/run_01/unweighted_events.lhe.gz)
      │  │         existent
      │  │
      │  └──4 > MadgraphConfig(process=test, external)
      │           LocalFileTarget(fs=local_fs, path=config/test/madgraph.dat)
      │             existent
      │
      └──3 > PythiaConfig(process=test, external)
               LocalFileTarget(fs=local_fs, path=config/test/pythia.cmnd)
                 existent
```
We can see, that the workflow executed all necessary steps, such as using madgraph to produce `LHE` files, using pythia and delphes to produce `root` files, skimming the events, and finally plotting some key features.