#!/usr/bin/env bash
action() {
    # Set version of used software
    local pythia_version_major="pythia83"
    local pythia_version="pythia8311"
    local delphes_version="Delphes-3.5.0"

    # Set main directories
    local shell_is_zsh="$( [ -z "${ZSH_VERSION}" ] && echo "false" || echo "true" )"
    local this_file="$( ${shell_is_zsh} && echo "${(%):-%x}" || echo "${BASH_SOURCE[0]}" )"
    local this_dir="$( cd "$( dirname "${this_file}" )" && pwd )"

    # Set code and law area
    export GEN_CODE="${this_dir}"
    export GEN_OUT="${this_dir}/output"
    export PYTHONPATH="${this_dir}:${PYTHONPATH}"
    
    # Setup software directories
    export SOFTWARE_DIR="${this_dir}/software"
    mkdir -p $SOFTWARE_DIR

    export PYTHIA_DIR="${SOFTWARE_DIR}/${pythia_version}"
    export DELPHES_DIR="${SOFTWARE_DIR}/${delphes_version}"

    # If no conda available, activate it
    if ! command -v conda >/dev/null 2>&1; then
        module load python
    fi

    # If conda env "withroot" does not exist create it
    if ! conda env list | grep -q '^withroot'; then
        mamba create --name withroot
        mamba env update -n withroot --file environment.yml

    fi

    # Activate conda environment
    conda activate withroot

    # If Pythia not installed yet, do so
    if [ -d "$PYTHIA_DIR" ]; then
        echo "Pythia already installed"
    else
        echo "Installing Pythia"
        cd $SOFTWARE_DIR
        wget "https://pythia.org/download/${pythia_version_major}/${pythia_version}.tgz"
        tar xzvf "${pythia_version}.tgz"
        rm "${pythia_version}.tgz"
        cd $pythia_version
        make

        cd $this_dir
    fi

    # Link pythia installation
    export PYTHIA8="${PYTHIA_DIR}"
    export PYTHIA8DATA="${PYTHIA_DIR}/share/Pythia8/xmldoc"
    export LD_LIBRARY_PATH="${PYTHIA_DIR}/lib:${LD_LIBRARY_PATH}"

    # If Delphes not installed yet, do so
    if [ -d "$DELPHES_DIR" ]; then
        echo "Delphes already installed"
    else
        echo "Installing Delphes"
        cd $SOFTWARE_DIR
        wget "http://cp3.irmp.ucl.ac.be/downloads/${delphes_version}.tar.gz"
        tar -zxf "${delphes_version}.tar.gz"
        rm "${delphes_version}.tar.gz"
        cd $delphes_version
        make -j4
        make -j4 HAS_PYTHIA8=true DelphesPythia8

        cp $this_dir/myprocess_ttbar.C $DELPHES_DIR/examples
        cp $this_dir/pythia_ttbar.cmnd $DELPHES_DIR/cards

        cd $this_dir
    fi

    export LD_LIBRARY_PATH="${DELPHES_DIR}:${LD_LIBRARY_PATH}"
}
action