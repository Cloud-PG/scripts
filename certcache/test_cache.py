import unittest
from cache import *
from random import randint

class TestStringMethods(unittest.TestCase):

    def test_init(self):
        manager = ZookeeperCache("['127.0.0.1']")
        self.assertIsInstance(manager, CacheManager)

    def test_add_variable(self):
        manager = ZookeeperCache("['127.0.0.1']")
        variable = "/test/myvar" + str(randint(0, 100))
        manager.add_variable(variable)
        self.assertIsInstance(
            getattr(
                manager,
                manager.var_2_attr_name(variable)
            ),
            Variable
        )
    
    def test_get_variable(self):
        manager = ZookeeperCache("['127.0.0.1']")
        variable = "/test/myvar" + str(randint(0, 100))
        manager.add_variable(variable)
        attribute = getattr(manager, manager.var_2_attr_name(variable))
        self.assertEqual(attribute.value, "")

    def test_set_variable(self):
        manager = ZookeeperCache("['127.0.0.1']")
        variable = "/test/myvar" + str(randint(0, 100))
        manager.add_variable(variable)
        random_int = randint(0, 100)
        attribute = getattr(manager, manager.var_2_attr_name(variable))
        attribute.value = random_int
        self.assertEqual(attribute.value, str(random_int))
    
    def test_del_variable(self):
        manager = ZookeeperCache("['127.0.0.1']")
        variable = "/test/myvar" + str(randint(0, 100))
        manager.add_variable(variable)
        attribute = getattr(manager, manager.var_2_attr_name(variable))
        del attribute.value
        self.assertEqual(attribute.value, "ERROR: Node NOT EXISTS or was DELETED!")

if __name__ == '__main__':
    unittest.main()