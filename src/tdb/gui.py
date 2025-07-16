import argparse
import math
import os
import re
import time

import pandas as pd
import altair as alt
import streamlit as st
import tdb.config_tdb

from tdb.optimization.constraint import TDBConstraint
from tdb.data.datatype import DataType
from tdb.data.nldbs import get_nldb_by_name
from tdb.optimization.optimizer import CostOptimizer
from tdb.queries.query import NLQuery, NLQueryInfo

# If GUI, use GPTProcessor and corresponding lower and upper thresholds for NLFilter, and preprocess_nr_feedbacks.
tdb.config_tdb.GUI = True


class DummyDB:
    """Represents ThalamusDB implementation."""

    def __init__(self, dbname):
        """Initialize for given database.

        Args:
            dbname: name of database to initialize for
        """
        if dbname == "Craigslist":
            dbname = "craigslist"
        else:
            raise ValueError(f"Invalid database: {dbname}")
        self.nldb = get_nldb_by_name(dbname)

    def profile(self, sql):
        """Profile NL predicates in query.

        Args:
            query: query to profile
        """
        sql = sql.lower()
        # Temporary fix for TEXT type columns. Need to handle this within the NLQuery class.
        sql = re.sub(r'nl\(title,', 'nl(title_u,', sql)
        sql = re.sub(r'nl\(neighborhood,', 'nl(neighborhood_u,', sql)
        sql = re.sub(r'nl\(url,', 'nl(url_u,', sql)
        query = NLQuery(sql)
        nl_filters, fid2runtime, info = self.nldb.profile(query)
        constraints, estimates = self.estimate(query, nl_filters, fid2runtime, info)

        self.query = query
        self.nl_filters = nl_filters
        self.fid2runtime = fid2runtime
        self.info = info
        self.constraints = constraints
        self.estimates = estimates

    def estimate(self, query, nl_filters, fid2runtime, result_info):
        query_info = NLQueryInfo(query, self.nldb)
        optimizer = CostOptimizer(self.nldb, fid2runtime, 1)
        max_nr_total = max(
            [self.nldb.info.tables[name].nr_rows for name in query.tables]
        )
        cur_nr_feedbacks = sum(result_info["feedback"])
        cur_runtime = sum(fid2runtime)

        errors = [0.8, 0.6, 0.4, 0.2, 0.1, 0.05, 0.01]
        constraints = [TDBConstraint("error", error, 1) for error in errors]

        estimates = []
        for idx, constraint in enumerate(constraints):
            _, est_cost, est_error = optimizer.optimize_local_search(
                query_info,
                nl_filters,
                max_nr_total,
                constraint,
                cur_nr_feedbacks,
                cur_runtime,
            )
            # Resort to exact processing.
            if est_error > constraint.threshold:
                est_error = 0
                est_cost = sum(nl_filter.col.processor.nr_total for nl_filter in nl_filters)
            estimates.append(
                (est_cost, est_error, f"Constraint: Error <= {constraint.threshold}")
            )
        return constraints, estimates

    def process(self, constraint):
        """Process query with constraint.

        Args:
            constraint: constraint to satisfy
        """
        constraint = TDBConstraint(*constraint)
        start_time = time.time()
        method = "local"
        for info in self.nldb.process(
            self.query,
            constraint,
            self.nl_filters,
            self.fid2runtime,
            self.info,
            start_time,
            None,
            method,
        ):
            yield info

    def run(self, sql, constraint):
        """Run query with constraint.

        Args:
            query: query to run
            constraint: constraint to satisfy
        """
        sql = sql.lower()
        query = NLQuery(sql)
        constraint = TDBConstraint(*constraint)
        method = "local"
        for info in self.nldb.run_yield(query, constraint, None, method):
            yield info


@st.cache_resource
def load_db(database):
    print(f"Loading Database: {database}")
    db = DummyDB(database)
    print(f"Finished Loading Database: {database}")
    return db


def profile_query(database, sql):
    print(f"Profiling Query: {sql}")
    db.profile(sql)
    st.session_state["profile_done"] = True
    print(f"Finished Profiling Query: {sql}")


def draw_line_bounds():
    # Update bounds.
    lus = st.session_state["lus"]
    if lus:
        lus = st.session_state["lus"]
        st.write("Deterministic Bounds on Query Result (Updated per Action):")
        print("==========CURRENT QUERY RESULT==========")
        # Upper should come first in order to display values when hovered.
        df_chart = pd.DataFrame(lus, columns=["Upper", "Lower"])
        print(df_chart)
        # st.area_chart(df_chart)
        # st.line_chart(df_chart)
        data_chart = (
            df_chart.reset_index().melt("index").rename(columns={"variable": "Bound"})
        )
        # print(data_chart)

        lines = (
            alt.Chart(data_chart)
            .mark_line()
            .encode(
                x=alt.X("index:O", title="Actions"),
                y=alt.Y("value", title="Value"),
                color=alt.Color("Bound", legend=None),
            )
        )
        points = lines.mark_point().encode(color="Bound", shape="Bound")
        st.altair_chart(
            alt.layer(lines, points).resolve_scale(
                color="independent", shape="independent"
            ),
            theme="streamlit",
            use_container_width=True,
        )


# Interface.
print("RELOADING")

parser = argparse.ArgumentParser()
parser.add_argument("openai_key", type=str, help="OpenAI key")
args = parser.parse_args()
os.environ["OPENAI_API_KEY"] = args.openai_key

st.set_page_config(page_title="ThalamusDB")

with st.sidebar:
    st.markdown(
        """
    # ThalamusDB
    ThalamusDB answers complex queries with natural language predicates on multi-modal data.
    """
    )

    database = st.selectbox("Database:", options=["Craigslist"])
    db = load_db(database)
    with st.expander("Database Schema Info", expanded=True):  # expanded=True
        for table_name, table_info in db.nldb.info.tables.items():
            col_strs = []
            for col_info in table_info.cols.values():
                if not col_info.col.name.endswith("_u") and not col_info.col.name.endswith("_c"):
                    col_str = col_info.col.name
                    if col_info.col.datatype == DataType.IMG:
                        col_str += " :sunrise_over_mountains:"
                    elif col_info.col.datatype == DataType.TEXT:
                        col_str += " :page_facing_up:"
                    col_strs.append(col_str)
            st.markdown(
                f"{table_name}"
                f' ({", ".join(col_strs)})'
                f" [{table_info.nr_rows} rows]"
            )

sql = st.text_area(
    "SQL Aggregate Query with Natural Language Predicates:",
    value="""SELECT Min(Price) FROM Images, Furniture WHERE Images.Aid = Furniture.Aid 
AND (NL(Img, 'wooden table') OR NL(Title, 'good condition'))""",
)
constraint = None

if "profile" not in st.session_state:
    st.session_state["profile"] = None
if "profile_done" not in st.session_state:
    st.session_state["profile_done"] = False
if "process" not in st.session_state:
    st.session_state["process"] = None
if "stop" not in st.session_state:
    st.session_state["stop"] = None
if "under_estimate" not in st.session_state:
    st.session_state['under_estimate'] = False


def click_profile():
    st.session_state["profile"] = (database, sql)
    st.session_state["profile_done"] = False


def click_process():
    st.session_state["process"] = (database, sql, constraint)
    st.session_state["stop"] = None
    profile_placeholder.empty()
    proceed_btn.empty()


def click_stop():
    st.session_state["stop"] = (database, sql, constraint)
    st.session_state["process"] = None


placeholder = None
warning_placeholder = None
profile_placeholder = None
proceed_btn = None
if st.session_state["profile"] != (database, sql):
    st.button("Start Profiling", on_click=click_profile)
else:
    if not st.session_state["profile_done"]:
        profile_query(database, sql)

    # Display estimates.
    df_estimate = pd.DataFrame(db.estimates, columns=["Cost", "Error", "Option"])
    print(df_estimate)
    # Remove redundant options based on cost and error.
    df_estimate = df_estimate.groupby(["Cost", "Error"]).last().reset_index()
    # Plot estimates.
    chart = (
        alt.Chart(df_estimate)
        .mark_line(point=True)
        .encode(
            x=alt.X("Cost", title="Estimated # of LLM Requests"),
            y=alt.Y("Error", title="Estimated Error"),
        )
    )
    text = chart.mark_text(align="left", baseline="middle").encode(
        text="Option",
    )
    if profile_placeholder is None:
        profile_placeholder = st.empty()
    with profile_placeholder.container():
        st.write(f"Finished Profiling Query (Estimated Cost vs Error):")
        st.altair_chart(chart + text, theme="streamlit", use_container_width=True)

        constraint_max = 1.0
        constraint_value = float(
            st.slider(
                f"Error Constraint (Upper Bound):",
                min_value=0.0,
                max_value=constraint_max,
                value=0.1,
            )
        )
    constraint = ("error", constraint_value, 1)

    if st.session_state["process"] != (database, sql, constraint):
        proceed_btn = st.empty()
        with proceed_btn.container():
            st.button("Proceed with Error Constraint", on_click=click_process)
    else:
        if st.session_state["stop"] != (database, sql, constraint):
            stop_btn = st.empty()
            with stop_btn.container():
                st.button("Stop Processing", on_click=click_stop)
            st.session_state["lus"] = []
            for info in db.process(constraint):
                if not info["is_last"]:
                    lus = info["lus"]
                    if not math.isinf(lus[0][0]) and not math.isinf(lus[0][1]):
                        st.session_state["lus"].append((lus[0][1], lus[0][0]))
                    # To arrange its location.
                    if warning_placeholder is None:
                        warning_placeholder = st.empty()
                    # Warning if post-processing.
                    if st.session_state['under_estimate']:
                        warning_placeholder.warning("Post-Processing (Beyond Estimated # of Requests) to Satisfy Error Constraint!")
                    # To arrange its location.
                    if placeholder is None:
                        placeholder = st.empty()
                    with placeholder.container():
                        draw_line_bounds()
            if warning_placeholder is not None:
                warning_placeholder.empty()
            st.write(f"Finished Processing Query with Final Error: {info['error']}")
            stop_btn.empty()
        else:
            st.write("Processing Stopped!")
            placeholder = st.empty()
            with placeholder.container():
                draw_line_bounds()
