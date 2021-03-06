import re
import os
from rdflib import Graph, Namespace
from rdflib.term import URIRef, Literal, BNode
from flask import Flask, request, make_response, url_for
from ldf_server.backends.backend import load_backend, TriplesResult


app = Flask(__name__)
app.config['DEBUG'] = True

hydra = Namespace("http://www.w3.org/ns/hydra/core#")
void = Namespace("http://rdfs.org/ns/void#")
rdf = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

BACKEND = load_backend(
    os.environ.get(
        "LDF_SERVER_BACKEND",
        "ldf_server.backends.rdflib_backend.RDFLibBackend?{}".format(
            "file://{}".format(
                os.path.abspath(
                    os.path.join(
                        os.path.dirname(__file__), "../example.ttl"
                    )
                )
            )
        )
    )
)


def _fix_fragments(url):
    # substitute the #'s for %23
    return url.replace("#", "%23")


@app.route("/")
def index():
    triple_pattern = _triple_pattern(
        [request.args.get(x, '') for x in ['s', 'p', 'o']]
    )

    start_index = request.args.get('start', '')

    triples_result = BACKEND.triples(
        triple_pattern,
        start_index=start_index
    )

    if triples_result.next is not None:
        next_page_uri = url_for(
            'index',
            s=triple_pattern[0],
            p=triple_pattern[1],
            o=triple_pattern[2],
            start=triples_result.next
        )
    else:
        next_page_uri = None

    graph = _response_graph(
        request.base_url,
        _fix_fragments(request.url),
        triples_result,
        next_page_uri
    )
    response = make_response(graph.serialize(format="turtle"))
    response.headers['Content-Type'] = "text/turtle"
    response.cache_control.max_age = 30
    return response


def _response_graph(root_uri, request_uri, triples_result, next_page_uri):
    count = 0
    g = Graph()
    for triple in triples_result.triples:
        g.add(triple)
        count += 1

    # TODO Hydra controls
    dataset_uri = URIRef(root_uri + "#dataset")
    request_uri = URIRef(request_uri)
    template_bnode = BNode()
    s_mapping_bnode = BNode()
    p_mapping_bnode = BNode()
    o_mapping_bnode = BNode()

    if next_page_uri:
        g.add( (request_uri, hydra.nextPage, URIRef(next_page_uri)) )

    g += [
        (dataset_uri, rdf.type, void.Dataset),
        (dataset_uri, rdf.type, hydra.Collection),
        (dataset_uri, rdf.type, hydra.PagedCollection),
        (dataset_uri, void.subset, request_uri),
        (dataset_uri, hydra.search, template_bnode),
        (request_uri, rdf.type, hydra.Collection),
        (request_uri, hydra.totalItems, Literal(triples_result.total_triples)),
        (request_uri, void.triples, Literal(count)),
        (template_bnode, hydra.template, Literal(root_uri + "{?s,p,o}")),
        (template_bnode, hydra.mapping, s_mapping_bnode),
        (template_bnode, hydra.mapping, p_mapping_bnode),
        (template_bnode, hydra.mapping, o_mapping_bnode),
        (s_mapping_bnode, hydra.variable, Literal("s")),
        (p_mapping_bnode, hydra.variable, Literal("p")),
        (o_mapping_bnode, hydra.variable, Literal("o")),

        (s_mapping_bnode, hydra.property, rdf.subject),
        (p_mapping_bnode, hydra.property, rdf.predicate),
        (o_mapping_bnode, hydra.property, rdf.object),
    ]

    return g


def _triple_pattern(triple_strings):
    """
    _triple_pattern([str(), str(), str()]) -> (
        rdflib.term.Identifier() | None,
        rdflib.term.Identifier() | None,
        rdflib.term.Identifier() | None,
    )

    >>> _triple_pattern(('', '', ''))
    (None, None, None)

    >>> _triple_pattern(('?x', '', ''))
    (None, None, None)

    >>> _triple_pattern(('http://example.com/', '', ''))
    (rdflib.term.URIRef(u'http://example.com/'), None, None)

    >>> _triple_pattern(('"foo"', '', ''))
    (rdflib.term.Literal(u'foo'), None, None)

    >>> _triple_pattern(('""', '', ''))
    (rdflib.term.Literal(u''), None, None)
    """
    def str2identifier(s):
        # TODO constant literal with language or type
        # http://www.hydra-cg.com/spec/latest/triple-pattern-fragments/#h4_urls-for-triple-pattern-fragments
        if _is_literal(s):
            return _str_to_literal(s)
        elif _is_variable(s):
            return None
        else:
            return URIRef(s)
    return tuple(map(str2identifier, triple_strings))


def _is_variable(s):
    """
    >>> _is_variable("http://example.org/bar")
    False

    >>> _is_variable('"my text"')
    False

    >>> _is_variable('"my text"@en-gb')
    False

    >>> _is_variable('"42"^^http://www.w3.org/2001/XMLSchema#integer')
    False

    >>> _is_variable('?var')
    True
    """
    return s is None or s.startswith('?') or s.strip() == ""


def _is_literal(s):
    """
    >>> _is_literal("http://example.org/bar")
    False

    >>> _is_literal('"my text"')
    True

    >>> _is_literal('"my text"@en-gb')
    True

    >>> _is_literal('"42"^^http://www.w3.org/2001/XMLSchema#integer')
    True

    >>> _is_literal('?var')
    False

    """
    return s.startswith('"')


STRING_LITERAL_PAT = re.compile(r'^"(.*)"((\^\^|@)(.+))?$')


def _str_to_literal(s):
    """
    >>> _str_to_literal('"my text"')
    rdflib.term.Literal(u'my text')

    >>> _str_to_literal('"my text"@en-gb')
    rdflib.term.Literal(u'my text', lang='en-gb')

    >>> _str_to_literal('"42"^^http://www.w3.org/2001/XMLSchema#integer')
    rdflib.term.Literal(u'42', \
datatype=rdflib.term.URIRef(u'http://www.w3.org/2001/XMLSchema#integer'))

    """
    # locate the last " and nix any language or type annotations
    match = STRING_LITERAL_PAT.match(s)
    if match:
        if match.group(3) == "^^":
            return Literal(match.group(1), datatype=match.group(4))
        elif match.group(3) == "@":
            return Literal(match.group(1), lang=match.group(4))
        else:
            return Literal(match.group(1))
    else:
        raise ValueError("{} is not a valid string literal".format(s))


application = app
if __name__ == '__main__':
    app.run()
