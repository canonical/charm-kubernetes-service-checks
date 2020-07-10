import logging
import ssl
import os

from charmhelpers.fetch import snap
from charmhelpers.core import host
from charmhelpers.contrib.charmsupport.nrpe import NRPE

class KSCHelper():
    def __init__(self, config, state):
        """Initialize the Helper with the config and state"""
        self.config = config
        self.state = state

    def configure(self):
        """Refresh configuration data"""
        pass

    @property
    def kubernetes_api_address(self):
        return self.state.kube_api_endpoint.get("hostname", None)

    @property
    def kubernetes_api_port(self):
        return self.state.kube_api_endpoint.get("port", None)

    @property
    def client_token(self):
        token = None
        for _, creds in self.state.kube_control.get("creds", {}).items():
            token = creds.get("client_token", None)
        return token

    @property
    def trusted_ssl_cert(self):
        return self.config.get("trusted_ssl_cert")

    def kuberntes_cert_path(self):
        return "/etc/ssl/certs/ca-certificates.crt"

    @property
    def plugins_dir(self):
        return '/usr/local/lib/nagios/plugins/'

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

    def install_kubectl(self):
        """ Attempt to install kubectl

        :returns: bool, indicating whether or not successful
        """
        # snap retry is excessive
        snap.SNAP_NO_LOCK_RETRY_DELAY = 0.5
        snap.SNAP_NO_LOCK_RETRY_COUNT = 3
        try:
            channel = self.config['channel']
            snap.snap_install("kubectl",
                              "--classic",
                              "--channel={}".format(channel)
                              )
            return True
        except snap.CouldNotAcquireLockException:
            return False
