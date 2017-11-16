"""Module for caching variables in different stores."""
from abc import ABCMeta
from abc import abstractmethod
from ast import literal_eval

from six import add_metaclass

from kazoo.client import KazooClient
from kazoo import exceptions as kazoo_exceptions


@add_metaclass(ABCMeta)
class CacheManager(object):

    """Base cache manager class."""

    @abstractmethod
    def get_var(self, name):
        """Method GET for a variable."""
        pass

    @abstractmethod
    def set_var(self, name, value):
        """Method SET for a variable."""
        pass

    @abstractmethod
    def del_var(self, name):
        """Method DEL for a variable."""
        pass

    def var_2_attr_name(self, string):
        """Variable string name converter.

        By default it returns the same input string,
        you have to override the method for a proper
        conversion.

        Params:
            string (str): the name to convert

        Returns:
            str
        """
        return string

    def add_variable(self, name):
        """Insert a variable with a specific GET, SET, DEL methods.

        The variable name is converted by 'var_2_attr_name' method.
        GET, SET and DEL methods are prepared with the name
        of the variable as partial funcions.

        Params:
            name (str): name fo the variable to insert
        """
        attr_name = self.var_2_attr_name(name)
        new_var = Variable(
            attr_name,
            self.get_var,
            self.set_var,
            self.del_var
        )
        setattr(self.__class__, attr_name, new_var)


class Variable(object):

    """Class representing a variable in cache."""

    def __init__(self, name, fget, fset, fdel):
        self.__name = name
        self.__fget = fget
        self.__fset = fset
        self.__fdel = fdel

    def m_get(self):
        """Call of the real GET method.

        NOTE: the real function needs the name of the
              variable (self.__name) and it's a function
              overrided in CacheManager class.

        """
        return self.__fget(self.__name)

    def m_set(self, value):
        """Call of the real SET method.

        NOTE: the real function needs the name of the
              variable (self.__name) and it's a function
              overrided in CacheManager class.
        """
        return self.__fset(self.__name, value)

    def m_del(self):
        """Call of the real DEL method.

        NOTE: the real function needs the name of the
              variable (self.__name) and it's a function
              overrided in CacheManager class.
        """
        return self.__fdel(self.__name)

    value = property(m_get, m_set, m_del)


class ZookeeperCache(CacheManager):

    """Cache manager with Zookeeper."""

    def __init__(self, zookeeper_host_list):
        super(ZookeeperCache, self).__init__()

        self.zookeeper_host_list = None
        self.zk_client = None
        self.map = {}

        self.init(zookeeper_host_list)
        self.start()

    def __del__(self):
        """Ensure to close the connection."""
        self.stop()

    def get_var(self, name):
        """Returns the variable string.

        Params:
            name (str): name of the variable

        Returns:
            str: the value of the variable converted in string

        Notes:
            The method get of zk_client returns a byte string that have
            to be converted into a string with the method decode.
        """
        try:
            value, _ = self.zk_client.get(self.map[name])
        except kazoo_exceptions.NoNodeError:
            return "ERROR: Node NOT EXISTS or was DELETED!"
        return value.decode("utf-8")

    def set_var(self, name, value):
        """Set the variable into the zookeeper environment.

        Params:
            name (str): name of the variable
            value (str): the value to set

        Returns:
            kazoo.protocol.states.ZnodeStat

        """
        return self.zk_client.set(self.map[name], str(value))

    def del_var(self, name):
        """Returns the variable string.

        Params:
            name (str): name of the variable

        Returns:
            tuple(value, ZnodeStat)
        """
        return self.zk_client.delete(self.map[name])

    def var_2_attr_name(self, string):
        """Convert into an attr name and store a zookeeper path.

        The path is stored in self.map and the attr name is
        returned. In this section is initialized the zookeeper
        variable.

        Params:
            string (str): the path string, e.g. "/marathon/refresh_token"

        Returns:
            str: the converted path in a proper attribute string.
                 Each '/' character it's converted into '_' except
                 for the first slash char.

        Example:
            "/marathon/refresh_token" -> "marathon_refresh_token"
        """
        tmp = string.strip().split("/")
        tmp = "_".join([elm for elm in tmp if elm != ""])
        self.map[tmp] = string
        self.zk_client.ensure_path(self.map[tmp])
        return tmp

    def init(self, zookeeper_host_list):
        """Generate zookeeper host list string."""
        host_list = literal_eval(zookeeper_host_list)
        self.zookeeper_host_list = ",".join(
            [host + ":2181" for host in host_list]
        )
        return self  # Enable Chaining

    def start(self):
        """Start zookeeper connection.

        Kazoo client needs a string with the list of zookeeper hosts
        divided by a comma. This little piece of code converts the
        list given as environment variable to a proper kazoo host string
        and starts the connection only if ZOOKEEPER_HOST_LIST is not None.
        In this phase we also prepare the zookeeper nodes to store variables.

        SOURCE: https://kazoo.readthedocs.io/en/latest/api/client.html#kazoo.client.KazooClient

        EXAMPLE:
          host1:port1,host2:port2,host3:port3

        NOTE:
          In zookeeper cms cluser are present these children from root ("/") node:
             ["marathon", "mesos", "zookeeper"]
          So path like "/marathon", "/mesos", "/zookeeper" are already available

        """
        self.zk_client = KazooClient(hosts=self.zookeeper_host_list)
        self.zk_client.start()
        return self  # Enable Chaining

    def stop(self):
        """Close zookeeper connection."""
        self.zk_client.stop()
        return self  # Enable Chaining
