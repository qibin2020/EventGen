import os
import numpy as np

os.chdir("Delphes-3.5.0")
os.system("rm tmp.root")
os.system("./DelphesPythia8 cards/delphes_card_CMS.tcl cards/pythia_ttbar.cmnd tmp.root")
os.system("root -b -x -q 'examples/myprocess_ttbar.C(\"tmp.root\",\"ttbar_tmp.txt\")'")
os.system("rm tmp.root")
os.system("mv ttbar_tmp.txt ../.")
