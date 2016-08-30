# plugin.sh - DevStack plugin.sh dispatch script for proton

PROTON_DIR=$(cd $(dirname $BASH_SOURCE)/.. && pwd)

proton_debug() {
    if [ ! -z "$PROTON_DEVSTACK_DEBUG" ] ; then
	"$@" || true # a debug command failing is not a failure
    fi
}

# For debugging purposes, highlight proton sections
proton_debug tput setab 1

name=proton

# The server

GITREPO['proton']=${PROTON_REPO:-https://github.com/GluonsAndProtons/proton.git}
GITBRANCH['proton']=${PROTON_BRANCH:-master}
GITDIR['proton']=$DEST/proton

function pre_install_me {
    :
}

function install_me {
    git_clone_by_name 'proton'
    setup_develop "$PROTON_DIR"
}

function init_me {
    run_process $name "'$PROTON_BINARY' --config-file '$PROTON_CONFIG_FILE'"
}

function configure_me {
    sudo install -d -o "$STACK_USER" "$PROTON_CONF_DIR"

    # This tells Proton where to reside
    iniset ${PROTON_CONFIG_FILE} api host "$PROTON_HOST"
    iniset ${PROTON_CONFIG_FILE} api port "$PROTON_PORT"
}

function shut_me_down {
    stop_process $name
}

# check for service enabled
if is_service_enabled $name; then

    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then
        # Set up system services
        echo_summary "Configuring system services $name"
	pre_install_me

    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing $name"
        install_me

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        # Configure after the other layer 1 and 2 services have been configured
        echo_summary "Configuring $name"
        configure_me

    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # Initialize and start the service
        echo_summary "Initializing $name"
        init_me
    fi

    if [[ "$1" == "unstack" ]]; then
        # Shut down services
	shut_me_down
    fi

    if [[ "$1" == "clean" ]]; then
        # Remove state and transient data
        # Remember clean.sh first calls unstack.sh
        # no-op
        :
    fi
fi

proton_debug tput setab 9
