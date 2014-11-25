from ldf_server.backends.backend import Backend, TriplesResult
from rdflib import Graph


class RDFLibBackend(Backend):
    def __init__(self, graph_uri):
        self.graph = Graph().parse(graph_uri, format="turtle")

    def triples(self, triple_pattern, start_index=''):

        triples = sorted(
            self.graph.triples(triple_pattern)
        )
        total_triples = len(triples)
        try:
            start = int(start_index)
        except:
            start = 0

        page_size = 100
        next_start = start + page_size

        if total_triples < next_start:
            next_start = None


        return TriplesResult(
            total_triples,
            next_start,
            triples[start:start+page_size]
        )
