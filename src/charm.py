#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
# Copyright © 2020 Llama Charmers  llama-charmers@lists.ubuntu.com

"""Operator Charm main library."""
# Load modules from lib directory
import logging

import setuppath  # noqa:F401
from lib_kubernetes_service_checks import KSCHelper

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, MaintenanceStatus, BlockedStatus


class Kubernetes_Service_ChecksCharm(CharmBase):
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
            self.on.kube_api_endpoint_relation_changed,
            self.on_kube_api_endpoint_relation_changed,
        )
        self.framework.observe(
            self.on.kube_control_relation_changed,
            self.on_kube_control_relation_changed,
        )
        self.framework.observe(
            self.on.nrpe_external_master_relation_joined,
            self.on_nrpe_external_master_relation_joined
        )
        self.framework.observe(
            self.on.nrpe_external_master_relation_changed,
            self.on_nrpe_external_master_relation_changed
        )
        self.framework.observe(
            self.on.nrpe_external_master_relation_departed,
            self.on_nrpe_external_master_relation_departed
        )
        # -- initialize states --
        self.state.set_default(installed=False)
        self.state.set_default(configured=False)
        self.state.set_default(started=False)
        self.state.set_default(kube_control={})
        self.state.set_default(kube_api_endpoint={})
        self.state.set_default(nrpe_configured=False)
        self.helper = KSCHelper(self.model.config, self.state)

    def on_install(self, event):
        """Handle install state."""
        # TOFIX: installing kubectl isnt necessary
        self.unit.status = MaintenanceStatus("Installing charm software")
        self.unit.status = MaintenanceStatus("Install complete")
        logging.info("Install of software complete")
        self.state.installed = True

    def on_upgrade_charm(self, event):
        """Handle upgrade and resource updates."""
        # Re-install for new snaps
        logging.info("Reinstalling for upgrade-charm hook")
        self.on_install(event)

    def check_charm_status(self):
        """Check that required data is available from relations and set charm's state"""
        # check that relations are configured with expected data

        if not self.helper.kubernetes_api_address or not self.helper.kubernetes_api_port:
            logging.warning("kubernetes-api-endpoint relation missing or misconfigured")
            self.unit.status = BlockedStatus("missing kubernetes-api-endpoint relation")
            return
        if not self.helper.kubernetes_client_token:
            logging.warning("kubernetes-control relation missing or misconfigured")
            self.unit.status = BlockedStatus("missing kubernetes-control relation")
            return
        if not self.state.nrpe_configured:
            logging.warning("nrpe-external-master relation missing")
            self.unit.status = BlockedStatus("missing nrpe-external-master relation")
            return

        # check specific config values if necessary
        # Set up TLS Certificate
        if self.helper.use_tls_cert:
            logging.info("Updating tls certificates")
            if self.helper._update_tls_certificates():
                logging.info("TLS Certificates updated successfully")
            else:
                logging.error("Failed to update TLS Certificates")
                self.unit.status = BlockedStatus("update-ca-certificates error. check logs")
        else:
            logging.warn("No trusted_ssl_ca provided, SSL Host Authentication disabled")


        # configure checks
        logging.info("Configuring Kubernetes Service Checks")
        self.helper.configure()
        self.state.configured = True


    def on_config_changed(self, event):
        """Handle config changed."""
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
        self.unit.status = MaintenanceStatus("Starting charm software")
        # Start software
        # TODO: Do any host services need to be started?
        # host.service_start(self.helper.service_name)
        self.unit.status = ActiveStatus("Unit is ready")
        self.state.started = True
        logging.info("Started")

    def _defer_once(self, event):
        """Defer the given event, but only once."""
        notice_count = 0
        handle = str(event.handle)

        for event_path, _, _ in self.framework._storage.notices(None):
            if event_path.startswith(handle.split('[')[0]):
                notice_count += 1
                logging.debug("Found event: {} x {}".format(event_path, notice_count))

        if notice_count > 1:
            logging.debug("Not deferring {} notice count of {}".format(handle, notice_count))
        else:
            logging.debug("Deferring {} notice count of {}".format(handle, notice_count))
            event.defer()

    def on_kube_api_endpoint_relation_changed(self, event):
        """ Handle kube_api_endpoint relation change event by importing the
        provided hostname and port to KSCHelper.
        """
        self.unit.status = MaintenanceStatus("Updating K8S Endpoint")
        self.state.kube_api_endpoint.update(event.relation.data[event.unit])
        self.check_charm_status()

    def on_kube_control_relation_changed(self, event):
        self.unit.status = MaintenanceStatus("Updating K8S Credentials")
        self.state.kube_control.update(event.relation.data[event.unit])
        self.check_charm_status()

    def on_nrpe_external_master_relation_joined(self, event):
        self.state.nrpe_configured = True
        self.check_charm_status()

    def on_nrpe_external_master_relation_changed(self, event):
        pass
        # need to provide some NRPE values
        #nagios_host_context: bootstack - okcupid - wa
        #nagios_hostname: bootstack - okcupid - wa - openstack - service - checks - 0

    def on_nrpe_external_master_relation_departed(self, event):
        self.state.nrpe_configured = False
        self.check_charm_status()


if __name__ == "__main__":
    from ops.main import main
    main(Kubernetes_Service_ChecksCharm)
