import logging
import ssl
import os
import subprocess

from charmhelpers.fetch import snap
from charmhelpers.core import hookenv, host
from charmhelpers.contrib.charmsupport.nrpe import NRPE

CERT_FILE = "/usr/local/share/ca-certificates/kubernetes-service-checks.crt"
NAGIOS_PLUGINS_DIR = "/usr/local/lib/nagios/plugins/"

class KSCHelper():
    def __init__(self, config, state):
        """Initialize the Helper with the config and state"""
        self.config = config
        self.state = state

    @property
    def kubernetes_api_address(self):
        return self.state.kube_api_endpoint.get("hostname", None)

    @property
    def kubernetes_api_port(self):
        return self.state.kube_api_endpoint.get("port", None)

    @property
    def kubernetes_client_token(self):
        try:
            data = eval(self.state.kube_control.get("creds", "{}"))
        except:
            data = {}
        for creds in data.values():
            token = creds.get("client_token", None)
            if token:
                return token
        return None

    @property
    def use_tls_cert(self):
        return bool(self._ssl_certificate)

    @property
    def _ssl_certificate(self):
        # TODO: Expand this later to take a cert from a relation or from the config.
        # cert from the relation is to be prioritized
        ssl_cert = self.config.get("trusted_ssl_ca", None)
        if ssl_cert:
            ssl_cert = ssl_cert.strip()
        return ssl_cert

    @property
    def ssl_cert_path(self):
        return CERT_FILE

    @property
    def plugins_dir(self):
        return NAGIOS_PLUGINS_DIR

    def update_tls_certificates(self):
        """Write the trusted ssl certificate to the CERT_FILE"""
        if self._ssl_certificate:
            try:
                with open(self.ssl_cert_path, "w") as f:
                    # TODO
                    # cert_content = base64.b64decode(self._ssl_certificate).decode()
                    f.write(self._ssl_certificate)
                subprocess.call(['/usr/sbin/update-ca-certificates'])
                return True
            except subprocess.CalledProcessError as e:
                logging.error(e)
                return False
            except PermissionError as e:
                logging.error(e)
                return False
        else:
            logging.error("Trusted SSL Certificate is not defined")
            return False

    def configure(self):
        """Refresh configuration data"""
        self.update_plugins()
        self.render_checks()

    def update_plugins(self):
        """Rsync the Kubernetes Service Checks charm provided plugins to the
        plugin directory.
        """
        charm_plugin_dir = os.path.join(hookenv.charm_dir(), "files", "plugins/")
        host.rsync(charm_plugin_dir, self.plugins_dir, options=["--executability"])

    def render_checks(self):
        nrpe = NRPE()
        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)

        # register basic api health check
        check_k8s_plugin = os.path.join(self.plugins_dir, "check_kubernetes_api.py")
        for check in ["health"]:
            check_command = "{} -H {} -P {} -T {} --check {}".format(
                check_k8s_plugin,
                self.kubernetes_api_address,
                self.kubernetes_api_port,
                self.kubernetes_client_token,
                check
            ).strip()
            # TODO: Add -C if cert check required.

            nrpe.add_check(
                shortname="k8s_api_{}".format(check),
                description="Check Kubernetes API ({})".format(check),
                check_cmd=check_command,
            )

        # register k8s host certificate expiration check
        check_http_plugin = "/usr/lib/nagios/plugins/check_http"
        check_command = "{} -I {} -p {} -C {},{}".format(
            check_http_plugin,
            self.kubernetes_api_address,
            self.kubernetes_api_port,
            self.config.get("tls_warn_days"),
            self.config.get("tls_crit_days")
        ).strip()
        nrpe.add_check(
            shortname="k8s_api_cert_expiration",
            description="Check Kubernetes API ({})".format(check),
            check_cmd=check_command,
        )
        nrpe.write()

    def install_kubectl(self):
        """ Attempt to install kubectl

        :returns: bool, indicating whether or not successful
        """
        # snap retry is excessive
        snap.SNAP_NO_LOCK_RETRY_DELAY = 0.5
        snap.SNAP_NO_LOCK_RETRY_COUNT = 3
        try:
            channel = self.config.get('channel')
            snap.snap_install("kubectl",
                              "--classic",
                              "--channel={}".format(channel)
                              )
            return True
        except snap.CouldNotAcquireLockException:
            return False
