"""Charm unit tests."""
import os
from pathlib import Path
import unittest


import mock
import yaml
import setuppath  # noqa:F401

from charm import Kubernetes_Service_ChecksCharm  # noqa:I100
import ops.main
from ops.testing import Harness

TEST_KUBE_CONTOL_RELATION_DATA = {"creds":
                                   """{"system:node:juju-62684f-0":
                                      {"client_token": "DECAFBADBEEF",
                                       "kubelet_token": "ABCDEF012345",
                                       "proxy_token": "BADC0FFEEDAD",
                                       "scope": "kubernetes-worker/0"}
                                   }"""  # noqa:E127
                                  }
TEST_KUBE_API_ENDPOINT_RELATION_DATA = {"hostname": "1.1.1.1",
                                        "port": "1111"}


class TestKubernetes_Service_ChecksCharm(unittest.TestCase):  # noqa:N801
    """Test Kubernetes Service Checks Charm Code."""

    @classmethod
    def setUpClass(cls):
        """Prepare class fixture."""
        # Stop unit test from calling fchown
        fchown_patcher = mock.patch("os.fchown")
        cls.mock_fchown = fchown_patcher.start()
        chown_patcher = mock.patch("os.chown")
        cls.mock_chown = chown_patcher.start()

        # Stop charmhelpers host from logging via debug log
        host_log_patcher = mock.patch("charmhelpers.core.host.log")
        cls.mock_juju_log = host_log_patcher.start()

        # Stop charmhelpers snap from logging via debug log
        snap_log_patcher = mock.patch("charmhelpers.fetch.snap.log")
        cls.mock_snap_log = snap_log_patcher.start()

        charm_logger_patcher = mock.patch("charm.logging")
        cls.mock_charm_log = charm_logger_patcher.start()

        lib_logger_patcher = mock.patch("lib.lib_kubernetes_service_checks.logging")
        cls.mock_lib_logger = lib_logger_patcher.start()

        # Prevent charmhelpers from calling systemctl
        host_service_patcher = mock.patch("charmhelpers.core.host.service_stop")
        cls.mock_service_stop = host_service_patcher.start()
        host_service_patcher = mock.patch("charmhelpers.core.host.service_start")
        cls.mock_service_start = host_service_patcher.start()
        host_service_patcher = mock.patch("charmhelpers.core.host.service_restart")
        cls.mock_service_restart = host_service_patcher.start()

        # Setup mock JUJU Environment variables
        os.environ["JUJU_UNIT_NAME"] = "mock/0"
        os.environ["JUJU_CHARM_DIR"] = "."

    def setUp(self):
        """Prepare tests."""
        self.harness = Harness(Kubernetes_Service_ChecksCharm)
        # Mock config_get to return default config
        with open(ops.main._get_charm_dir() / Path("config.yaml"), "r") as config_file:
            config = yaml.safe_load(config_file)
        charm_config = {}

        for key, _ in config["options"].items():
            charm_config[key] = config["options"][key]["default"]

        self.harness._backend._config = charm_config

    def test_harness(self):
        """Verify harness."""
        self.harness.begin()
        self.assertFalse(self.harness.charm.state.installed)

    @mock.patch("charmhelpers.fetch.snap.subprocess.check_call")
    def test_install(self, mock_snap_subprocess):
        """Test response to an install event."""
        mock_snap_subprocess.return_value = 0
        mock_snap_subprocess.side_effect = None

        self.harness.begin()
        self.harness.charm.on.install.emit()

        self.assertEqual(self.harness.charm.unit.status.name, "maintenance")
        self.assertEqual(self.harness.charm.unit.status.message, "Install complete")
        self.assertTrue(self.harness.charm.state.installed)

    def test_config_changed(self):
        """Test response to config changed event."""
        self.harness.set_leader(True)
        self.harness.populate_oci_resources()
        self.harness.begin()
        self.harness.charm.check_charm_status = mock.MagicMock()
        self.harness.charm.state.installed = True
        self.harness.charm.on.config_changed.emit()
        self.harness.charm.check_charm_status.assert_called_once()

    def test_start_not_installed(self):
        """Test response to start event without install state."""
        self.harness.begin()
        self.harness.charm.on.start.emit()
        self.assertFalse(self.harness.charm.state.started)

    def test_start_not_configured(self):
        """Test response to start event without configured state."""
        self.harness.begin()
        self.harness.charm.state.installed = True
        self.harness.charm.on.start.emit()
        self.assertFalse(self.harness.charm.state.started)

    def test_start(self):
        """Test response to start event."""
        self.harness.begin()
        self.harness.charm.state.installed = True
        self.harness.charm.state.configured = True
        self.harness.charm.on.start.emit()
        self.assertTrue(self.harness.charm.state.started)
        self.assertEqual(self.harness.charm.unit.status.name, "active")

    def test_on_kube_api_endpoint_relation_changed(self):
        """Check kube-api-endpoint relation changed handling."""
        relation_id = self.harness.add_relation('kube-api-endpoint', 'kubernetes-master')
        remote_unit = "kubernetes-master/0"
        self.harness.begin()
        self.harness.charm.check_charm_status = mock.MagicMock()
        self.harness.add_relation_unit(relation_id, remote_unit)
        self.harness.update_relation_data(relation_id, remote_unit, TEST_KUBE_API_ENDPOINT_RELATION_DATA)

        self.harness.charm.check_charm_status.assert_called_once()
        self.assertEqual(self.harness.charm.helper.kubernetes_api_address, "1.1.1.1")
        self.assertEqual(self.harness.charm.helper.kubernetes_api_port, "1111")

    def test_on_kube_control_relation_changed(self):
        """Check kube-control relation changed handling."""
        relation_id = self.harness.add_relation('kube-control', 'kubernetes-master')
        remote_unit = "kubernetes-master/0"
        self.harness.begin()
        self.harness.charm.check_charm_status = mock.MagicMock()
        self.harness.add_relation_unit(relation_id, remote_unit)
        self.harness.update_relation_data(relation_id, remote_unit, TEST_KUBE_CONTOL_RELATION_DATA)

        self.harness.charm.check_charm_status.assert_called_once()
        assert self.harness.charm.helper.kubernetes_client_token == "DECAFBADBEEF"

    def test_nrpe_external_master_relation_joined(self):
        """Check that nrpe.configure is True after nrpe relation joined."""
        relation_id = self.harness.add_relation('nrpe-external-master', 'nrpe')
        remote_unit = "nrpe/0"
        self.harness.begin()
        self.assertFalse(self.harness.charm.state.nrpe_configured)
        self.harness.charm.check_charm_status = mock.MagicMock()
        self.harness.add_relation_unit(relation_id, remote_unit)

        self.harness.charm.check_charm_status.assert_called_once()
        self.assertTrue(self.harness.charm.state.nrpe_configured)

    @mock.patch("ops.model.RelationData")
    def test_nrpe_external_master_relation_departed(self, mock_relation_data):
        """Check that nrpe.configure is False after nrpe relation departed."""
        mock_relation_data.return_value.__getitem__.return_value = {}
        self.harness.begin()
        self.harness.charm.check_charm_status = mock.MagicMock()
        self.emit("nrpe_external_master_relation_departed")
        self.harness.charm.check_charm_status.assert_called_once()

        self.assertFalse(self.harness.charm.state.nrpe_configured)

    def test_check_charm_status_kube_api_endpoint_relation_missing(self):
        """Check that the chatm blocks without kube-api-endpoint relation."""
        self.harness.begin()
        self.harness.charm.state.kube_control.update(TEST_KUBE_CONTOL_RELATION_DATA)
        self.harness.charm.state.nrpe_configured = True
        self.harness.charm.check_charm_status()

        self.assertFalse(self.harness.charm.state.configured)
        self.assertEqual(self.harness.charm.unit.status.name, "blocked")
        self.assertEqual(self.harness.charm.unit.status.message, "missing kube-api-endpoint relation")

    def test_check_charm_status_kube_control_relation_missing(self):
        """Check that the charm blocks without kube-control relation."""
        self.harness.begin()
        self.harness.charm.state.kube_api_endpoint.update(TEST_KUBE_API_ENDPOINT_RELATION_DATA)
        self.harness.charm.state.nrpe_configured = True
        self.harness.charm.check_charm_status()

        self.assertFalse(self.harness.charm.state.configured)
        self.assertEqual(self.harness.charm.unit.status.name, "blocked")
        self.assertEqual(self.harness.charm.unit.status.message, "missing kube-control relation")

    def test_check_charm_status_nrpe_relation_missing(self):
        """Check that the charm bloack without nrpe relation."""
        self.harness.begin()
        self.harness.charm.state.kube_control.update(TEST_KUBE_CONTOL_RELATION_DATA)
        self.harness.charm.state.kube_api_endpoint.update(TEST_KUBE_API_ENDPOINT_RELATION_DATA)
        self.harness.charm.check_charm_status()

        self.assertFalse(self.harness.charm.state.configured)
        self.assertEqual(self.harness.charm.unit.status.name, "blocked")
        self.assertEqual(self.harness.charm.unit.status.message, "missing nrpe-external-master relation")

    def test_check_charm_status_configured(self):
        """Check the charm becomes configured."""
        self.harness.begin()
        self.harness.charm.helper.configure = mock.MagicMock()
        self.harness.charm.state.kube_control.update(TEST_KUBE_CONTOL_RELATION_DATA)
        self.harness.charm.state.kube_api_endpoint.update(TEST_KUBE_API_ENDPOINT_RELATION_DATA)
        self.harness.charm.state.nrpe_configured = True
        self.harness.charm.check_charm_status()

        self.harness.charm.helper.configure.assert_called_once()
        self.assertTrue(self.harness.charm.state.configured)

    def emit(self, event):
        """Emit the named hook on the charm."""
        self.harness.charm.framework.reemit()

        if "_relation_" in event:
            relation_name = event.split("_relation")[0].replace("_", "-")
            with mock.patch.dict(
                "os.environ",
                {
                    "JUJU_RELATION": relation_name,
                    "JUJU_RELATION_ID": "1",
                    "JUJU_REMOTE_APP": "mock",
                    "JUJU_REMOTE_UNIT": "mock/0",
                },
            ):
                ops.main._emit_charm_event(self.harness.charm, event)
        else:
            ops.main._emit_charm_event(self.harness.charm, event)


if __name__ == "__main__":
    unittest.main()
