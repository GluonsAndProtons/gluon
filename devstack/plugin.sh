# plugin.sh - DevStack plugin.sh dispatch script for gluon

gluon_debug() {
    if [ ! -z "$GLUON_DEVSTACK_DEBUG" ] ; then
	"$@" || true # a debug command failing is not a failure
    fi
}

# For debugging purposes, highlight gluon sections
gluon_debug tput setab 1

name=gluon

# The server

GITREPO['gluon']=${GLUON_REPO:-https://github.com/GluonsAndProtons/gluon.git}
GITBRANCH['gluon']=${GLUON_BRANCH:-master}
GITDIR['gluon']=$DEST/gluon

# The client API libraries
GITREPO['gluonlib']=${GLUONLIB_REPO:-https://github.com/GluonsAndProtons/gluonlib.git}
GITBRANCH['gluonlib']=${GLUONLIB_BRANCH:-master}
GITDIR['gluonlib']=$DEST/gluonlib

# The Nova client plugin
GITREPO['gluon-nova']=${GLUON_NOVA_REPO:-https://github.com/iawells/gluon-nova.git}
GITBRANCH['gluon-nova']=${GLUON_NOVA_BRANCH:-master}
GITDIR['gluon-nova']=$DEST/gluon-nova

function pre_install_me {
    :
}

gluon_libs_executed=''
function install_gluon_libs {
    if [ -z "$gluon_libs_executed" ] ; then
        gluon_libs_executed=1 
(

	git_clone_by_name gluonlib # $GLUONLIB_REPO ${GITLIB['gluonlib']} $GLUONLIB_BRANCH
        cd ${GITDIR['gluonlib']}
	setup_dev_lib 'gluonlib'

	git_clone_by_name 'gluon-nova' #  $GLUON_NOVA_REPO ${GITDIR['gluon-nova']} $GLUON_NOVA_BRANCH
        cd ${GITDIR['gluon-nova']}
	setup_dev_lib 'gluon-nova'
)
    fi
}

function install_me {
    git_clone_by_name 'gluon' # $GLUON_REPO ${GITDIR['gluon']} $GLUON_BRANCH
    setup_develop ${GITDIR['gluon']}
}

function init_me {
    run_process $name "'$GLUON_BINARY' --config-file $GLUON_CONFIG_FILE"
}

function configure_me {
    # Nova needs adjusting from what it thinks it's doing
    iniset $NOVA_CONF DEFAULT network_api_class "gluon_nova.api.API"

    # This tells the Neutron backend how to talk to Neutron
    # TODO should be in keeping with register_config_opts
    iniset ${GLUON_CONFIG_FILE} neutron username "$ADMIN_USERNAME"
    iniset ${GLUON_CONFIG_FILE} neutron password "$ADMIN_PASSWORD"
    iniset ${GLUON_CONFIG_FILE} neutron tenant "$ADMIN_TENANT"
    iniset ${GLUON_CONFIG_FILE} neutron auth_url "$KEYSTONE_URL"

    # This tells Gluon where to reside
    iniset ${GLUON_CONFIG_FILE} api host "$GLUON_HOST"
    iniset ${GLUON_CONFIG_FILE} api port $GLUON_PORT"
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

gluon_debug tput setab 9
