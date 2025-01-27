#!/usr/bin/env bash
action() {
    # Set version of used software
    local madgraph_download_dir="https://launchpad.net/mg5amcnlo/3.0/3.6.x/+download"
    local madgraph_download_file="MG5_aMC_v3.5.6"

    local pythia_download_dir="https://pythia.org/download/pythia83"
    local pythia_download_file="pythia8311"

    local delphes_download_dir="http://cp3.irmp.ucl.ac.be/downloads"
    local delphes_download_file="Delphes-3.5.0"

    # Set main directories
    local shell_is_zsh="$( [ -z "${ZSH_VERSION}" ] && echo "false" || echo "true" )"
    local this_file="$( ${shell_is_zsh} && echo "${(%):-%x}" || echo "${BASH_SOURCE[0]}" )"
    local this_dir="$( cd "$( dirname "${this_file}" )" && pwd )"

    # set PYTHONPATH
    export PYTHONPATH="${this_dir}:${PYTHONPATH}"

    CONFIG_FILE="${this_dir}/.config"

    # Function to read the output directory from the config file
    read_config() {
        if [[ -f $CONFIG_FILE ]]; then
            source $CONFIG_FILE
        else
            export GEN_OUT=""
        fi
    }

    # Function to write the output directory to the config file
    write_config() {
        echo "export GEN_OUT=\"$GEN_OUT\"" > $CONFIG_FILE
    }

    # Prompt user for input if GEN_OUT is not set
    prompt_user() {
        read -p "Enter the output directory: " user_input
        if [[ -n $user_input ]]; then
            export GEN_OUT=$user_input
            write_config
        fi
    }

    # Main script execution
    read_config

    if [[ -z $GEN_OUT ]]; then
        echo "No output directory configured."
        prompt_user
    fi

    # Use the GEN_OUT in your script
    echo "Using output directory: $GEN_OUT"

    # Set code and law area
    export GEN_CODE="${this_dir}"
    export GEN_SLURM="${GEN_OUT}/slurm"

    export LAW_HOME="${this_dir}/.law"
    export LAW_CONFIG_FILE="${this_dir}/law.cfg"

    # Setup software directories
    export SOFTWARE_DIR="${this_dir}/software"
    mkdir -p $SOFTWARE_DIR

    export MADGRAPH_DIR="${SOFTWARE_DIR}/${madgraph_download_file//./_}"
    export PYTHIA_DIR="${SOFTWARE_DIR}/${pythia_download_file}"
    export DELPHES_DIR="${SOFTWARE_DIR}/${delphes_download_file}"

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

    # law setup
    source "$( law completion )" ""

    # If Pythia not installed yet, do so
    if [ -d "$MADGRAPH_DIR" ]; then
        echo "Madgraph already installed"
    else
        echo "Installing Madgraph"
        cd $SOFTWARE_DIR
        wget ${madgraph_download_dir}/${madgraph_download_file}.tar.gz
        tar -xf "${madgraph_download_file}.tar.gz"
        rm "${madgraph_download_file}.tar.gz"
        
        cd $this_dir
    fi

    # If Pythia not installed yet, do so
    if [ -d "$PYTHIA_DIR" ]; then
        echo "Pythia already installed"
    else
        echo "Installing Pythia"
        cd $SOFTWARE_DIR
        wget "${pythia_download_dir}/${pythia_download_file}.tgz"
        tar xzvf "${pythia_download_file}.tgz"
        rm "${pythia_download_file}.tgz"
        cd $pythia_download_file
        make -j4

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
        wget "${delphes_download_dir}/${delphes_download_file}.tar.gz"
        tar -zxf "${delphes_download_file}.tar.gz"
        rm "${delphes_download_file}.tar.gz"
        cd $delphes_download_file
        make -j4
        make -j4 HAS_PYTHIA8=true DelphesPythia8

        cd $this_dir
    fi

    export LD_LIBRARY_PATH="${DELPHES_DIR}:${LD_LIBRARY_PATH}"
}
action
