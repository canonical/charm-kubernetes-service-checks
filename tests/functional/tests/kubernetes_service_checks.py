import concurrent.futures
import unittest
import zaza.model
import re
import time
import logging

from juju.model import Model
from juju.errors import JujuAPIError

class TestBase(unittest.TestCase):
    """Base Class for charm funcitonal tests"""
    @classmethod
    def setUpClass(cls):
        """ Run setup for tests. """
        cls.model_name = zaza.model.get_juju_model()
        cls.application_name = "kubernetes-service-checks"

    def setUp(self):
        for local_relation_name, remote_relation_unit in [
                ("kube-api-endpoint", "kubernetes-master"),
                ("kube-control", "kubernetes-master"),
                ("nrpe-external-master", "nrpe")]:
            logging.info("Adding relation {} with {}".format(local_relation_name,
                                                             remote_relation_unit))
            try:
                zaza.model.add_relation(self.application_name,
                                        local_relation_name,
                                        remote_relation_unit,
                                        self.model_name)
            except JujuAPIError as e:
                p = "^.*cannot\ add\ relation.*already\ exists"
                if re.search(p, e.message):
                    pass
                else:
                    raise(e)
        zaza.model.block_until_wl_status_info_starts_with(
            self.application_name,
            status="Unit is ready",
            timeout=200
        )

class TestRelations(TestBase):
    def _get_relation_id(self, remote_application, interface_name):
            return zaza.model.get_relation_id(self.application_name,
                                              remote_application,
                                              model_name=self.model_name,
                                              remote_interface_name=interface_name)

    def test_remove_kube_api_endpoint(self):
        rel_name = "kube-api-endpoint"
        remote_app = "kubernetes-master"
        logging.info("Removing kube-api-endpoint relation")

        zaza.model.remove_relation(self.application_name,
                                   rel_name,
                                   remote_app,
                                   self.model_name)
        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name,
                status="missing kube-api-endpoint relation",
                timeout=180
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become blocked")

        logging.info("Waiting for relation {} to be destroyed".format(rel_name))
        timeout = time.time() + 600
        while self._get_relation_id(remote_app, rel_name) is not None:
            time.sleep(5)
            if time.time() > timeout:
                self.fail("Timed out waiting for the relation {} to be destroyed".format(rel_name))

    def test_remove_kube_control(self):
        rel_name = "kube-control"
        remote_app = "kubernetes-master"
        logging.info("Removing kube-control relation")

        zaza.model.remove_relation(self.application_name,
                                   rel_name,
                                   remote_app,
                                   self.model_name)

        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name,
                status="missing kube-control relation",
                timeout=180
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become blocked")

        logging.info("Waiting for relation {} to be destroyed".format(rel_name))
        timeout = time.time() + 600
        while self._get_relation_id(remote_app, rel_name) is not None:
            time.sleep(5)
            if time.time() > timeout:
                self.fail("Timed out waiting for the relation {} to be destroyed".format(rel_name))

    def test_remove_nrpe_external_master(self):
        rel_name = "nrpe-external-master"
        remote_app = "nrpe"
        logging.info("Removing nrpe-external-master relation")

        zaza.model.remove_relation(self.application_name,
                                   rel_name,
                                   remote_app,
                                   self.model_name)

        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name,
                status="missing nrpe-external-master relation",
                timeout=180
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become blocked")

        logging.info("Waiting for relation {} to be destroyed".format(rel_name))
        timeout = time.time() + 600
        while self._get_relation_id(remote_app, rel_name) is not None:
            time.sleep(5)
            if time.time() > timeout:
                self.fail("Timed out waiting for the relation {} to be destroyed".format(rel_name))
