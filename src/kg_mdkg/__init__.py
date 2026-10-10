import pandas as pd
import streamlit as st
from rdflib import Graph

from src.kg_mdkg.core import (
    analyze_graph,
    build_mdkg_ttl,
    build_stage_graph,
    parse_uploaded_graph,
    sample_ttl,
)

st.set_page_config(page_title="KG → MDKG Workbench", layout="wide")


def render_stage(title: str, input_summary: str, processing_summary: str, graph_obj, validation_summary: str):
    st.subheader(title)
    left, right = st.columns([1, 1])
    with left:
        st.markdown("**1. Input**")
        st.write(input_summary)
        st.markdown("**2. Processing**")
        st.write(processing_summary)
    with right:
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
    st.caption("Universal KG → MDKG Converter with Graphical Output")

    with st.sidebar:
        st.header("Upload RDF/Turtle files")
        uploaded_files = st.file_uploader(
            "Choose TTL files",
            type=["ttl"],
            accept_multiple_files=True,
            key="ttl_uploads"
        )
        st.markdown("---")
        st.markdown("Supported RDF modes")
        st.write("• TBox only")
        st.write("• ABox only")
        st.write("• TBox + ABox")
        st.write("• Combined TTL")
        st.write("• Existing QB/QB4OLAP")

    if uploaded_files:
        graph = parse_uploaded_graph(uploaded_files)
        message = f"Loaded {len(uploaded_files)} uploaded Turtle file(s)."
    else:
        graph = Graph().parse(data=sample_ttl, format="turtle")
        message = "Loaded built-in sample KG for demonstration."

    analysis = analyze_graph(graph)

    st.info(message)

    st.subheader("KG Explorer")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Classes", len(analysis["classes"]))
    with c2:
        st.metric("Properties", len(analysis["properties"]))
    with c3:
        st.metric("Individuals", len(analysis["individuals"]))

    summary = pd.DataFrame([
        {"Category": "Classes", "Count": len(analysis["classes"])},
        {"Category": "Properties", "Count": len(analysis["properties"])},
        {"Category": "Individuals", "Count": len(analysis["individuals"])},
        {"Category": "Triples", "Count": len(graph)},
    ])
    st.dataframe(summary, use_container_width=True)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Stages 2.1–2.4",
        "Stages 2.5–2.8",
        "Stages 2.9–2.11",
        "Stages 2.12–2.13",
        "Configuration",
        "Export",
    ])

    with tab1:
        stage1_graph = build_stage_graph(
            "Stage 2.1 — Analysis question",
            [
                ("Objective", "Find fact-oriented analytical target"),
                ("Fact candidate", analysis["fact_candidate"]),
                ("Grain", analysis["grain"]),
            ],
            [("Objective", "Fact candidate"), ("Fact candidate", "Grain")],
            {"Objective": "lightblue", "Fact candidate": "gold", "Grain": "lightgreen"},
        )
        render_stage(
            "2.1 — Analysis question",
            "Analyse the graph and propose a fact-based analytical objective.",
            "Choose the most connected class as a fact candidate and define its grain.",
            stage1_graph,
            "Proposed default only; user confirmation is required for the final fact/grain choice.",
        )

        stage2_graph = build_stage_graph(
            "Stage 2.2 — Fact and grain",
            [
                ("Fact class", analysis["fact_candidate"]),
                ("Grain", analysis["grain"]),
                ("Dimension candidates", ", ".join(analysis["dimensions"]) if analysis["dimensions"] else "none"),
            ],
            [("Fact class", "Grain"), ("Grain", "Dimension candidates")],
            {"Fact class": "tomato", "Grain": "orange", "Dimension candidates": "lightgreen"},
        )
        render_stage(
            "2.2 — Fact and grain",
            f"Fact class: {analysis['fact_candidate']}\nPossible dimensions: {analysis['dimensions']}",
            "Assign one observation unit and define the grain of the fact table.",
            stage2_graph,
            "The grain is a proposal; validate it against business meaning before export.",
        )

        stage3_graph = build_stage_graph(
            "Stage 2.3 — Property classification",
            [
                ("Measures", ", ".join(analysis["measures"]) if analysis["measures"] else "none"),
                ("Dimensions", ", ".join(analysis["dimensions"]) if analysis["dimensions"] else "none"),
                ("Attributes", ", ".join(analysis["attributes"]) if analysis["attributes"] else "none"),
            ],
            [("Measures", "Dimensions"), ("Dimensions", "Attributes")],
            {"Measures": "lightcoral", "Dimensions": "lightblue", "Attributes": "lightgreen"},
        )
        render_stage(
            "2.3 — Property classification",
            f"Properties found: {analysis['properties']}",
            "Classify properties as numeric measures, structural dimensions, and descriptive attributes.",
            stage3_graph,
            "Heuristic classification—must be reviewed for semantic correctness.",
        )

        fact_table = analysis["fact_table"].copy()
        st.subheader("2.4 — Fact table")
        st.write("**Input**")
        st.write(f"Fact class: {analysis['fact_candidate']}")
        st.write("**Processing**")
        st.write("Build a fact row table by collecting subject–predicate–object triples tied to the selected fact class.")
        st.write("**Graphical result**")
        st.dataframe(fact_table.head(25), use_container_width=True)
        st.write("**Validation**")
        st.write("The fact table is a structured observation preview. It should be confirmed before cube export.")

    with tab2:
        agg_graph = build_stage_graph(
            "Stage 2.5 — Aggregate function",
            [
                ("Measure", analysis["measures"][0] if analysis["measures"] else "measureValue"),
                ("Aggregate", "SUM/AVG/MIN/MAX/COUNT"),
                ("Result", "Aggregated fact view"),
            ],
            [("Measure", "Aggregate"), ("Aggregate", "Result")],
            {"Measure": "lightcoral", "Aggregate": "gold", "Result": "lightgreen"},
        )
        render_stage(
            "2.5 — Aggregate function",
            f"Candidate measures: {analysis['measures']}",
            "Choose the measure and permitted aggregation rule for the cube.",
            agg_graph,
            "Aggregation is assumed to be generic; a domain expert should validate it.",
        )

        level_graph = build_stage_graph(
            "Stage 2.6 — Level discovery",
            [
                ("Member", "Lowest grain"),
                ("Parent", "Roll-up level"),
                ("All", "Top level"),
            ],
            [("Member", "Parent"), ("Parent", "All")],
            {"Member": "lightblue", "Parent": "gold", "All": "lightgreen"},
        )
        render_stage(
            "2.6 — Level discovery",
            f"Hierarchy candidates: {analysis['level_candidates']}",
            "Discover parent-child roll-up paths and level membership for each dimension.",
            level_graph,
            "Hierarchy recovery is approximated from RDF structure and should be reviewed.",
        )

        hierarchy_graph = build_stage_graph(
            "Stage 2.7 — Hierarchies",
            [("Member", "Region"), ("Region", "Country"), ("Country", "All")],
            [("Member", "Region"), ("Region", "Country"), ("Country", "All")],
            {"Member": "lightblue", "Region": "gold", "Country": "orange", "All": "lightgreen"},
        )
        render_stage(
            "2.7 — Hierarchies",
            "Dimension hierarchy template derived from roll-up patterns.",
            "Map each dimension into a hierarchy with a top All level.",
            hierarchy_graph,
            "This is a generic hierarchy pattern; actual levels depend on the ontology.",
        )

        schema_graph = build_stage_graph(
            "Stage 2.8 — Dimension schemas",
            [
                ("Cube", "Dimension A"),
                ("Cube", "Dimension B"),
                ("Cube", "Measure set"),
                ("Dimension A", "Level 1"),
                ("Dimension A", "Level 2"),
            ],
            [("Cube", "Dimension A"), ("Cube", "Dimension B"), ("Cube", "Measure set"), ("Dimension A", "Level 1"), ("Dimension A", "Level 2")],
            {"Cube": "tomato", "Dimension A": "lightblue", "Dimension B": "lightblue", "Measure set": "lightcoral", "Level 1": "gold", "Level 2": "gold"},
        )
        render_stage(
            "2.8 — Dimension schemas",
            f"Dimensions: {analysis['dimensions']}\nMeasures: {analysis['measures']}",
            "Formalize each dimension as an ordered level system related to the cube.",
            schema_graph,
            "This is the canonical schema template. The final dimension definitions should be confirmed by the user.",
        )

    with tab3:
        cube_graph = build_stage_graph(
            "Stage 2.9 — Cube schema",
            [
                ("Fact", analysis["fact_candidate"]),
                ("Dimension 1", analysis["dimensions"][0] if analysis["dimensions"] else "N/A"),
                ("Dimension 2", analysis["dimensions"][1] if len(analysis["dimensions"]) > 1 else "N/A"),
                ("Measure", analysis["measures"][0] if analysis["measures"] else "N/A"),
            ],
            [("Fact", "Dimension 1"), ("Fact", "Dimension 2"), ("Fact", "Measure")],
            {"Fact": "tomato", "Dimension 1": "lightblue", "Dimension 2": "lightblue", "Measure": "lightcoral"},
        )
        render_stage(
            "2.9 — Cube schema",
            f"Selected fact: {analysis['fact_candidate']}",
            "Link the fact to dimensions and measures to define a cube model.",
            cube_graph,
            "A cube skeleton is created; if multiple fact classes exist, the user must select the business fact.",
        )

        dim_members_graph = build_stage_graph(
            "Stage 2.10 — Dimension instances",
            [("Fact row", "Member A"), ("Member A", "Parent level"), ("Parent level", "All")],
            [("Fact row", "Member A"), ("Member A", "Parent level"), ("Parent level", "All")],
            {"Fact row": "tomato", "Member A": "lightblue", "Parent level": "gold", "All": "lightgreen"},
        )
        render_stage(
            "2.10 — Dimension instances",
            "Dimension members are inferred from individuals and roll-up links.",
            "Map each fact row to dimension members and compute membership hierarchy.",
            dim_members_graph,
            "Member hierarchies are inferred structurally unless explicit RDF roll-up relations exist.",
        )

        cuboids_graph = build_stage_graph(
            "Stage 2.11 — Cuboids",
            [("Cuboid 1", "Cuboid 2"), ("Cuboid 2", "Cuboid 3"), ("Cuboid 3", "All")],
            [("Cuboid 1", "Cuboid 2"), ("Cuboid 2", "Cuboid 3"), ("Cuboid 3", "All")],
            {"Cuboid 1": "lightblue", "Cuboid 2": "gold", "Cuboid 3": "orange", "All": "lightgreen"},
        )
        render_stage(
            "2.11 — Cuboids",
            "A cuboid lattice is induced from combinations of dimensions and measures.",
            "Create aggregated views for roll-up and drill-down operations.",
            cuboids_graph,
            "Cuboids are structural abstractions; actual aggregated values depend on the chosen measure semantics.",
        )

    with tab4:
        mdkg_graph = build_stage_graph(
            "Stage 2.12 — MDKG encoding",
            [("qb:DataSet", "Cube"), ("Cube", "Observation"), ("Observation", "Dimension"), ("Observation", "Measure")],
            [("qb:DataSet", "Cube"), ("Cube", "Observation"), ("Observation", "Dimension"), ("Observation", "Measure")],
            {"qb:DataSet": "tomato", "Cube": "lightblue", "Observation": "gold", "Dimension": "lightgreen", "Measure": "lightcoral"},
        )
        render_stage(
            "2.12 — MDKG encoding",
            "Generate a QB4OLAP-like RDF description of the cube.",
            "Create dataset, structure, dimension properties, measures and observation triples.",
            mdkg_graph,
            "The export is a valid MDKG shell and can be refined with domain-specific hierarchy coding.",
        )

        olap_graph = build_stage_graph(
            "Stage 2.13 — OLAP operations",
            [("Cube", "Roll-up"), ("Cube", "Drill-down"), ("Cube", "Slice"), ("Cube", "Dice")],
            [("Cube", "Roll-up"), ("Cube", "Drill-down"), ("Cube", "Slice"), ("Cube", "Dice")],
            {"Cube": "lightblue", "Roll-up": "gold", "Drill-down": "orange", "Slice": "lightgreen", "Dice": "lightcoral"},
        )
        render_stage(
            "2.13 — OLAP operations",
            "Conceptual OLAP transitions over the cube.",
            "Apply roll-up, drill-down, slice and dice to the fact table.",
            olap_graph,
            "Operational semantics are defined once the cube structure and aggregation rules are accepted by the user.",
        )

    with tab5:
        st.subheader("MDKG Configuration")
        config_df = pd.DataFrame([
            {"Field": "Fact class", "Value": analysis["fact_candidate"]},
            {"Field": "Grain", "Value": analysis["grain"]},
            {"Field": "Dimensions", "Value": ", ".join(analysis["dimensions"]) if analysis["dimensions"] else "None"},
            {"Field": "Measures", "Value": ", ".join(analysis["measures"]) if analysis["measures"] else "None"},
            {"Field": "Attributes", "Value": ", ".join(analysis["attributes"]) if analysis["attributes"] else "None"},
        ])
        st.dataframe(config_df, use_container_width=True)

        st.markdown("### User confirmation panel")
        st.selectbox("Fact class", options=analysis["classes"] + [analysis["fact_candidate"]], index=0 if analysis["classes"] else 0)
        st.text_input("Grain definition", value=analysis["grain"])
        st.text_area("Dimension review", value="The system proposes dimensions and measures from RDF structure. Review them before export.")

    with tab6:
        mdkg_ttl = build_mdkg_ttl(analysis)
        st.subheader("MDKG export")
        st.code(mdkg_ttl, language="turtle")
        st.download_button("Download .ttl", mdkg_ttl, file_name="mdkg_export.ttl", mime="text/turtle")

        validation = {
            "Triples parsed": len(graph),
            "Classes": len(analysis["classes"]),
            "Properties": len(analysis["properties"]),
            "Individuals": len(analysis["individuals"]),
            "Fact candidate": analysis["fact_candidate"],
            "Status": "Heuristic configuration generated. Final approval required before production MDKG export.",
        }
        st.json(validation)


if __name__ == "__main__":
    main()

