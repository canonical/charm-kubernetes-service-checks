#!/usr/bin/python3
"""NRPE Plugin for checking Kubernetes API."""

import argparse
import json
import sys

import urllib3

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
    """Return the check status in Nagios preferred format.

    :param status: Nagios Check status code (in [0, 1, 2, 3])
    :param message: Message describing the status
    :return: sys.exit("{status_string}: {message}")
    """
    assert status in NAGIOS_STATUS, "Invalid Nagios status code"
    # prefix status name to message
    output = "{}: {}".format(NAGIOS_STATUS[status], message)
    print(output)  # nagios requires print to stdout, no stderr
    sys.exit(status)


def check_kubernetes_health(k8s_address, client_token, disable_ssl):
    """Call <kubernetes-api>/healthz endpoint and check return value is 'ok'.

    :param k8s_address: Address to kube-api-server formatted 'https://<IP>:<PORT>'
    :param client_token: Token for authenticating with the kube-api
    :param disable_ssl: Disables SSL Host Key verification
    """
    url = k8s_address + "/healthz"
    if disable_ssl:
        # perform check without SSL verification
        http = urllib3.PoolManager(cert_reqs="CERT_NONE", assert_hostname=False)
    else:
        http = urllib3.PoolManager()

    try:
        resp = http.request(
            "GET", url, headers={"Authorization": "Bearer {}".format(client_token)}
        )
    except urllib3.exceptions.MaxRetryError as e:
        return NAGIOS_STATUS_CRITICAL, e

    if resp.status != 200:
        return (
            NAGIOS_STATUS_CRITICAL,
            "Unexpected HTTP Response code ({})".format(resp.status),
        )
    elif resp.data != b"ok":
        return (
            NAGIOS_STATUS_WARNING,
            "Unexpected Kubernetes healthz status '{}'".format(resp.data),
        )
    return NAGIOS_STATUS_OK, "Kubernetes health 'ok'"


def check_kubernetes_nodes(k8s_address, client_token, disable_ssl):
    """Call <kubernetes-api>/api/v1/nodes endpoint and check each node status.

    :param k8s_address: Address to kube-api-server formatted 'https://<IP>:<PORT>'
    :param client_token: Token for authenticating with the kube-api
    :param disable_ssl: Disables SSL Host Key verification
    """
    url = k8s_address + "/api/v1/nodes"
    if disable_ssl:
        # perform check without SSL verification
        http = urllib3.PoolManager(cert_reqs="CERT_NONE", assert_hostname=False)
    else:
        http = urllib3.PoolManager()

    try:
        resp = http.request(
            "GET", url, headers={"Authorization": "Bearer {}".format(client_token)}
        )
    except urllib3.exceptions.MaxRetryError as e:
        return NAGIOS_STATUS_CRITICAL, e

    if resp.status != 200:
        return (
            NAGIOS_STATUS_CRITICAL,
            "Unexpected HTTP Response code ({})".format(resp.status),
        )

    response_body = json.loads(resp.data)
    nodes_not_ready = []
    for item in response_body["items"]:
        for condition in item["status"]["conditions"]:
            if condition["type"] == "Ready":
                node_name = item["metadata"]["name"]
                if condition["status"] != "True":
                    nodes_not_ready.append(node_name)

    if nodes_not_ready:
        nodes = ", ".join(nodes_not_ready)
        return (
            NAGIOS_STATUS_CRITICAL,
            f"Nodes NotReady: {nodes}",
        )

    return NAGIOS_STATUS_OK, "All Nodes Ready"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check Kubernetes API status",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-H",
        "--host",
        dest="host",
        help="Hostname or IP of the kube-api-server",
        required=True,
    )

    parser.add_argument(
        "-P",
        "--port",
        dest="port",
        type=int,
        default=6443,
        help="Port of the kube-api-server",
        required=True,
    )

    parser.add_argument(
        "-T",
        "--token",
        dest="client_token",
        help="Client access token for authenticate with the Kubernetes API",
    )

    check_choices = ["health", "nodes"]
    parser.add_argument(
        "--check",
        dest="check",
        metavar="|".join(check_choices),
        type=str,
        choices=check_choices,
        default=check_choices[0],
        help="which check to run",
    )

    parser.add_argument(
        "-d",
        "--disable-host-key-check",
        dest="disable_host_key_check",
        default=False,
        action="store_true",
        help="Disables Host SSL Key Authentication",
    )
    args = parser.parse_args()

    checks = {
        "health": check_kubernetes_health,
        "nodes": check_kubernetes_nodes,
    }

    k8s_url = "https://{}:{}".format(args.host, args.port)
    nagios_exit(
        *checks[args.check](k8s_url, args.client_token, args.disable_host_key_check)
    )

"""
TODO: Future Checks

GET /api/v1/componentstatuses HTTP/1.1
Authorization: Bearer $TOKEN
Accept: application/json
Connection: close

"""
