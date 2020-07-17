#!/usr/bin/python3
import argparse
import urllib3
import sys
import os

NAGIOS_STATUS_OK = 0
NAGIOS_STATUS_WARNING = 1
NAGIOS_STATUS_CRITICAL = 2
NAGIOS_STATUS_UNKNOWN = 3

NAGIOS_STATUS = {
    NAGIOS_STATUS_OK: "OK",
    NAGIOS_STATUS_WARNING: "WARNING",
    NAGIOS_STATUS_CRITICAL: "CRITICAL",
    NAGIOS_STATUS_UNKNOWN: "UNKNOWN",
}

def nagios_exit(status, message):
    assert status in NAGIOS_STATUS, "Invalid Nagios status code"
    # prefix status name to message
    output = "{}: {}".format(NAGIOS_STATUS[status], message)
    print(output)  # nagios requires print to stdout, no stderr
    sys.exit(status)

def check_kubernetes_health(k8s_address, client_token, ssl_ca):
    """ Make a call to the <kubernetes-api>/healthz endpoint - the expected
    return value is 'ok'
    :param k8s_address: Address to kube-api-server formatted 'https://<IP>:<PORT>'
    :param client_token: Token for authenticating with the kube-api
    :param ssl_ca: path to SSL CA certificate for authenticating the kube-api cert
    """
    url = k8s_address + "/healthz"
    if ssl_ca is None or not os.path.exists(ssl_ca):
        # perform check without SSL verification
        http = urllib3.PoolManager(
            cert_reqs="CERT_NONE",
            assert_hostname=False
        )
    else:
        http = urllib3.PoolManager(cert_reqs="CERT_REQUIRED", ca_file=ssl_ca)

    try:
        req = http.request(
            "GET",
            url,
            headers={"Authorization": "Bearer {}".format(client_token)}
        )
    except urllib3.exceptions.MaxRetryError as e:
        return NAGIOS_STATUS_CRITICAL, e

    if req.status != 200:
        return NAGIOS_STATUS_CRITICAL, "Unexpected HTTP Response code ({})".format(req.status)
    elif req.data != b"ok":
        return NAGIOS_STATUS_WARNING, "Unexpected Kubernetes healthz status '{}'".format(req.data)
    return NAGIOS_STATUS_OK, "Kubernetes health 'ok'"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check Kubernetes API status",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-H", "--host", dest="host",
        help="Hostname or IP of the kube-api-server"
    )

    parser.add_argument(
        "-P", "--port", dest="port", type=int, default=6443,
        help="Port of the kube-api-server"
    )

    parser.add_argument(
        "-T", "--token", dest="client_token",
        help="Client access token for authenticate with the Kubernetes API"
    )

    check_choices = ["health"]
    parser.add_argument(
        "--check", dest="check", metavar="|".join(check_choices),
        type=str, choices=check_choices,
        default=check_choices[0],
        help="which check to run")

    parser.add_argument(
        "-C", "--trusted-ca-cert", dest="ssl_ca_path", type=str, default=None,
        help="String containing path to the trusted CA certificate"
    )
    args = parser.parse_args()

    checks = {
        "health": check_kubernetes_health,
    }

    k8s_url = "https://{}:{}".format(args.host, args.port)
    nagios_exit(*checks[args.check](k8s_url,
                                    args.client_token,
                                    args.ssl_ca_path))

"""
Future Checks

GET /api/v1/componentstatuses HTTP/1.1
Authorization: Bearer $TOKEN
Accept: application/json
Connection: close

GET /api/va/nodes HTTP/1.1
Authorization: Bearer $TOKEN
Accept: application/json
Connection: close

"""