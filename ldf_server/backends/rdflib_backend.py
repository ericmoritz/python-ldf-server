from ldf_server.backends.backend import Backend
from rdflib import Graph


class RDFLibBackend(Backend):
    def __init__(self, graph_uri):
        self.graph = Graph().parse(graph_uri, format="turtle")

    def triples(self, triple_pattern):
        return self.graph.triples(triple_pattern)
