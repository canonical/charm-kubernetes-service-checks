import concurrent.futures
import unittest
import zaza.model
import re

from juju.model import Model
from juju.errors import JujuAPIError

class TestBase(unittest.TestCase):
    """Base Class for charm funcitonal tests"""
    @classmethod
    def setUpClass(cls):
        """ Run setup for tests. """
        cls.model_name = zaza.model.get_juju_model()
        cls.application_name = "kubernetes-service-checks"
        cls.required_relations = [
            ("kube-api-endpoint", "kubernetes-master"),
            ("kube-control", "kubernetes-master"),
            ("nrpe-external-master", "nrpe")
        ]

    def _add_relation(self, local_relation, remote_relation):
        try:
            zaza.model.add_relation(self.application_name,
                                    local_relation,
                                    remote_relation,
                                    self.model_name)
        except JujuAPIError as e:
            p = "^.*cannot\ add\ relation.*already\ exists"
            if re.search(p, e.message):
                pass
            else:
                raise(e)


class TestRelations(TestBase):
    def setUp(self):
        # add all required relatons
        for local_relation_name, remote_relation_app in self.required_relations:
            self._add_relation(local_relation_name, remote_relation_app)

        zaza.model.block_until_wl_status_info_starts_with(
            self.application_name,
            status="Unit is ready",
            timeout=90
        )

    def test_add_all_required_relations(self):
        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name,
                status="Unit is ready",
                timeout=90
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become ready")

    def test_remove_kube_api_endpoint(self):
        zaza.model.remove_relation(self.application_name,
                                   "kube-api-endpoint",
                                   "kubernetes-master",
                                   self.model_name)
        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name,
                status="missing kube-api-endpoint relation",
                timeout=90
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become blocked")

    def test_remove_kube_control(self):
        zaza.model.remove_relation(self.application_name,
                                   "kube-control",
                                   "kubernetes-master",
                                   self.model_name)
        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name,
                status="missing kube-control relation",
                timeout=90
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become blocked")

    def test_remove_nrpe_external_master(self):
        zaza.model.remove_relation(self.application_name,
                                   "nrpe-external-master",
                                   "nrpe",
                                   self.model_name)
        try:
            zaza.model.block_until_wl_status_info_starts_with(
                self.application_name,
                status="missing nrpe-external-master relation",
                timeout=90
            )
        except concurrent.futures._base.TimeoutError:
            self.fail("Timed out waiting for Unit to become blocked")

