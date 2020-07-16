# kubernetes-service-checks Charm

Overview
--------

This charm provides Kubernetes Service checks for Nagios

Quickstart
----------

    juju deploy cs:kubernetes-service-checks
    juju add-relation kubernetes-service-checks nrpe
    juju add-relation kubernetes-service-checks:kube-api-endpoint kubernetes-master
    juju add-relation kuberentes-service-checks:kube-control kuberentes-master
    



### Relations

* **kubernetes-master:kube-api-endpoint** - Provides KSC with the kubernetes-api *hostname* and *port*

* **kuberentes-master:kube-control** - Provides KSC with a kuberentes-api *client-token* for authentication

* **nrpe:nrpe-external-master** - Required for nagios; provides additional plugins 


**Note:** Future relations with kubernetes-master *may* be changed so that a 
single relation can provide the K8S api hostname, port, client token and ssl ca
cert.

### Config Options

**trusted_ssl_ca** *(Optional)* Setting this option enables SSL host 
certificate authentication in the api checks
    
    juju config kubernetes-service-checks trusted_ssl_ca="${KUBERNETES_API_CA}"


Service Checks
--------------
The plugin *check_kubernetes_api.py* ships with this charm and contains an array of checks for the k8s api health.

```
check_kubernetes_api.py --help
usage: check_kubernetes_api.py [-h] [-H HOST] [-P PORT] [-T CLIENT_TOKEN]
                               [--check health] [-C SSL_CA_PATH]

Check Kubernetes API status

optional arguments:
  -h, --help            show this help message and exit
  -H HOST, --host HOST  Hostname or IP of the kube-api-server (default: None)
  -P PORT, --port PORT  Port of the kube-api-server (default: 6443)
  -T CLIENT_TOKEN, --token CLIENT_TOKEN
                        Client access token for authenticate with the
                        Kubernetes API (default: None)
  --check health        which check to run (default: health)
  -C SSL_CA_PATH, --trusted-ca-cert SSL_CA_PATH
                        String containing path to the trusted CA certificate
                        (default: None)

```

**health** - This polls the kubernetes-api */healthz* endpoint. Posting a GET to this URL endpoint is expected to 
return 200 - 'ok' if the api is healthy, otherwise 500.  


Other Checks
------------

**Certificate Expiration:** The *check_http* plugin is shipped with nrpe, and contains a built in cert expiration check. The warning and crit 
thesholds are configurable:

    juju config kubernetes-service-checks tls_warn_days=90
    juju config kubernetes-service-checks tls_crit_days=30

Testing
-------

Juju should be installed and bootstrapped on the system to run functional tests.


```
    export MODEL_SETTINGS=<semicolon-separated list of "juju model-config" settings>
    make test
```

NOTE: If you are behind a proxy, be sure to export a MODEL_SETTINGS variable as
described above. Note that you will need to use the juju-http-proxy, juju-https-proxy, juju-no-proxy 
and similar settings.

Contact
-------
 - Author: **Llama Charmers** *<llama-charmers@lists.ubuntu.com>*
 - Bug Tracker: [lp:charm-kubernetes-service-checks](https://launchpad.net/charm-kubernetes-service-checks)
