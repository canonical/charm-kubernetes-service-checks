#! /usr/bin/env python3
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
# Copyright © 2020 Ryan Farrell ryan.farrell@canonical.com

"""Operator Charm main library."""
# Load modules from lib directory
import logging

import setuppath  # noqa:F401
from lib_kubernetes_service_checks import KSCHelper

from charmhelpers.fetch import snap

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
        # -- initialize states --
        self.state.set_default(installed=False)
        self.state.set_default(configured=False)
        self.state.set_default(started=False)

        self.helper = KSCHelper(self.model.config)
        # snap retry is excessive
        snap.SNAP_NO_LOCK_RETRY_DELAY = 0.5
        snap.SNAP_NO_LOCK_RETRY_COUNT = 3

    def on_install(self, event):
        """Handle install state."""
        self.unit.status = MaintenanceStatus("Installing kubectl snap")
        try:
            channel = self.model.config['channel']
            snap.snap_install("kubectl",
                              "--classic",
                              "--channel={}".format(channel)
                              )
        except snap.CouldNotAcquireLockException:
            self.unit.status = BlockedStatus("kubectl failed to install")
            logging.error(
                "Could not install resource, deferring event: {}".format(event.handle)
            )
            self._defer_once(event)

            return
        # TODO: What else is needed for KSC?


        self.unit.status = MaintenanceStatus("Install complete")
        logging.info("Install of software complete")
        self.state.installed = True

    def on_upgrade_charm(self, event):
        """Handle upgrade and resource updates."""
        # Re-install for new snaps
        logging.info("Reinstalling for upgrade-charm hook")
        self.on_install(event)

    def on_config_changed(self, event):
        """Handle config changed."""

        if not self.state.installed:
            logging.warning("Config changed called before install complete, deferring event: {}.".format(event.handle))
            self._defer_once(event)

            return

        # Reconfigure helper with new config values
        self.helper.configure()

        # TODO: Do any host services need to be restarted?
        # host.service_restart(self.helper.service_name)

        # TODO: check if the 'channel' config has been changed - may need to call install again to update kubectl

        if self.state.started:
            # Stop if necessary for reconfig
            logging.info("Stopping for configuration, event handle: {}".format(event.handle))
        # Configure the software
        logging.info("Configuring")
        self.state.configured = True

    def on_start(self, event):
        """Handle start state."""

        if not self.state.configured:
            logging.warning("Start called before configuration complete, deferring event: {}".format(event.handle))
            self._defer_once(event)

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
        """Handle kube_api_endpoint relation change event, which will """
        kube_api_server = event.relation.data[event.unit].get("private-address")
        kube_api_port = event.relation.data[event.unit].get("port")

        self.unit.status = MaintenanceStatus("Configuring K8S Endpoint")
        self.helper.update_k8s_endpoint(kube_api_server, kube_api_port)
        event.log("Retrieved Kubernetes Master URL: {}".format(helper.k8s_endpoint))

        self.state._k8s_endpoint_configured = True
        #if self.mysql.is_ready:
        #    event.log("Database relation complete")
        #self.state._db_configured = True

    #def on__relation_changed(self, event):

'''
    def on_example_action(self, event):
        """Handle the example_action action."""
        event.log("Hello from the example action.")
        event.set_results({"success": "true"})
'''

if __name__ == "__main__":
    from ops.main import main
    main(Kubernetes_Service_ChecksCharm)
