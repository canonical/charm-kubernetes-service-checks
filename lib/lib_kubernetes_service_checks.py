import logging

from charmhelpers.core import host
from charmhelpers.contrib.charmsupport.nrpe import NRPE

class KSCHelper():
    def __init__(self, config):
        """Initialize the Helper with the config"""
        self.charm_config = config

    def configure(self):
        """Refresh configuration data"""
        logging.info("Configuring Kubernetes Service Checks")

    def update_k8s_endpoint(self, k8s_address, k8s_port):
        self.k8s_endpoint = "https://{}:{}".format(k8s_address, k8s_port)

    def render_kube_config(self, creds):
        """Render the Nagios .kube/config from template"""
        render(source='kube.config', target=self.kubeconfig, context=creds,
               owner='nagios', group='nagios')
        # TOFIX: render the config to the host?

    def update_plugins(self):
        charm_plugin_dir = os.path.join(hookenv.charm_dir(), 'files', 'plugins/')
        host.rsync(charm_plugin_dir, self.plugins_dir, options=['--executability'])

    def render_checks(self):
        nrpe = NRPE()
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)
        self.update_plugins()

        k8s_check_command = os.path.join(self.plugins_dir, 'check_k8s_services.py')
        #check_command = '{} --warn {} --crit {} --skip-aggregates {} {}'.format(
        #    k8s_check_command, self.nova_warn, self.nova_crit, self.nova_skip_aggregates,
        #    self.skip_disabled).strip()
        #nrpe.add_check(shortname='nova_services',
        #               description='Check that enabled Nova services are up',
        #               check_cmd=check_command,
        #               )

# TODO: get_credentials - either from a relation or from the config - Goes in Charm
#    creds = get_credentials()
#    if not creds:
#        return