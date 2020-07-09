import os
import unittest
import subprocess
import mock
import yaml

from pathlib import Path

import setuppath  # noqa:F401
from charm import Kubernetes_Service_ChecksCharm

#from operator_fixtures import OperatorTestCase
import ops.main
from ops.testing import Harness

#class TestCharm(OperatorTestCase):
class TestKubernetes_Service_ChecksCharm(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Setup class fixture"""

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
        """Setup tests"""
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
        # check that kubectl snap install is called
        channel = self.harness._backend._config["channel"]

#        mock_snap_subprocess.assert_called_with(["snap",
#                                                 "install",
#                                                 "--classic",
#                                                 "--channel={}".format(channel),
#                                                 "kubectl"], env=os.environ)
        self.assertEqual(self.harness.charm.unit.status.name, "maintenance")
        self.assertEqual(self.harness.charm.unit.status.message, "Install complete")

        self.assertTrue(self.harness.charm.state.installed)

#    @mock.patch("charmhelpers.fetch.snap.subprocess.check_call")
#    def test_install_snap_failure(self, mock_snap_subprocess):
#        """Test response to a failed install event."""
#        error = subprocess.CalledProcessError("cmd", "Install failed")
#        error.returncode = 1
#        mock_snap_subprocess.return_value = 1
#        mock_snap_subprocess.side_effect = error

#        self.harness.begin()
#        self.harness.charm.on.install.emit()
#        self.assertEqual(self.harness.charm.unit.status.name, "blocked")
#        self.assertEqual(self.harness.charm.unit.status.message, "kubectl failed to install")

    def test_config_changed(self):
        """Test response to config changed event."""
        self.harness.set_leader(True)
        self.harness.populate_oci_resources()
        self.harness.begin()
        self.harness.charm.state.installed = True
        self.harness.charm.on.config_changed.emit()
        self.assertTrue(self.harness.charm.state.configured)
        # TODO: check that KSCHelper update is called

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


if __name__ == "__main__":
    unittest.main()
