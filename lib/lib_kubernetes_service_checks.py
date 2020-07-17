"""Kubernetes Service Checks Helper Library."""
import base64
import json
import logging
import os
import subprocess

from charmhelpers.contrib.charmsupport.nrpe import NRPE
from charmhelpers.core import hookenv, host
from charmhelpers.fetch import snap

CERT_FILE = "/usr/local/share/ca-certificates/kubernetes-service-checks.crt"
NAGIOS_PLUGINS_DIR = "/usr/local/lib/nagios/plugins/"


class KSCHelper():
    """Kubernetes Service Checks Helper Class."""

    def __init__(self, config, state):
        """Initialize the Helper with the charm config and state."""
        self.config = config
        self.state = state

    @property
    def kubernetes_api_address(self):
        """Get kubernetes api hostname."""
        return self.state.kube_api_endpoint.get("hostname", None)

    @property
    def kubernetes_api_port(self):
        """Get kubernetes api port."""
        return self.state.kube_api_endpoint.get("port", None)

    @property
    def kubernetes_client_token(self):
        """Get kubernetes client token."""
        try:
            data = json.loads(self.state.kube_control.get("creds", "{}"))
        except json.decoder.JSONDecodeError:
            data = {}
        for creds in data.values():
            token = creds.get("client_token", None)
            if token:
                return token
        return None

    @property
    def use_tls_cert(self):
        """Check if SSL cert is provided for use."""
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
        """Get cert file path."""
        return CERT_FILE

    @property
    def plugins_dir(self):
        """Get nagios plugins directory."""
        return NAGIOS_PLUGINS_DIR

    def restart_nrpe_service(self):
        """Restart nagios-nrpe-server service."""
        host.service_restart('nagios-nrpe-server')

    def update_tls_certificates(self):
        """Write the trusted ssl certificate to the CERT_FILE."""
        if self._ssl_certificate:
            cert_content = base64.b64decode(self._ssl_certificate).decode()
            try:
                logging.debug('Writing ssl ca cert to {}'.format(self.ssl_cert_path))
                with open(self.ssl_cert_path, "w") as f:
                    f.write(cert_content)
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
        """Refresh configuration data."""
        self.update_plugins()
        self.render_checks()

    def update_plugins(self):
        """Rsync plugins to the plugin directory."""
        charm_plugin_dir = os.path.join(hookenv.charm_dir(), "files", "plugins/")
        host.rsync(charm_plugin_dir, self.plugins_dir, options=["--executability"])

    def render_checks(self):
        """Render nrpe checks."""
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
            if not self.use_tls_cert:
                check_command += " -d"

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
        """Attempt to install kubectl.

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
