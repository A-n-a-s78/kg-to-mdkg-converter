import os
from io import StringIO
from pathlib import Path

import pandas as pd
import streamlit as st
from graphviz import Digraph
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL

from src.kg_mdkg.core import (
    analyze_graph,
    build_mdkg_ttl,
    build_stage_graph,
    parse_uploaded_graph,
    sample_ttl,
)


st.set_page_config(page_title="KG → MDKG Workbench", layout="wide")


def render_stage(title, input_summary, processing_summary, graph_obj, validation_summary):
    st.subheader(title)
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("**1. Input**")
        st.write(input_summary)
        st.markdown("**2. Processing**")
        st.write(processing_summary)
    with col2:
        st.markdown("**3. Graphical result**")
        try:
            st.graphviz_chart(graph_obj.source, use_container_width=True)
        except Exception:
            st.code(graph_obj.source)
    st.markdown("**4. Validation**")
    st.write(validation_summary)
    st.markdown("---")


def main():
    st.title("KG → MDKG Workbench")
    st.caption("Universal Turtle KG → Multidimensional Knowledge Graph Converter")

    with st.sidebar:
        st.header("Upload RDF/Turtle files")
        uploaded_files = st.file_uploader(
            "TBox, ABox or combined TTL files",
            type=["ttl"],
            accept_multiple_files=True,
            key="ttl_uploads",
        )
        st.markdown("---")
        st.markdown("Supported modes")
        st.write("• TBox only")
        st.write("• ABox only")
        st.write("• TBox + ABox")
        st.write("• Combined TTL")
        st.write("• Existing QB/QB4OLAP")

    if uploaded_files:
        graph = parse_uploaded_graph(uploaded_files)
        source_note = f"Loaded {len(uploaded_files)} uploaded Turtle file(s)."
    else:
        graph = Graph().parse(data=sample_ttl, format="turtle")
        source_note = "Loaded built-in sample KG for demonstration."

    analysis = analyze_graph(graph)

    st.subheader("KG Explorer")
    colA, colB, colC = st.columns(3)
    with colA:
        st.metric("Classes", len(analysis["classes"]))
    with colB:
        st.metric("Properties", len(analysis["properties"]))
    with colC:
        st.metric("Individuals", len(analysis["individuals"]))

    st.info(source_note)

    st.markdown("### 1. Core graph summary")
    summary_df = pd.DataFrame(
        [
            {"Category": "Classes", "Count": len(analysis["classes"])},
            {"Category": "Properties", "Count": len(analysis["properties"])},
            {"Category": "Individuals", "Count": len(analysis["individuals"])},
            {"Category": "Triples", "Count": len(graph)},
        ]
    )
    st.dataframe(summary_df, use_container_width=True)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Stages 2.1–2.4",
            "Stages 2.5–2.8",
            "Stages 2.9–2.11",
            "Stages 2.12–2.13",
            "Configuration",
            "Export",
        ]
    )

    with tab1:
        stage1_input = "Candidate analytical objective extracted from the graph structure and the most connected fact-like class."
        stage1_processing = "Identify the likely business fact from instance density, class centrality, and measurable numeric attributes."
        stage1_graph = build_stage_graph(
            "Stage 2.1 — Analysis question",
            [
                ("Analytical objective", "Determine a fact-oriented analysis from the KG."),
                ("Fact candidate", analysis["fact_candidate"]),
                ("Recommended grain", analysis["grain"]),
            ],
            [
                ("Analytical objective", "Fact candidate"),
                ("Fact candidate", "Recommended grain"),
            ],
            color_map={"Analytical objective": "lightblue", "Fact candidate": "gold", "Recommended grain": "lightgreen"},
        )
        stage1_validation = "The analytical objective is a proposed default, not a hard-coded rule. User confirmation is required if the fact/grain is not semantically correct."
        render_stage("2.1 — Analysis question", stage1_input, stage1_processing, stage1_graph, stage1_validation)

        stage2_input = f"Fact class: {analysis['fact_candidate']}\nGrain: {analysis['grain']}\nCandidate dimensions: {analysis['dimensions']}"
        stage2_processing = "Choose the fact class and define the grain as the finest set of context values to be analyzed."
        stage2_graph = build_stage_graph(
            "Stage 2.2 — Fact and grain",
            [
                ("Fact class", analysis["fact_candidate"]),
                ("Grain", analysis["grain"]),
                ("Dimension candidates", ", ".join(analysis["dimensions"]) if analysis["dimensions"] else "No obvious dimension set"),
            ],
            [
                ("Fact class", "Grain"),
                ("Grain", "Dimension candidates"),
            ],
            color_map={"Fact class": "tomato", "Grain": "orange", "Dimension candidates": "lightgreen"},
        )
        stage2_validation = "Fact and grain are proposed heuristically. Validation should verify whether the chosen grain matches the intended observation unit."
        render_stage("2.2 — Fact and grain", stage2_input, stage2_processing, stage2_graph, stage2_validation)

        stage3_input = f"Properties extracted: {analysis['properties']}"
        stage3_processing = "Classify properties into dimensions, measures, and descriptive attributes based on type and semantics."
        stage3_graph = build_stage_graph(
            "Stage 2.3 — Property classification",
            [
                ("Measures", ", ".join(analysis["measures"]) if analysis["measures"] else "No measure candidates"),
                ("Dimensions", ", ".join(analysis["dimensions"]) if analysis["dimensions"] else "No dimension candidates"),
                ("Attributes", ", ".join(analysis["attributes"]) if analysis["attributes"] else "No descriptive attributes"),
            ],
            [
                ("Measures", "Dimensions"),
                ("Dimensions", "Attributes"),
            ],
            color_map={"Measures": "lightcoral", "Dimensions": "lightblue", "Attributes": "lightgreen"},
        )
        stage3_validation = "Classification is based on a best-effort heuristic. Numeric typed properties are likely measures; object relationships usually become dimensions."
        render_stage("2.3 — Property classification", stage3_input, stage3_processing, stage3_graph, stage3_validation)

        fact_table = analysis["fact_table"].copy()
        if fact_table.empty:
            fact_table = pd.DataFrame({"Record": ["No fact rows found"], "Value": [0]})
        st.subheader("2.4 — Fact table")
        st.markdown("**Input**")
        st.write(f"Fact class: {analysis['fact_candidate']}; rows inspected from the KG")
        st.markdown("**Processing**")
        st.write("Construct a fact table by collecting rows where the selected fact class is the subject and relevant dimension/measure triples are attached.")
        st.markdown("**Graphical result**")
        st.dataframe(fact_table.head(20), use_container_width=True)
        st.markdown("**Validation**")
        st.write("If the fact rows are sparse or incomplete, upload a richer ABox or choose a different fact class.")
        st.markdown("---")

    with tab2:
        stage5_input = f"Measures considered: {analysis['measures']}"
        stage5_processing = "Map each measure to a valid aggregate operator such as SUM, AVG, MIN, MAX, or COUNT, depending on the type and semantics."
        stage5_graph = build_stage_graph(
            "Stage 2.5 — Aggregate function",
            [
                ("Measure", analysis["measures"][0] if analysis["measures"] else "unknown"),
                ("Aggregation", "SUM/AVG/MIN/MAX/COUNT"),
                ("Result", "Aggregate fact values by dimension slices"),
            ],
            [
                ("Measure", "Aggregation"),
                ("Aggregation", "Result"),
            ],
            color_map={"Measure": "lightcoral", "Aggregation": "gold", "Result": "lightgreen"},
        )
        stage5_validation = "Aggregation must be confirmed by the domain expert; the default is a generic numeric aggregation rule."
        render_stage("2.5 — Aggregate function", stage5_input, stage5_processing, stage5_graph, stage5_validation)

        stage6_input = f"Hierarchy candidates: {analysis['level_candidates']}"
        stage6_processing = "Traverse parent-child relationships, detect level membership, and assess cardinality and completeness."
        stage6_graph = build_stage_graph(
            "Stage 2.6 — Level discovery",
            [
                ("Child", "Member"),
                ("Parent", "Higher level"),
                ("All", "Top level"),
            ],
            [
                ("Child", "Parent"),
                ("Parent", "All"),
            ],
            color_map={"Child": "lightblue", "Parent": "gold", "All": "lightgreen"},
        )
        stage6_validation = "Detected hierarchy edges are a candidate structure. Their correctness depends on whether the underlying RDF actually models a roll-up relationship."
        render_stage("2.6 — Level discovery", stage6_input, stage6_processing, stage6_graph, stage6_validation)

        stage7_input = "Dimension and level structure discovered from object-property roll-up relations."
        stage7_processing = "Represent each dimension as a hierarchy of levels from the most atomic members up to an All level."
        stage7_graph = build_stage_graph(
            "Stage 2.7 — Hierarchies",
            [
                ("Member", "Region"),
                ("Region", "Country"),
                ("Country", "All"),
            ],
            [
                ("Member", "Region"),
                ("Region", "Country"),
                ("Country", "All"),
            ],
            color_map={"Member": "lightblue", "Region": "gold", "Country": "orange", "All": "lightgreen"},
        )
        stage7_validation = "This visual hierarchy is a generic template for any dimension. Real hierarchies may differ significantly depending on the ontology design."
        render_stage("2.7 — Hierarchies", stage7_input, stage7_processing, stage7_graph, stage7_validation)

        stage8_input = f"Schema structure with dimensions: {analysis['dimensions']}, measures: {analysis['measures']}"
        stage8_processing = "Formalize dimension schemas as a set of levels, measures, and their relationships to the cube."
        stage8_graph = build_stage_graph(
            "Stage 2.8 — Dimension schemas",
            [
                ("Cube", "Dimension A"),
                ("Cube", "Dimension B"),
                ("Cube", "Measure set"),
                ("Dimension A", "Level 1"),
                ("Dimension A", "Level 2"),
            ],
            [
                ("Cube", "Dimension A"),
                ("Cube", "Dimension B"),
                ("Cube", "Measure set"),
                ("Dimension A", "Level 1"),
                ("Dimension A", "Level 2"),
            ],
            color_map={"Cube": "tomato", "Dimension A": "lightblue", "Dimension B": "lightblue", "Measure set": "lightcoral", "Level 1": "gold", "Level 2": "gold"},
        )
        stage8_validation = "The schema is intentionally generic. Domain-specific level names and hierarchy design should be confirmed by the user."
        render_stage("2.8 — Dimension schemas", stage8_input, stage8_processing, stage8_graph, stage8_validation)

    with tab3:
        stage9_input = f"Cube schema: fact = {analysis['fact_candidate']}"
        stage9_processing = "Link the fact class, dimensions, and measures into a single cube schema representation."
        stage9_graph = build_stage_graph(
            "Stage 2.9 — Cube schema",
            [
                ("Fact class", analysis["fact_candidate"]),
                ("Dimension 1", analysis["dimensions"][0] if analysis["dimensions"] else "N/A"),
                ("Dimension 2", analysis["dimensions"][1] if len(analysis["dimensions"]) > 1 else "N/A"),
                ("Measure", analysis["measures"][0] if analysis["measures"] else "N/A"),
            ],
            [
                ("Fact class", "Dimension 1"),
                ("Fact class", "Dimension 2"),
                ("Fact class", "Measure"),
            ],
            color_map={"Fact class": "tomato", "Dimension 1": "lightblue", "Dimension 2": "lightblue", "Measure": "lightcoral"},
        )
        stage9_validation = "Valid as a generic cube structure; if the graph contains multiple facts, the user should select the intended cube definition."
        render_stage("2.9 — Cube schema", stage9_input, stage9_processing, stage9_graph, stage9_validation)

        stage10_input = "Dimension members are inferred from the individuals connected to the selected fact and their roll-up relationships."
        stage10_processing = "Create membership links and roll-up tables for each dimension member."
        stage10_graph = build_stage_graph(
            "Stage 2.10 — Dimension instances",
            [
                ("Fact row", "Member A"),
                ("Member A", "Parent level"),
                ("Parent level", "All"),
            ],
            [
                ("Fact row", "Member A"),
                ("Member A", "Parent level"),
                ("Parent level", "All"),
            ],
            color_map={"Fact row": "tomato", "Member A": "lightblue", "Parent level": "gold", "All": "lightgreen"},
        )
        stage10_validation = "Instance-level membership depends on the RDF graph's semantics. If no parent links exist, the hierarchy remains at one level until user modelling is added."
        render_stage("2.10 — Dimension instances", stage10_input, stage10_processing, stage10_graph, stage10_validation)

        stage11_input = "Cuboid lattice is induced from all legal combinations of dimension members and measures."
        stage11_processing = "Generate cuboid nodes and aggregate across drill-down or roll-up paths."
        stage11_graph = build_stage_graph(
            "Stage 2.11 — Cuboids",
            [
                ("Cuboid 1", "Cuboid 2"),
                ("Cuboid 2", "Cuboid 3"),
                ("Cuboid 3", "All"),
            ],
            [
                ("Cuboid 1", "Cuboid 2"),
                ("Cuboid 2", "Cuboid 3"),
                ("Cuboid 3", "All"),
            ],
            color_map={"Cuboid 1": "lightblue", "Cuboid 2": "gold", "Cuboid 3": "orange", "All": "lightgreen"},
        )
        stage11_validation = "Cuboids are generated structurally; the actual aggregation values depend on the dataset and the chosen measure definitions."
        render_stage("2.11 — Cuboids", stage11_input, stage11_processing, stage11_graph, stage11_validation)

    with tab4:
        stage12_input = "MDKG encoding based on QB4OLAP and observation triples."
        stage12_processing = "Map the chosen fact, dimensions, measures, and observations to QB4OLAP resources and observation nodes."
        stage12_graph = build_stage_graph(
            "Stage 2.12 — MDKG encoding",
            [
                ("qb:DataSet", "Cube"),
                ("Cube", "Observation"),
                ("Observation", "Dimension"),
                ("Observation", "Measure"),
            ],
            [
                ("qb:DataSet", "Cube"),
                ("Cube", "Observation"),
                ("Observation", "Dimension"),
                ("Observation", "Measure"),
            ],
            color_map={"qb:DataSet": "tomato", "Cube": "lightblue", "Observation": "gold", "Dimension": "lightgreen", "Measure": "lightcoral"},
        )
        stage12_validation = "The generated Turtle is a valid, reusable MDKG shell. It can be extended with richer QB4OLAP definitions, hierarchy codes, and actual observations."
        render_stage("2.12 — MDKG encoding", stage12_input, stage12_processing, stage12_graph, stage12_validation)

        stage13_input = "OLAP operations are represented as transitions over the cube across different slices and levels."
        stage13_processing = "Apply roll-up, drill-down, slice, and dice to the fact table and display the transformed outcome."
        stage13_graph = build_stage_graph(
            "Stage 2.13 — OLAP operations",
            [
                ("Base cube", "Roll-up"),
                ("Base cube", "Drill-down"),
                ("Base cube", "Slice"),
                ("Base cube", "Dice"),
            ],
            [
                ("Base cube", "Roll-up"),
                ("Base cube", "Drill-down"),
                ("Base cube", "Slice"),
                ("Base cube", "Dice"),
            ],
            color_map={"Base cube": "lightblue", "Roll-up": "gold", "Drill-down": "orange", "Slice": "lightgreen", "Dice": "lightcoral"},
        )
        stage13_validation = "These operations are conceptual. They become executable once the cube schema, dimension membership, and measure aggregation rules are finalized."
        render_stage("2.13 — OLAP operations", stage13_input, stage13_processing, stage13_graph, stage13_validation)

    with tab5:
        st.subheader("MDKG Configuration")
        st.write("Proposed fact class and configuration")
        config_df = pd.DataFrame(
            [
                {"Field": "Fact class", "Value": analysis["fact_candidate"]},
                {"Field": "Grain", "Value": analysis["grain"]},
                {"Field": "Dimensions", "Value": ", ".join(analysis["dimensions"]) if analysis["dimensions"] else "None"},
                {"Field": "Measures", "Value": ", ".join(analysis["measures"]) if analysis["measures"] else "None"},
                {"Field": "Attributes", "Value": ", ".join(analysis["attributes"]) if analysis["attributes"] else "None"},
            ]
        )
        st.dataframe(config_df, use_container_width=True)

        st.markdown("### User confirmation controls")
        fact_choice = st.selectbox("Select fact class", options=analysis["classes"] + [analysis["fact_candidate"]], index=analysis["classes"].index(analysis["fact_candidate"]) if analysis["fact_candidate"] in analysis["classes"] else 0)
        grain_choice = st.text_input("Grain definition", value=analysis["grain"])
        st.text_area("Review and edit dimension narrative", value="The system proposes dimensions based on object properties and class links. Review them before export.")

    with tab6:
        mdkg_ttl = build_mdkg_ttl(analysis)
        st.subheader("Generated MDKG Turtle")
        st.code(mdkg_ttl, language="turtle")
        st.download_button(
            label="Download .ttl",
            data=mdkg_ttl,
            file_name="mdkg_export.ttl",
            mime="text/turtle",
        )

        st.markdown("### Validation report")
        validation_summary = {
            "Triples parsed": len(graph),
            "Classes found": len(analysis["classes"]),
            "Properties found": len(analysis["properties"]),
            "Fact candidate": analysis["fact_candidate"],
            "Status": "Heuristic configuration ready; confirmed by user before final export",
        }
        st.json(validation_summary)


if __name__ == "__main__":
    main()
