"""Tests for Kubernetes Service Checks Helper."""
import base64
import os
import subprocess
import tempfile
import unittest
from subprocess import CalledProcessError

from lib import lib_kubernetes_service_checks

import mock

import yaml


TEST_CERTIFICATE = """-----BEGIN CERTIFICATE-----
MIIDOzCCAiOgAwIBAgIJAPoOXrIwH+miMA0GCSqGSIb3DQEBCwUAMBgxFjAUBgNV
BAMMDTEwLjEzMi4yNTEuNjAwHhcNMjAwNzE3MTMzMzI0WhcNMzAwNzE1MTMzMzI0
WjAYMRYwFAYDVQQDDA0xMC4xMzIuMjUxLjYwMIIBIjANBgkqhkiG9w0BAQEFAAOC
AQ8AMIIBCgKCAQEAqpYVlmT/eRBhCKHaqXjY6EAzvx5GZY0PhL/YGBl9uF8YQGEF
F3k3Ec7pyJMIQblmWxdCPd1uNzHU8mwApiuPG9GtYOK+olqgslLsmOU9LTi6KJWX
x956VxdefXDYvr0B6K/Hdgkb1x//XwvipSV1fZ1MCDIiP/hWKi4CmEq31sVpCBdp
Uiz3qdCzsiGt0f4kbgIJSVtxhWlNJ5MaCOm7gXafkF8OIUTmWhmPp2gH7pfPzzl1
glOX2Z41qwPuz7Jbcxx/z/yGjdPeJTQYoqJfpDpCrT2er5xyRf66HqKx9Ld/FiqM
ZksRwmzF9WvqCBK8WoRmnvFxk1FZPGt6E5gotwIDAQABo4GHMIGEMB0GA1UdDgQW
BBSUCCmRxb4tKD6w8jZ3hHs4ciFizDBIBgNVHSMEQTA/gBSUCCmRxb4tKD6w8jZ3
hHs4ciFizKEcpBowGDEWMBQGA1UEAwwNMTAuMTMyLjI1MS42MIIJAPoOXrIwH+mi
MAwGA1UdEwQFMAMBAf8wCwYDVR0PBAQDAgEGMA0GCSqGSIb3DQEBCwUAA4IBAQBv
BYwILWI/4dGczqG0hcqt8tW04Oi+7y0HxzeI/oaUq/HKfvCz5a+WhpykMKRDJoaZ
aejR2Oc7A0OUnenpvMeIiMcUIetM3Q1Gzx0aU+vqUNNaZlooSSbe3z1VK6bUsYDo
qdKhs+mSyuEticK2SEWjT+ZWpV1rjSd5zRZ/UvC1ZhDNJGZotIIqryQWd3YfYl9l
7JrdzUVCbxs4ywxNp9/I+MJEiBfMHQx8FWr1M2HvLDAm6NZLfM68y5FClzfGpopV
0ARirz1AfbS6xUumyXHOH2qH527PUXFdfYGSn+juDG/dRTENYJ3OPAfWdj4ze1qQ
n3ajLSYPvdyKaztdB1VL
-----END CERTIFICATE-----"""


class TestLibKSCHelper(unittest.TestCase):
    """Unittest class for Kubernetes Service Checks Helper."""

    @classmethod
    def setUpClass(cls):
        """Prepare Class Fixture."""
        # Load default config
        with open("./config.yaml") as default_config:
            cls.config = yaml.safe_load(default_config)

        # set defaults to the config object
        for key in cls.config["options"]:
            if "default" in cls.config["options"][key]:
                cls.config[key] = cls.config["options"][key]["default"]

        # Create test state object
        class FakeStateObject(object):
            kube_api_endpoint = {"hostname": "1.1.1.1", "port": "1111"}
            kube_control = {
                "creds": """{"kube-client": {"client_token": "abcdef0123456789"}}"""
            }
            installed = False
            configured = False
            started = False
            nrpe_configured = False

        cls.state = FakeStateObject()

        # Stop unit test from calling fchown
        fchown_patcher = mock.patch("os.fchown")
        cls.mock_fchown = fchown_patcher.start()
        chown_patcher = mock.patch("os.chown")
        cls.mock_chown = chown_patcher.start()

        # Stop charmhelpers host from logging via debug log
        host_log_patcher = mock.patch("charmhelpers.core.host.log")
        cls.mock_juju_log = host_log_patcher.start()

        host_logger_patcher = mock.patch("lib.lib_kubernetes_service_checks.logging")
        cls.mock_logger = host_logger_patcher.start()

        # Stop charmhelpers snap from logging via debug log
        snap_log_patcher = mock.patch("charmhelpers.fetch.snap.log")
        cls.mock_snap_log = snap_log_patcher.start()

        # Setup a tmpdir
        cls.tmpdir = tempfile.TemporaryDirectory()
        cls.cert_path = os.path.join(cls.tmpdir.name, "kubernetes-service-checks.crt")

        lib_kubernetes_service_checks.CERT_FILE = cls.cert_path
        lib_kubernetes_service_checks.NAGIOS_PLUGINS_DIR = cls.tmpdir.name

    @classmethod
    def tearDownClass(cls):
        """Tear down class fixture."""
        mock.patch.stopall()
        cls.tmpdir.cleanup()

    def setUp(self):
        """Prepare test fixture."""
        self.helper = lib_kubernetes_service_checks.KSCHelper(self.config, self.state)

    def tearDown(self):
        """Clean up test fixture."""
        try:
            os.remove(self.cert_path)
        except FileNotFoundError:
            pass

    def test_kube_api_endpoint_properties(self):
        """Test that hostname and port properties get passed through."""
        # kube_api_endpoint (relation) -> hostname & port
        self.assertEqual(self.helper.kubernetes_api_address, "1.1.1.1")
        self.assertEqual(self.helper.kubernetes_api_port, "1111")

        self.helper.state.kube_api_endpoint = {}
        self.assertEqual(self.helper.kubernetes_api_address, None)
        self.assertEqual(self.helper.kubernetes_api_port, None)

    def test_kube_control_endpoint_properties(self):
        """Test KSCHelper client_token gets passed though."""
        # kube-control (relation) -> kube client token
        self.assertEqual(self.helper.kubernetes_client_token, "abcdef0123456789")

        self.helper.state.kube_control = {}
        self.assertEqual(self.helper.kubernetes_client_token, None)

    @mock.patch("lib.lib_kubernetes_service_checks.subprocess.call")
    def test_update_tls_certificates(self, mock_subprocess):
        """Test that SSL certificates get updated."""
        # returns False when no available trusted_ssl_cert
        self.assertFalse(self.helper.update_tls_certificates())

        # returns True when subprocess successful
        self.helper.config["trusted_ssl_ca"] = base64.b64encode(
            str.encode(TEST_CERTIFICATE)
        )
        self.assertTrue(self.helper.update_tls_certificates())
        with open(self.cert_path, "r") as f:
            self.assertEqual(f.read(), TEST_CERTIFICATE)
        mock_subprocess.assert_called_once_with(["/usr/sbin/update-ca-certificates"])
        mock_subprocess.reset_mock()

        # returns false when subprocess hits an exception
        mock_subprocess.side_effect = CalledProcessError(
            "Command", "Mock Subprocess Call Error"
        )
        self.assertFalse(self.helper.update_tls_certificates())

    def test_render_checks(self):
        """Test that NPRE is called to add KSC checks."""
        # TODO
        pass

    @mock.patch("charmhelpers.fetch.snap.subprocess.check_call")
    def test_install_kubectl(self, mock_snap_subprocess):
        """Test install kubectl snap helper function."""
        self.assertTrue(self.helper.install_kubectl())
        channel = self.config.get("channel")
        mock_snap_subprocess.assert_called_with(
            ["snap", "install", "--classic", "--channel={}".format(channel), "kubectl"],
            env=os.environ,
        )

    @mock.patch("charmhelpers.fetch.snap.subprocess.check_call")
    def test_install_snap_failure(self, mock_snap_subprocess):
        """Test response to a failed install event."""
        error = subprocess.CalledProcessError("cmd", "Install failed")
        error.returncode = 1
        mock_snap_subprocess.return_value = 1
        mock_snap_subprocess.side_effect = error
        self.assertFalse(self.helper.install_kubectl())


if __name__ == "__main__":
    unittest.main()
