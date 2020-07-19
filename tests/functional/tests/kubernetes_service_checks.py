"""Charm Kubernetes Service Checks Functional Tests."""
import concurrent.futures
import logging
import re
import time
import unittest

from juju.errors import JujuAPIError
import zaza.model


class TestBase(unittest.TestCase):
    """Base Class for charm functional tests."""

    @classmethod
    def setUpClass(cls):
        """Run setup for tests."""
        cls.model_name = zaza.model.get_juju_model()
        cls.application_name = "kubernetes-service-checks"

    def setUp(self):
        """Set up  functional tests & ensure all relations added."""
        for local_relation_name, remote_relation_unit in [
            ("kube-api-endpoint", "kubernetes-master"),
            ("kube-control", "kubernetes-master"),
            ("nrpe-external-master", "nrpe"),
        ]:
            logging.info("Adding relation {} with {}".format(local_relation_name, remote_relation_unit))
            try:
                zaza.model.add_relation(
                    self.application_name, local_relation_name, remote_relation_unit, self.model_name
                )
            except JujuAPIError as e:
                p = r"^.*cannot\ add\ relation.*already\ exists"
                if re.search(p, e.message):
                    pass
                else:
                    raise (e)
        zaza.model.block_until_wl_status_info_starts_with(self.application_name, status="Unit is ready", timeout=200)


class TestChecks(TestBase):
    """Tests for availability and usefulness of nagios checks."""

    expected_checks = ["check_k8s_api_health.cfg", "check_k8s_api_cert_expiration.cfg"]
    checks_dir = "/etc/nagios/nrpe.d/"
    expected_plugins = ["check_kubernetes_api.py"]
    plugins_dir = "/usr/local/lib/nagios/plugins/"

    # TODO: Need testing around setting the trusted_ssl_ca cert
    #    - does it get written to /etc/ssl/certs/ca-certificates.crt?
    #    - does the k8s check plugin see it and use it for verification?

    def test_check_plugins_exist(self):
        """Verify that kubernetes service checks plugins are found."""
        fail_messages = []
        for plugin in self.expected_plugins:
            pluginpath = self.plugins_dir + plugin
            response = zaza.model.run_on_unit(
                "kubernetes-service-checks/0", '[ -f "{}" ]'.format(pluginpath), model_name=self.model_name, timeout=30
            )
            if response["Code"] != "0":
                fail_messages.append("Missing plugin: {}".format(pluginpath))
                continue

            # check executable
            response = zaza.model.run_on_unit(
                "kubernetes-service-checks/0", '[ -x "{}" ]'.format(pluginpath), model_name=self.model_name, timeout=30
            )

            if response["Code"] != "0":
                fail_messages.append("Plugin not executable: {}".format(pluginpath))

        if fail_messages:
            self.fail("\n".join(fail_messages))

    def test_checks_exist(self):
        """Verify that kubernetes service checks nrpe checks exist."""
        fail_messages = []
        for check in self.expected_checks:
            checkpath = self.checks_dir + check
            response = zaza.model.run_on_unit(
                "kubernetes-service-checks/0", '[ -f "{}" ]'.format(checkpath), model_name=self.model_name, timeout=30
            )
            if response["Code"] != "0":
                fail_messages.append("Missing check: {}".format(checkpath))
        if fail_messages:
            self.fail("\n".join(fail_messages))


class TestRelations(TestBase):
    """Tests for charm behavior adding and removing relations."""

    def _get_relation_id(self, remote_application, interface_name):
        return zaza.model.get_relation_id(
            self.application_name, remote_application, model_name=self.model_name, remote_interface_name=interface_name
        )

    def test_remove_kube_api_endpoint(self):
        """Test removing kube-api-endpoint relation."""
        rel_name = "kube-api-endpoint"
        remote_app = "kubernetes-master"
        logging.info("Removing kube-api-endpoint relation")

        zaza.model.remove_relation(self.application_name, rel_name, remote_app, self.model_name)
        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name, status="missing kube-api-endpoint relation", timeout=180
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become blocked")

        logging.info("Waiting for relation {} to be destroyed".format(rel_name))
        timeout = time.time() + 600
        while self._get_relation_id(remote_app, rel_name) is not None:
            time.sleep(5)
            if time.time() > timeout:
                self.fail("Timed out waiting for the relation {} to be destroyed".format(rel_name))

    def test_remove_kube_control(self):
        """Test removing kube-control relation."""
        rel_name = "kube-control"
        remote_app = "kubernetes-master"
        logging.info("Removing kube-control relation")

        zaza.model.remove_relation(self.application_name, rel_name, remote_app, self.model_name)

        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name, status="missing kube-control relation", timeout=180
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become blocked")

        logging.info("Waiting for relation {} to be destroyed".format(rel_name))
        timeout = time.time() + 600
        while self._get_relation_id(remote_app, rel_name) is not None:
            time.sleep(5)
            if time.time() > timeout:
                self.fail("Timed out waiting for the relation {} to be destroyed".format(rel_name))

    def test_remove_nrpe_external_master(self):
        """Test removing nrpe-external-master relation."""
        rel_name = "nrpe-external-master"
        remote_app = "nrpe"
        logging.info("Removing nrpe-external-master relation")

        zaza.model.remove_relation(self.application_name, rel_name, remote_app, self.model_name)

        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name, status="missing nrpe-external-master relation", timeout=180
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become blocked")

        logging.info("Waiting for relation {} to be destroyed".format(rel_name))
        timeout = time.time() + 600
        while self._get_relation_id(remote_app, rel_name) is not None:
            time.sleep(5)
            if time.time() > timeout:
                self.fail("Timed out waiting for the relation {} to be destroyed".format(rel_name))
