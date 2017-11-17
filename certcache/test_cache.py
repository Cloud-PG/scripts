"""Unit test for cache module."""
import unittest
from random import randint

from cache import CacheManager, Variable, ZookeeperCache


class TestCacheModule(unittest.TestCase):

    """Test all functionalities of Zookeeper and Marathon
    cache module.
    """

    def test_init(self):
        """Zookeeper cache init."""
        cache_ = ZookeeperCache("['127.0.0.1']")
        self.assertIsInstance(cache_, CacheManager)

    def test_add_variable(self):
        """Zookeeper cache add variable."""
        cache_ = ZookeeperCache("['127.0.0.1']")
        variable = cache_.var_to_add
        self.assertIsInstance(
            variable,
            Variable
        )

    def test_get_variable(self):
        """Zookeeper cache init get variable."""
        cache_ = ZookeeperCache("['127.0.0.1']")
        variable_name = "myvar" + str(randint(0, 100))
        variable = cache_.add_variable(variable_name)
        self.assertEqual(variable.value, "")

    def test_set_variable(self):
        """Zookeeper cache init set variable."""
        cache_ = ZookeeperCache("['127.0.0.1']")
        variable = cache_.my_var
        random_int = randint(0, 100)
        variable.value = random_int
        self.assertEqual(variable.value, str(random_int))

    def test_del_variable(self):
        """Zookeeper cache init del variable."""
        cache_ = ZookeeperCache("['127.0.0.1']")
        variable = cache_.var_to_delete
        del variable.value
        self.assertEqual(
            variable.value, "ERROR: Node NOT EXISTS or was DELETED!")


if __name__ == '__main__':
    unittest.main()