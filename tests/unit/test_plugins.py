"""Unit tests for Kubernetes Service Checks NRPE Plugins."""
import unittest

import check_kubernetes_api
import mock


class TestKSCPlugins(unittest.TestCase):
    """Test cases for Kubernetes Service Checks NRPE plugins."""

    @mock.patch("check_kubernetes_api.sys.exit")
    @mock.patch("check_kubernetes_api.print")
    def test_nagios_exit(self, mock_print, mock_sys_exit):
        """Test the nagios_exit function."""
        msg = "Test message"
        for code, status in check_kubernetes_api.NAGIOS_STATUS.items():
            expected_output = "{}: {}".format(status, msg)
            check_kubernetes_api.nagios_exit(code, msg)

            mock_print.assert_called_with(expected_output)
            mock_sys_exit.assert_called_with(code)

    @mock.patch("check_kubernetes_api.urllib3.PoolManager")
    @mock.patch("check_kubernetes_api.os.path.exists")
    def test_kubernetes_health_ssl(self,
                                   mock_os_path_exists,
                                   mock_http_pool_manager):
        """Test the check k8s health function called with expected ssl params."""
        host_address = "https://1.1.1.1:1111"
        token = "0123456789abcdef"
        ssl_ca = None

        mock_http_pool_manager.return_value.status = 200
        mock_http_pool_manager.return_value.data = b"ok"

        check_kubernetes_api.check_kubernetes_health(
            host_address,
            token,
            ssl_ca
        )
        mock_http_pool_manager.assert_called_with(
            cert_reqs="CERT_NONE",
            assert_hostname=False
        )

        ssl_ca = "test/cert/path"
        mock_os_path_exists.return_value = True
        check_kubernetes_api.check_kubernetes_health(
            host_address,
            token,
            ssl_ca
        )
        mock_http_pool_manager.assert_called_with(
            cert_reqs="CERT_REQUIRED",
            ca_file=ssl_ca
        )

    @mock.patch("check_kubernetes_api.urllib3.PoolManager")
    @mock.patch("check_kubernetes_api.os.path.exists")
    def test_kubernetes_health_status(self,
                                      mock_os_path_exists,
                                      mock_http_pool_manager):
        """Test kubernetes health function."""
        host_address = "https://1.1.1.1:1111"
        token = "0123456789abcdef"
        ssl_ca = "test/cert/path"

        mock_os_path_exists.return_value = True
        mock_http_pool_manager.return_value.request.return_value.status = 200
        mock_http_pool_manager.return_value.request.return_value.data = b"ok"

        # verify status OK
        status, _ = check_kubernetes_api.check_kubernetes_health(
            host_address,
            token,
            ssl_ca
        )
        self.assertEqual(status, check_kubernetes_api.NAGIOS_STATUS_OK)
        mock_http_pool_manager.return_value.request.assert_called_once_with(
            "GET",
            "{}/healthz".format(host_address),
            headers={"Authorization": "Bearer {}".format(token)}
        )

        mock_http_pool_manager.return_value.request.return_value.status = 500
        mock_http_pool_manager.return_value.request.return_value.data = b"ok"
        status, _ = check_kubernetes_api.check_kubernetes_health(
            host_address,
            token,
            ssl_ca
        )
        self.assertEqual(status, check_kubernetes_api.NAGIOS_STATUS_CRITICAL)

        mock_http_pool_manager.return_value.request.return_value.status = 200
        mock_http_pool_manager.return_value.request.return_value.data = b"not ok"
        status, _ = check_kubernetes_api.check_kubernetes_health(
            host_address,
            token,
            ssl_ca
        )
        self.assertEqual(status, check_kubernetes_api.NAGIOS_STATUS_WARNING)
