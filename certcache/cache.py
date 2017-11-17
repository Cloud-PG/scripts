"""Module for caching variables in different stores."""
from abc import ABCMeta, abstractmethod
from ast import literal_eval

from six import add_metaclass

from kazoo import exceptions as kazoo_exceptions
from kazoo.client import KazooClient


@add_metaclass(ABCMeta)
class CacheManager(object):

    """Base cache manager class."""

    def __init__(self):
        self.__variables = {}

    def __getattr__(self, name):
        """Insert a new attribute variable."""
        if name not in self.__variables:
            return self.add_variable(name)
        return self.__variables[name]

    @abstractmethod
    def get_var(self, name):
        """Method GET for a cached variable."""
        pass

    @abstractmethod
    def set_var(self, name, value):
        """Method SET for a cached variable."""
        pass

    @abstractmethod
    def del_var(self, name):
        """Method DEL for a cached variable."""
        pass

    @abstractmethod
    def pre_add(self, name):
        """Function called before insertion in __variables.

        Params:
            name (str): the name of the variable
        """
        pass

    @abstractmethod
    def post_add(self, name, variable):
        """Function called after insertion in __variables.

        Params:
            name (str): the name of the variable
            variable (Variable): obj variable
        """
        pass

    def add_variable(self, name):
        """Insert a variable with a specific GET, SET, DEL methods.

        This function call pre_add and post_add. It wraps the
        creation of the variable.

        Params:
            name (str): name fo the variable to insert
        """
        self.pre_add(name)
        new_var = Variable(
            name,
            self.get_var,
            self.set_var,
            self.del_var
        )
        self.__variables[name] = new_var
        self.post_add(name, new_var)
        return self.__variables[name]


class Variable(object):

    """Class representing a variable in cache.

    This object will have an attribute called 'value'
    that is linked to the external fget, fset and fdel.
    These functions are passed during the initialization
    along with the name of the variable. The name of
    the variable is binded and is passed as first argument
    each time a GET, SET, DEL function is called.
    """

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

    def __init__(self, zookeeper_host_list, prefix="/cache/"):
        super(ZookeeperCache, self).__init__()

        self.zookeeper_host_list = None
        self.zk_client = None
        self.map = {}
        self.zookeeper_prefix = prefix

        self.init(zookeeper_host_list)
        self.start()

    def __del__(self):
        """Ensure to close the connection."""
        self.stop()

    def string_2_path(self, name):
        """Return the zookeeper cache path for the given name.

        It uses the zookeeper prefix, take a look at
        __init__ function.

        Params:
            name (str): name of the attribute

        Returns:
            str: the zookeeper path in cache
        """
        return self.zookeeper_prefix + name

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

    def pre_add(self, name):
        """Store the variable into the map as Zookeeper node.

        Params:
            name (str): the variable string name

        Returns:
            str: the path of that variable inside Zookeeper

        Example:
            "my_var" -> "/cache/my_var"
        """
        self.map[name] = self.string_2_path(name)
        return self.map[name]

    def post_add(self, name, variable):
        """Add the variable as Zookeeper node.

        Params:
            name (str): the name of the variable
            variable (Variable): obj variable

        Returns:
            IAsyncResult
        """
        return self.zk_client.ensure_path(self.map[name])

    def init(self, zookeeper_host_list):
        """Parse and save zookeeper host list string.
        
        This function tries also to add the default port
        when is not present in the host address.

        The list is normally retreived from the envirnment
        variables where is stored as a string like:
            - ZOOKEEPER_HOST_LIST="['10.1.4.2']"

        Params:
            zookeeper_host_list (str): zookeeper host addresses
        
        Returns:
            self
        """
        host_list = literal_eval(zookeeper_host_list)
        self.zookeeper_host_list = ",".join(
            [host + ":2181" if host.find(":") == -1 else host for host in host_list]
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
        
        Returns:
            self

        NOTE:
          In zookeeper cms cluser are present these children from root ("/") node:
             ["marathon", "mesos", "zookeeper"]
          So path like "/marathon", "/mesos", "/zookeeper" are already available

        """
        self.zk_client = KazooClient(hosts=self.zookeeper_host_list)
        self.zk_client.start()
        return self  # Enable Chaining

    def stop(self):
        """Close zookeeper connection.
        
        Returns:
            self
        """
        self.zk_client.stop()
        return self  # Enable Chaining
