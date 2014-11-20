from abc import ABCMeta, abstractmethod
from urlparse import urlparse
from importlib import import_module


def load_backend(uri):
    bits = urlparse(uri)
    modulename, classname = _split_module_path(bits.path)
    mod = import_module(modulename)
    klass = getattr(mod, classname)
    return klass(bits.query)


def _split_module_path(path):
    bits = path.split(".")
    return ".".join(bits[:-1]), bits[-1]


class Backend:
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, querystring):
        pass

    @abstractmethod
    def triples(self, triple_pattern):
        pass
