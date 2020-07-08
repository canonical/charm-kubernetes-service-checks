import unittest
import yaml

from lib.lib_kubernetes_service_checks import KSCHelper

class TestLibKSCHelper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Setup Class Fixture"""
        # Load default config
        with open("./config.yaml") as default_config:
            cls.config = yaml.safe_load(default_config)

    @classmethod
    def tearDownClass(cls):
        """Tear down class fixture."""
        # mock.patch.stopall()
        # cls.tmpdir.cleanup()
        pass

    def setUp(self):
        """Setup test fixture"""
        self.helper = KSCHelper(self.config)

    def tearDown(self):
        """Clean up test fixture."""
        pass

if __name__ == "__main__":
    unittest.main()