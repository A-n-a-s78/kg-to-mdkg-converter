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
            graph.parse(data=content.decode("utf-8"), format="turtle")
        except Exception:
            try:
                graph.parse(data=content, format="turtle")
            except Exception as exc:
                raise ValueError(f"Could not parse Turtle content: {exc}") from exc
    return graph


def _safe_label(value: Any) -> str:
    if isinstance(value, URIRef):
        return str(value).split("/")[-1].split("#")[-1]
    if isinstance(value, Literal):
        return str(value)
    if isinstance(value, BNode):
        return "bnode"
    return str(value)


def _guess_fact_candidate(classes: List[str], property_map: Dict[str, List[str]], instance_counts: Dict[str, int]) -> str:
    if not classes:
        return "UnknownFact"

    def score(cls: str) -> int:
        obj_props = len(property_map.get(cls, []))
        return instance_counts.get(cls, 0) + obj_props * 3

    return max(classes, key=score)


def analyze_graph(graph: Graph) -> Dict[str, Any]:
    classes = set()
    for s in graph.subjects(RDF.type, None):
        classes.add(_safe_label(s))
    for o in graph.objects(None, RDFS.subClassOf):
        classes.add(_safe_label(o))
    for s in graph.subjects(RDFS.domain, None):
        classes.add(_safe_label(s))

    properties = {}
    for pred in graph.predicates(None, None):
        properties[str(pred)] = []

    class_property_map: Dict[str, List[str]] = {}
    for subj, pred, obj in graph:
        if isinstance(subj, URIRef):
            subj_label = _safe_label(subj)
            if not subj_label in class_property_map:
                class_property_map[subj_label] = []
            class_property_map[subj_label].append(_safe_label(pred))

    individuals = []
    for s in graph.subjects(RDF.type, None):
        if isinstance(s, URIRef):
            individuals.append(_safe_label(s))

    instance_counts: Dict[str, int] = {}
    for s, _, _ in graph:
        if isinstance(s, URIRef):
            label = _safe_label(s)
            instance_counts[label] = instance_counts.get(label, 0) + 1

    class_list = sorted(list(classes))
    fact_candidate = _guess_fact_candidate(class_list, class_property_map, instance_counts)
    dimensions = []
    measures = []
    attributes = []

    for item in class_list:
        if item == fact_candidate:
            continue
        dimensions.append(item)

    for pred in graph.predicates(None, None):
        label = _safe_label(pred)
        if any(label.endswith("grade") or label.endswith("score") or label.endswith("value") or label.endswith("amount") for _ in [0]):
            measures.append(label)

    if not measures:
        measures = ["measureValue"]

    attributes = ["description", "label", "name"]

    fact_rows = []
    for s, pred, obj in graph:
        if isinstance(s, URIRef):
            row = {"subject": _safe_label(s), "predicate": _safe_label(pred), "object": _safe_label(obj)}
            fact_rows.append(row)

    fact_table = pd.DataFrame(fact_rows[:25])
    if fact_table.empty:
        fact_table = pd.DataFrame({"subject": [fact_candidate], "predicate": ["type"], "object": ["fact"]})

    grain = f"One row per {fact_candidate} instance with associated dimension membership and measure observation."
    level_candidates = {
        "fact": fact_candidate,
        "possible_levels": dimensions[:5],
    }

    return {
        "graph": graph,
        "classes": class_list,
        "properties": sorted(list(properties.keys())),
        "individuals": sorted(set(individuals)),
        "fact_candidate": fact_candidate,
        "dimensions": dimensions[:5],
        "measures": measures[:5],
        "attributes": attributes,
        "grain": grain,
        "level_candidates": level_candidates,
        "fact_table": fact_table,
    }


def build_stage_graph(title: str, nodes: List[Tuple[str, str]], edges: List[Tuple[str, str]], color_map: Dict[str, str]) -> Digraph:
    dot = Digraph(name=title, format="png")
    dot.attr(rankdir="LR", nodesep="0.5", ranksep="0.8", splines="spline")
    dot.attr("node", shape="box", style="rounded,filled", fontname="Helvetica")
    dot.attr("edge", color="gray40", arrowsize="0.8")

    for node_id, label in nodes:
        color = color_map.get(node_id, "white")
        dot.node(node_id, label=label, fillcolor=color, color="black")

    for left, right in edges:
        dot.edge(left, right)

    return dot


def build_mdkg_ttl(analysis: Dict[str, Any]) -> str:
    fact = analysis["fact_candidate"]
    dims = analysis["dimensions"]
    measures = analysis["measures"]

    ttl_lines = [
        "@prefix ex: <http://example.org/> .",
        "@prefix qb: <http://purl.org/linked-data/cube#> .",
        "@prefix qb4o: <http://purl.org/qb4olap/cubes#> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
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
        ttl_lines.append(f"    qb:component [ qb:dimension ex:{dim} ] ;")
    for measure in measures:
        ttl_lines.append(f"    qb:component [ qb:measure ex:{measure} ] ;")

    ttl_lines[-1] = ttl_lines[-1].rstrip(" ;") + " ."
    ttl_lines.append("")

    for dim in dims:
        ttl_lines.append(f"ex:{dim} a qb:DimensionProperty, qb4o:Dimension ;")
        ttl_lines.append(f"    rdfs:label \"{dim}\"@en .")
        ttl_lines.append("")

    for measure in measures:
        ttl_lines.append(f"ex:{measure} a qb:MeasureProperty ;")
        ttl_lines.append(f"    rdfs:label \"{measure}\"@en .")
        ttl_lines.append("")

    ttl_lines.append(f"ex:obs_001 a qb:Observation ;")
    ttl_lines.append(f"    qb:dataSet ex:{fact}Cube ;")
    for dim in dims[:2]:
        ttl_lines.append(f"    ex:{dim} ex:{dim}_member ;")
    for measure in measures[:1]:
        ttl_lines.append(f"    ex:{measure} \"0\"^^xsd:decimal .")

    return "\n".join(ttl_lines)
