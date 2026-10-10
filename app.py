from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd
from graphviz import Digraph
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

EXAMPLE_NS = Namespace("http://example.org/")
QB = Namespace("http://purl.org/linked-data/cube#")
QB4O = Namespace("http://purl.org/qb4olap/cubes#")

sample_ttl = """
@prefix ex: <http://example.org/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:Student a rdfs:Class .
ex:Course a rdfs:Class .
ex:Department a rdfs:Class .
ex:Enrollment a rdfs:Class .

ex:studentId a rdf:Property ; rdfs:domain ex:Student ; rdfs:range xsd:string .
ex:enrolledIn a rdf:Property ; rdfs:domain ex:Student ; rdfs:range ex:Course .
ex:memberOf a rdf:Property ; rdfs:domain ex:Student ; rdfs:range ex:Department .
ex:grade a rdf:Property ; rdfs:domain ex:Enrollment ; rdfs:range xsd:float .
ex:courseName a rdf:Property ; rdfs:domain ex:Course ; rdfs:range xsd:string .
ex:departmentName a rdf:Property ; rdfs:domain ex:Department ; rdfs:range xsd:string .

ex:alice a ex:Student ; ex:studentId "S001" ; ex:enrolledIn ex:math ; ex:memberOf ex:cs .
ex:bob a ex:Student ; ex:enrolledIn ex:bio ; ex:memberOf ex:med .
ex:math a ex:Course ; ex:courseName "Mathematics" .
ex:bio a ex:Course ; ex:courseName "Biology" .
ex:cs a ex:Department ; ex:departmentName "Computer Science" .
ex:med a ex:Department ; ex:departmentName "Medicine" .

ex:e1 a ex:Enrollment ; ex:grade "92.5"^^xsd:float ; ex:student ex:alice ; ex:course ex:math .
ex:e2 a ex:Enrollment ; ex:grade "85.0"^^xsd:float ; ex:student ex:bob ; ex:course ex:bio .
"""


def parse_uploaded_graph(files: Iterable[Any]) -> Graph:
    graph = Graph()
    for uploaded_file in files:
        content = uploaded_file.read()
        try:
            text = content.decode("utf-8")
            graph.parse(data=text, format="turtle")
        except Exception:
            try:
                graph.parse(data=content, format="turtle")
            except Exception as exc:
                raise ValueError(f"Could not parse Turtle: {exc}") from exc
    return graph


def _safe_label(value: Any) -> str:
    if isinstance(value, URIRef):
        return str(value).split("/")[-1].split("#")[-1]
    if isinstance(value, Literal):
        return str(value)
    if isinstance(value, BNode):
        return "bnode"
    return str(value)


def _as_class_name(uri: str) -> str:
    if uri.startswith("http://") or uri.startswith("https://"):
        return uri.rsplit("/", 1)[-1].split("#")[-1]
    return uri


def _discover_classes(graph: Graph) -> List[str]:
    classes = set()
    for s, _, _ in graph.triples((None, RDF.type, None)):
        classes.add(_as_class_name(str(s)))
    for _, _, o in graph.triples((None, RDFS.subClassOf, None)):
        classes.add(_as_class_name(str(o)))
    for _, _, o in graph.triples((None, RDF.type, RDFS.Class)):
        classes.add(_as_class_name(str(o)))
    return sorted(classes)


def _discover_properties(graph: Graph) -> List[str]:
    props = set()
    for predicate in graph.predicates(None, None):
        props.add(_as_class_name(str(predicate)))
    return sorted(props)


def _discover_individuals(graph: Graph) -> List[str]:
    individuals = []
    for s, _, _ in graph:
        if isinstance(s, URIRef):
            individuals.append(_as_class_name(str(s)))
    return sorted(set(individuals))


def _numeric_predicates(graph: Graph) -> List[str]:
    numeric = []
    seen = set()
    for _, pred, obj in graph:
        if isinstance(obj, Literal) and isinstance(obj.toPython(), (int, float)):
            name = _as_class_name(str(pred))
            if name not in seen:
                numeric.append(name)
                seen.add(name)
    return numeric


def _fact_candidates(graph: Graph, classes: List[str]) -> List[str]:
    if not classes:
        return ["Observation"]
    candidates = []
    for cls in classes:
        count = 0
        for s, _, o in graph:
            if _as_class_name(str(s)).startswith(cls) or _as_class_name(str(o)).startswith(cls):
                count += 1
        candidates.append((cls, count))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in candidates[:5]]


def analyze_graph(graph: Graph) -> Dict[str, Any]:
    classes = _discover_classes(graph)
    properties = _discover_properties(graph)
    individuals = _discover_individuals(graph)
    numeric_props = _numeric_predicates(graph)
    fact_candidates = _fact_candidates(graph, classes)
    fact_candidate = fact_candidates[0] if fact_candidates else "Observation"

    dimensions = []
    for prop in properties:
        if prop.lower() not in {"type", "label", "name", "description"} and prop not in numeric_props:
            dimensions.append(prop)

    measures = numeric_props[:5] if numeric_props else ["measureValue"]
    attributes = [p for p in properties if p.lower() in {"label", "name", "description"}]
    if not attributes:
        attributes = ["description", "label", "name"]

    fact_rows = []
    for s, p, o in graph:
        fact_rows.append({
            "subject": _as_class_name(str(s)),
            "predicate": _as_class_name(str(p)),
            "object": _as_class_name(str(o)) if isinstance(o, URIRef) else str(o)
        })

    fact_table = pd.DataFrame(fact_rows[:25])
    if fact_table.empty:
        fact_table = pd.DataFrame({"subject": [fact_candidate], "predicate": ["type"], "object": ["fact"]})

    grain = f"One fact row per {fact_candidate} instance, with dimension context and measure values."

    hierarchy_candidates = []
    for prop in dimensions:
        hierarchy_candidates.append({"dimension": prop, "level": ["Member", "Parent", "All"]})

    return {
        "graph": graph,
        "classes": classes,
        "properties": properties,
        "individuals": individuals,
        "fact_candidate": fact_candidate,
        "dimensions": dimensions[:5],
        "measures": measures,
        "attributes": attributes[:5],
        "grain": grain,
        "level_candidates": hierarchy_candidates,
        "fact_table": fact_table,
    }


def build_stage_graph(title: str, nodes: List[Tuple[str, str]], edges: List[Tuple[str, str]], color_map: Dict[str, str]) -> Digraph:
    dot = Digraph(name=title, format="png")
    dot.attr(rankdir="LR", nodesep="0.5", ranksep="0.8", splines="line")
    dot.attr("node", shape="box", style="rounded,filled", fontname="Helvetica")
    dot.attr("edge", color="gray40", arrowsize="0.8")
    for node_id, label in nodes:
        dot.node(node_id, label=label, fillcolor=color_map.get(node_id, "white"), color="black")
    for source, target in edges:
        dot.edge(source, target)
    return dot


def build_mdkg_ttl(analysis: Dict[str, Any]) -> str:
    fact = analysis["fact_candidate"]
    dims = analysis["dimensions"]
    measures = analysis["measures"]

    lines = [
        "@prefix ex: <http://example.org/> .",
        "@prefix qb: <http://purl.org/linked-data/cube#> .",
        "@prefix qb4o: <http://purl.org/qb4olap/cubes#> .",
        "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        f"ex:{fact}Cube a qb:DataSet ;",
        f"    qb:structure ex:{fact}Structure .",
        f"",
        f"ex:{fact}Structure a qb:DataStructureDefinition ;",
    ]

    for dim in dims:
        lines.append(f"    qb:component [ qb:dimension ex:{dim} ] ;")
    for measure in measures:
        lines.append(f"    qb:component [ qb:measure ex:{measure} ] ;")
    if lines[-1].endswith(" ;"):
        lines[-1] = lines[-1][:-2] + " ."
    lines.append("")

    for dim in dims:
        lines.append(f"ex:{dim} a qb:DimensionProperty, qb4o:Dimension ;")
        lines.append(f"    rdfs:label \"{dim}\"@en .")
        lines.append("")

    for measure in measures:
        lines.append(f"ex:{measure} a qb:MeasureProperty ;")
        lines.append(f"    rdfs:label \"{measure}\"@en .")
        lines.append("")

    lines.append(f"ex:obs_001 a qb:Observation ;")
    lines.append(f"    qb:dataSet ex:{fact}Cube ;")
    if dims:
        lines.append(f"    ex:{dims[0]} ex:{dims[0]}_member ;")
    if measures:
        lines.append(f"    ex:{measures[0]} \"0\"^^xsd:decimal .")

    return "\n".join(lines)


# legacy alias to preserve compatibility with earlier app imports
sample_ttl_data = sample_ttl

