import logging
import ssl
import os

from charmhelpers.fetch import snap
from charmhelpers.core import host
from charmhelpers.contrib.charmsupport.nrpe import NRPE

CERT_FILE = "/usr/local/share/ca-certificates/kubernetes-service-checks.crt"

class KSCHelper():
    def __init__(self, config, state):
        """Initialize the Helper with the config and state"""
        self.config = config
        self.state = state

    def _update_tls_certificates(self):
        if self._ssl_certificate:
            try:
                with open(CERT_FILE, "w") as f:
                    f.write(self._ssl_certificate)
                subprocess.call(['/usr/sbin/update-ca-certificates'])
                return True
            except subprocess.CalledProcessError as e:
                logging.error(e)
                return False
            except PermissionError as e:
                logging.error(e)
                return False

    def configure(self):
        """Refresh configuration data"""
        self.update_plugins()
        self.render_checks()

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
    def kubernetes_cert_path(self):
        return "kubernetes-service-checks.crt"

    @property
    def use_tls_cert(self):
        return self._ssl_certificate is not None

    @property
    def _ssl_certificate(self):
        # TODO: Expand this later to take a cert from a relation or from the config.
        # cert from the relation is to be prioritized
        ssl_cert = self.config.get("trusted_ssl_ca", None)
        if ssl_cert:
            ssl_cert = ssl_cert.strip()
        return ssl_cert

    @property
    def plugins_dir(self):
        return '/usr/local/lib/nagios/plugins/'

    def update_plugins(self):
        """ Rsync the Kubernetes Service Checks charm provided plugins to the
        plugin directory.
        """
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
