#Install Pythia

module load python
mamba create -c conda-forge --name withroot root
conda activate withroot

export path_to_PYTHIA8_installation=$PWD

wget https://pythia.org/download/pythia82/pythia8235.tgz
tar xzvf pythia8235.tgz
cd pythia8235
./configure --prefix=$path_to_PYTHIA8_installation
make install
cd ..

#Install Delphes
wget http://cp3.irmp.ucl.ac.be/downloads/Delphes-3.5.0.tar.gz
tar -zxf Delphes-3.5.0.tar.gz

cd Delphes-3.5.0
make HAS_PYTHIA8=true

cd ..

cp myprocess_ttbar.C Delphes-3.5.0/examples/.
cp pythia_ttbar.cmnd Delphes-3.5.0/cards/.
