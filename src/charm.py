#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
# Copyright © 2020 Bootstack Charmers  bootstack-charmers@lists.canonical.com

"""Operator Charm main library."""
# Load modules from lib directory
import logging

import setuppath  # noqa:F401

from lib_kubernetes_service_checks import KSCHelper  # noqa:I100
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus


class KubernetesServiceChecksCharm(CharmBase):
    """Class representing this Operator charm."""

    state = StoredState()

    def __init__(self, *args):
        """Initialize charm and configure states and events to observe."""
        super().__init__(*args)
        # -- standard hook observation
        self.framework.observe(self.on.install, self.on_install)
        self.framework.observe(self.on.start, self.on_start)
        self.framework.observe(self.on.config_changed, self.on_config_changed)
        self.framework.observe(
            self.on.kube_api_endpoint_relation_changed, self.on_kube_api_endpoint_relation_changed,
        )
        self.framework.observe(self.on.kube_api_endpoint_relation_departed, self.on_kube_api_endpoint_relation_departed)
        self.framework.observe(
            self.on.kube_control_relation_changed, self.on_kube_control_relation_changed,
        )
        self.framework.observe(self.on.kube_control_relation_departed, self.on_kube_control_relation_departed)
        self.framework.observe(
            self.on.nrpe_external_master_relation_joined, self.on_nrpe_external_master_relation_joined
        )
        self.framework.observe(
            self.on.nrpe_external_master_relation_departed, self.on_nrpe_external_master_relation_departed
        )
        # -- initialize states --
        self.state.set_default(
            installed=False,
            configured=False,
            started=False,
            kube_control={},
            kube_api_endpoint={},
            nrpe_configured=False,
        )
        self.helper = KSCHelper(self.model.config, self.state)

    def on_install(self, event):
        """Handle install state."""
        self.unit.status = MaintenanceStatus("Install complete")
        logging.info("Install of software complete")
        self.state.installed = True

    def on_upgrade_charm(self, event):
        """Handle upgrade and resource updates."""
        self.state.configured = False
        logging.info("Reinstalling for upgrade-charm hook")
        self.on_install(event)
        self.check_charm_status()

    def check_charm_status(self):
        """
        Check that required data is available from relations.

        - Check kube-api-endpoint relation and data available
        - Check kube-control relation and data available
        - Check nrpe-external-master is configured
        - Check any required config options
        - Finally, configure the charms checks and set flags
        """
        if not self.helper.kubernetes_api_address or not self.helper.kubernetes_api_port:
            logging.warning("kube-api-endpoint relation missing or misconfigured")
            self.unit.status = BlockedStatus("missing kube-api-endpoint relation")
            return
        if not self.helper.kubernetes_client_token:
            logging.warning("kube-control relation missing or misconfigured")
            self.unit.status = BlockedStatus("missing kube-control relation")
            return
        if not self.state.nrpe_configured:
            logging.warning("nrpe-external-master relation missing or misconfigured")
            self.unit.status = BlockedStatus("missing nrpe-external-master relation")
            return

        # Check specific required config values
        # Set up TLS Certificate
        if self.helper.use_tls_cert:
            logging.info("Updating tls certificates")
            if self.helper.update_tls_certificates():
                logging.info("TLS Certificates updated successfully")
            else:
                logging.error("Failed to update TLS Certificates")
                self.unit.status = BlockedStatus("update-ca-certificates error. check logs")
                return
        else:
            logging.warning("No trusted_ssl_ca provided, SSL Host Authentication disabled")

        # configure nrpe checks
        logging.info("Configuring Kubernetes Service Checks")
        self.helper.configure()
        if not self.state.configured:
            logging.info("Reloading nagios-nrpe-server")
            self.helper.restart_nrpe_service()
            self.state.configured = True
        self.unit.status = ActiveStatus("Unit is ready")

    def on_config_changed(self, event):
        """Handle config changed."""
        self.state.configured = False
        if not self.state.installed:
            logging.warning("Config changed called before install complete, deferring event: {}.".format(event.handle))
            self._defer_once(event)
            return
        self.check_charm_status()

    def on_start(self, event):
        """Handle start state."""
        if not self.state.configured:
            logging.warning("Start called before configuration complete, deferring event: {}".format(event.handle))
            event.defer()
            return
        self.unit.status = ActiveStatus("Unit is ready")
        self.state.started = True
        logging.info("Started")

    def _defer_once(self, event):
        """Defer the given event, but only once."""
        notice_count = 0
        handle = str(event.handle)

        for event_path, _, _ in self.framework._storage.notices(None):
            if event_path.startswith(handle.split("[")[0]):
                notice_count += 1
                logging.debug("Found event: {} x {}".format(event_path, notice_count))

        if notice_count > 1:
            logging.debug("Not deferring {} notice count of {}".format(handle, notice_count))
        else:
            logging.debug("Deferring {} notice count of {}".format(handle, notice_count))
            event.defer()

    def on_kube_api_endpoint_relation_changed(self, event):
        """Handle kube_api_endpoint relation changed."""
        self.state.configured = False
        self.unit.status = MaintenanceStatus("Updating K8S Endpoint")
        self.state.kube_api_endpoint.update(event.relation.data.get(event.unit, {}))
        self.check_charm_status()

    def on_kube_api_endpoint_relation_departed(self, event):
        """Handle kube-api-endpoint relation departed."""
        self.state.configured = False
        for k in self.state.kube_api_endpoint.keys():
            self.state.kube_api_endpoint[k] = ""
        self.check_charm_status()

    def on_kube_control_relation_changed(self, event):
        """Handle kube-control relation changed."""
        self.state.configured = False
        self.unit.status = MaintenanceStatus("Updating K8S Credentials")
        self.state.kube_control.update(event.relation.data.get(event.unit, {}))
        self.check_charm_status()

    def on_kube_control_relation_departed(self, event):
        """Handle kube-control relation departed."""
        self.state.configured = False
        for k in self.state.kube_control.keys():
            self.state.kube_control[k] = ""
        self.check_charm_status()

    def on_nrpe_external_master_relation_joined(self, event):
        """Handle nrpe-external-master relation joined."""
        self.state.nrpe_configured = True
        self.check_charm_status()

    def on_nrpe_external_master_relation_departed(self, event):
        """Handle nrpe-external-master relation departed."""
        self.state.configured = False
        self.state.nrpe_configured = False
        self.check_charm_status()


if __name__ == "__main__":
    main(KubernetesServiceChecksCharm)
