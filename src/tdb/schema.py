import random
import time
import math
import streamlit as st

import tdb.config_tdb
from tdb.constraint import TDBMetric
from tdb.optimizer import CostOptimizer
from tdb.datatype import DataType
from tdb.nlfilter import NLFilter
from tdb.stats import NLDatabaseInfo
from tdb.query import NLQueryInfo


def is_aggregate(select_str):
    agg_funcs = ['count', 'sum', 'avg', 'min', 'max']
    return any(agg_func in select_str for agg_func in agg_funcs)


def is_avg_aggregate(select_str):
    return 'avg' in select_str


class NLColumn:
    def __init__(self, name, datatype, processor=None):
        self.name = name
        self.datatype = datatype
        self.processor = processor
        assert not (DataType.is_unstructured_except_text(self.datatype) and self.processor is None)
        # table is initialized when column is added to table.
        self.table = None

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


class NLTable:
    def __init__(self, name):
        self.name = name
        self.cols = {}
        self.db = None

    def add(self, *cols):
        for col in cols:
            col.table = self.name
            self.cols[col.name] = col

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


class NLDatabase:
    def __init__(self, name, con):
        self.name = name
        self.con = con
        self.tables = {}
        self.info = None
        # Join on two tables, e.g., {(table1, table2): (table1, col1, table2, col2)}.
        self.__relationships = {}

    def add(self, *tables):
        for table in tables:
            table.db = self.name
            self.tables[table.name] = table

    def add_relationships(self, *relationships):
        for relationship in relationships:
            table1, col1, table2, col2 = relationship
            assert table1 != table2
            key = (table1, table2) if table1 < table2 else (table2, table1)
            self.__relationships[key] = relationship

    def get_count_columns_for_foreign_key(self, query):
        cols_count = []
        for table1, col1, table2, col2 in self.__relationships.values():
            if table1 in query.tables and table2 in query.tables:
                cols_count.append(col1 + "_c")
        return cols_count

    def init_info(self):
        self.info = NLDatabaseInfo(self)

    def get_col_by_name(self, name):
        cols = [table.cols[name] for table in self.tables.values() if name in table.cols]
        nr_cols = len(cols)
        if nr_cols == 1:
            return cols[0]
        elif nr_cols > 2:
            raise ValueError(f'Multiple columns with the same name: {name} in {", ".join(col.table for col in cols)}')
        else:
            raise ValueError(f'No such column: {name}')

    def get_table_by_col_from_query(self, col_name, query):
        for table_name in query.tables:
            if col_name in self.tables[table_name].cols:
                return table_name
        raise ValueError(f'No table with such column: {col_name}')

    def _get_relationship_cols(self, table1, table2):
        assert table1 != table2
        key = (table1, table2) if table1 < table2 else (table2, table1)
        table1, col1, table2, col2 = self.__relationships[key]
        return (col1, col2) if table1 == key[0] else (col2, col1)

    def execute_sql(self, sql, result_info):
        start = time.time()
        tables = self.con.execute('show tables')
        table_rows = tables.fetchall()
        print(table_rows)
        
        result = self.con.execute(sql)
        if result_info is not None:
            result_info['time_sql'] += time.time() - start
        return result

    # TODO: Check whether there is a better class for containing this method.
    def get_sql_sids(self, fid, col_name, table_name, asc_desc, nr_to_process, nl_filter):
        if table_name != nl_filter.col.table:
            col1, col2 = self._get_relationship_cols(table_name, nl_filter.col.table)
            sql_sids = f"""
            SELECT DISTINCT sid
            FROM (SELECT sid, {col2} FROM {nl_filter.col.table}, scores{fid} WHERE {nl_filter.col.name} = scores{fid}.sid AND score IS NULL) AS temp_scores,
            {table_name}
            WHERE {table_name}.{col1} = temp_scores.{col2}
            ORDER BY {table_name}.{col_name} {asc_desc}
            LIMIT {nr_to_process}"""
        else:
            sql_sids = f"""
            SELECT DISTINCT sid
            FROM (SELECT sid, {col_name} FROM {nl_filter.col.table}, scores{fid} WHERE {nl_filter.col.name} = scores{fid}.sid AND score IS NULL) AS temp_scores
            ORDER BY {col_name} {asc_desc}
            LIMIT {nr_to_process}"""
        return sql_sids

    @staticmethod
    def get_sql_sids_conjunction(fid1, fid2, nr_to_process):
        sql_sids = f"""
        SELECT sid FROM 
        (SELECT scores{fid1}.sid FROM scores{fid1}, scores{fid2}
        WHERE scores{fid1}.sid = scores{fid2}.sid AND scores{fid1}.score IS NULL AND scores{fid2}.score IS NOT NULL) AS temp_scores
        USING SAMPLE {nr_to_process} ROWS"""
        return sql_sids

    def process_unstructured(self, action, query, nl_filters, processed_percent, result_info=None):
        action_type = action[0]
        fid = action[-1]
        nl_filter = nl_filters[fid]
        idx_to_score_new = {}
        if action_type == 'i':
            # Uniform.
            start_ml = time.time()
            idx_to_score_new = nl_filter.update(processed_percent)
            if result_info is not None:
                result_info['time_ml'] += time.time() - start_ml
        elif action_type == 'o':
            # Ordered by column.
            (_, _, col_idx, min_max, _) = action
            col_name = query.cols[col_idx]
            table_name = self.get_table_by_col_from_query(col_name, query)
            asc_desc = 'ASC' if min_max == 'min' else 'DESC'
            nr_to_process = int(nl_filter.col.processor.nr_total * processed_percent)
            sql = self.get_sql_sids(fid, col_name, table_name, asc_desc, nr_to_process, nl_filter)
            sids = self.execute_sql(sql, result_info).df().iloc[:, 0]
            print(f'len(sids) o: {len(sids)}')
            ordering_tpl = (sids, (min_max, col_name))

            start_ml = time.time()
            idx_to_score_new = nl_filter.update(processed_percent, ordering_tpl)
            if result_info is not None:
                result_info['time_ml'] += time.time() - start_ml
        # Update new scores to table.
        if idx_to_score_new:
            self.execute_sql(
                f"UPDATE scores{fid} SET processed=TRUE, score=(CASE sid {' '.join(f'WHEN {key} THEN {val}' for key, val in idx_to_score_new.items())} ELSE score END) WHERE sid IN ({', '.join(str(key) for key in idx_to_score_new.keys())})",
                result_info)
            # self.con.executemany(f"UPDATE scores{fid} SET score=?, processed=TRUE WHERE sid=?", [[val, key] for key, val in idx_to_score_new.items()])

    def profile(self, query, ground_truths=None):
        nl_filters = [NLFilter(self.get_col_by_name(col), text) for col, text in query.nl_preds]
        preprocess_percents = [nl_filter.default_process_percent for nl_filter in nl_filters]
        preprocess_nr_feedbacks = 0
        result_info = {'time_optimize': 0,
                       'time_sql': 0,
                       'time_ml': 0,
                       'estimated_cost': 0,
                       'processed': preprocess_percents,
                       'feedback': [preprocess_nr_feedbacks] * len(nl_filters),
                       'nr_actions': 0}
        # Create scores tables.
        print('About to add scores tables.')
        for fid, nl_filter in enumerate(nl_filters):
            print('Adding scores table for NL filter:', nl_filter.text)
            self.execute_sql(f"DROP TABLE IF EXISTS scores{fid}", result_info)
            self.execute_sql(f"CREATE TABLE scores{fid}(sid INTEGER PRIMARY KEY, score FLOAT, processed BOOLEAN)", result_info)
            if nl_filter.idx_to_score:
                self.execute_sql(f"INSERT INTO scores{fid} VALUES {', '.join(f'({key}, {val}, TRUE)' for key, val in nl_filter.idx_to_score.items())}", result_info)
            # self.con.executemany(f"INSERT INTO scores{fid} VALUES (?, ?, ?)",
            #                      [[key, val, True] for key, val in nl_filter.idx_to_score.items()])
            # Add null scores for remaining rows.
            self.execute_sql(f"""
            INSERT INTO scores{fid} SELECT {nl_filter.col.name}, NULL, FALSE
            FROM (SELECT {nl_filter.col.name}, score FROM {nl_filter.col.table} LEFT JOIN scores{fid} ON {nl_filter.col.table}.{nl_filter.col.name} = scores{fid}.sid) AS temp_scores
            WHERE score IS NULL""", result_info)
        # Get all possible orderings.
        possible_orderings = [('uniform',)]
        for col_name in query.cols:
            possible_orderings.append(('min', col_name))
            possible_orderings.append(('max', col_name))
        
        if tdb.config_tdb.GUI:
            total_nr_requests = sum(
                max(int(nl_filter.col.processor.nr_total * preprocess_percents[fid]), 1)
                for fid, nl_filter in enumerate(nl_filters)
            )
            progress_text = f"Progress Bar (Total # of LLM Requests for Profiling: {total_nr_requests})"
            progress_bar = st.progress(0.0, text=progress_text)
            st.session_state['total_nr_requests'] = total_nr_requests
            st.session_state['nr_requests'] = 0
            st.session_state['progress_text'] = progress_text
            for nl_filter in nl_filters:
                nl_filter.col.processor.progress_bar = progress_bar
        # Preprocess some data.
        fid2runtime = []
        for fid, nl_filter in enumerate(nl_filters):
            start_nl_filter = time.time()
            # To prevent bias towards uniform sampling.
            percent_per_ordering = preprocess_percents[fid] / len(possible_orderings)
            for ordering in possible_orderings:
                action = ('i', 1, fid) if ordering == ('uniform',) else ('o', 1, query.cols.index(ordering[1]), ordering[0], fid)
                self.process_unstructured(action, query, nl_filters, percent_per_ordering, result_info)
            end_nl_filter = time.time()
            time_nl_filter = (
                max(int(nl_filter.col.processor.nr_total * preprocess_percents[fid]), 1)
                if tdb.config_tdb.GUI
                else (end_nl_filter - start_nl_filter)
            )
            print(f'Unit process runtime: {time_nl_filter}')
            fid2runtime.append(time_nl_filter)
        # Collect a small number of user feedbacks.
        for nl_filter in nl_filters:
            for _ in range(preprocess_nr_feedbacks):
                ground_truth_threshold = None if ground_truths is None else ground_truths[nl_filter.text]
                nl_filter.collect_user_feedback(0.5, ground_truth_threshold)
        if tdb.config_tdb.GUI:
            progress_bar.empty()
        return nl_filters, fid2runtime, result_info

    def process(self, query, constraint, nl_filters, fid2runtime, result_info, start_time, ground_truths=None, optimizer_mode='local'):
        # Run query.
        if tdb.config_tdb.GUI:
            updated = True
            is_first = True
            display_info = st.empty()
            st.session_state['under_estimate'] = False
            result_info['is_last'] = False
        action_queue = []
        no_improvement = False
        while True:
            error, lus = self.query_to_compute_error(query, nl_filters, print_error=True, result_info=result_info)
            cur_nr_feedbacks = sum(result_info['feedback'])
            cur_runtime = time.time() - start_time
            if tdb.config_tdb.GUI:
                if not action_queue and not is_first and error > constraint.threshold:
                    # When we under-estimate nesessary cost.
                    if tdb.config_tdb.GUI:
                            st.session_state['under_estimate'] = True
                if updated:
                    updated = False
                    result_info['lus'] = lus
                    yield result_info

            if not (
                constraint.metric == TDBMetric.ERROR and error <= constraint.threshold
            ) and (
                (optimizer_mode == "local" and not no_improvement)
                or (optimizer_mode != "local" and constraint.check_continue(error, cur_nr_feedbacks, cur_runtime, len(nl_filters)))
            ):
                # If queue is empty, add more actions.
                if not action_queue:
                    start_optimize = time.time()
                    if optimizer_mode == 'random':
                        query_info = NLQueryInfo(query, self)
                        optimizer = CostOptimizer(self, fid2runtime, constraint.weight)
                        possible_actions = optimizer.get_all_possible_actions(len(nl_filters), len(query_info.query.cols))
                        print('Randomly selecting next action.')
                        action = random.choice(possible_actions)
                        action_queue.append(action)
                    elif optimizer_mode == 'local':
                        query_info = NLQueryInfo(query, self)
                        optimizer = CostOptimizer(self, fid2runtime, constraint.weight)
                        max_nr_total = max([self.info.tables[name].nr_rows for name in query.tables])
                        actions, *_ = optimizer.optimize_local_search(query_info, nl_filters, max_nr_total, constraint, cur_nr_feedbacks, cur_runtime)
                        if not actions:
                            no_improvement = True
                        action_queue.extend(actions)
                    elif optimizer_mode[0] == 'cost':
                        # One-shot, Multi-shots (i.e., thinking multiple steps ahead)
                        look_ahead = optimizer_mode[1]
                        query_info = NLQueryInfo(query, self)
                        optimizer = CostOptimizer(self, fid2runtime, constraint.weight)
                        max_nr_total = max([self.info.tables[name].nr_rows for name in query.tables])
                        actions = optimizer.optimize(query_info, nl_filters, max_nr_total, look_ahead, constraint, cur_nr_feedbacks, cur_runtime)
                        action_queue.extend(actions)
                    else:
                        raise ValueError(f'No such optimizer mode: {optimizer_mode}')
                    end_optimize = time.time()
                    time_optimize = end_optimize - start_optimize
                    print(f'Current optimization time: {time_optimize}')
                    result_info['time_optimize'] += time_optimize

                if action_queue:
                    if tdb.config_tdb.GUI:
                        updated = True
                        if is_first:
                            is_first = False
                            total_nr_requests = sum(fid2runtime[action[-1]] for action in action_queue if action[0] == 'i' or action[0] == 'o')
                            progress_text = f'Progress Bar (Estimated Total # of LLM Requests: {total_nr_requests})'
                            progress_bar = display_info.progress(0.0, text=progress_text)
                            st.session_state['total_nr_requests'] = total_nr_requests
                            st.session_state['nr_requests'] = 0
                            st.session_state['progress_text'] = progress_text
                            for nl_filter in nl_filters:
                                nl_filter.col.processor.progress_bar = progress_bar

                    action = action_queue.pop(0)
                    result_info['nr_actions'] += 1
                    print(f'Next action: {action}{f"~{query.cols[action[2]]}" if action[0] == "o" else ""}')
                    action_type = action[0]
                    fid = action[-1]
                    nl_filter = nl_filters[fid]
                    if action_type == 'i' or action_type == 'o':  # or action_type == 'c':
                        process_percent_multiple = action[1]
                        processed_percent = process_percent_multiple * nl_filter.default_process_percent
                        result_info['processed'][fid] += processed_percent
                        self.process_unstructured(action, query, nl_filters, processed_percent, result_info)
                    elif action_type == 'u':
                        user_feedback_opt = action[1]
                        result_info['feedback'][fid] += 1
                        ground_truth_threshold = None if ground_truths is None else ground_truths[nl_filter.text]
                        nl_filter.collect_user_feedback(user_feedback_opt, ground_truth_threshold)
                    else:
                        raise ValueError(f'Our action is out of scope: {action}')
            # When error below the given constraint.
            else:
                # Resort to greedy method if error constraint not satisfied.
                if optimizer_mode == 'local' and constraint.metric == TDBMetric.ERROR and error > constraint.threshold:
                    print(f'Resort to greedy method due to error constraint not satisfied: {error}')
                    optimizer_mode = ('cost', 1)
                    continue
                # Stop if satisfies the constraint.
                print('==========QUERY RESULT==========')
                error, lus = self.query_to_compute_error(query, nl_filters, print_error=True, print_result=True, result_info=result_info)
                result_info['error'] = error
                result_info['lus'] = lus
                break

        # print('==========NL FILTER RESULTS==========')
        # for nl_filter in nl_filters:
        #     idxs = nl_filter.idxs_tfu()
        #     # Audio files take too much time to output.
        #     if nl_filter.col.datatype == DataType.AUDIO:
        #         print(idxs.t)
        #     else:
        #         for idx_t in idxs.t:
        #             nl_filter.col.processor.show(idx_t)
        if tdb.config_tdb.GUI:
            display_info.empty()
            st.session_state['under_estimate'] = False
            result_info['is_last'] = True
        yield result_info

    def run_yield(self, query, constraint, ground_truths=None, optimizer_mode='local'):
        start_time = time.time()
        nl_filters, fid2runtime, result_info = self.profile(query, ground_truths)
        yield from self.process(query, constraint, nl_filters, fid2runtime, result_info, start_time, ground_truths, optimizer_mode)

    def run(self, query, constraint, ground_truths=None, optimizer_mode='local'):
        info = next(self.run_yield(query, constraint, ground_truths, optimizer_mode))
        return info

    def query_to_compute_error(self, query, nl_filters, print_error=False, print_result=False, result_info=None):
        # Compute lower and upper bounds.
        # Lower and upper thresholds of NL predicates are given as a list of tuples, e.g., [(lt, ut), ...]
        thresholds = [(nl_filter.lower, nl_filter.upper) for nl_filter in nl_filters]
        sql_l, sql_u, nr_avgs = query.to_lower_upper_sqls(nl_filters, thresholds)
        con_l = self.execute_sql(sql_l, result_info)
        result_l = con_l.fetchall()
        result_u = self.execute_sql(sql_u, result_info).fetchall()
        # print(f'Raw query results: {result_l} {result_u}')
        lus = []
        if query.limit < 0:
            nr_selects = len(con_l.description)
            nr_non_avgs = nr_selects - 2 * nr_avgs
            # Aggregates except avgs.
            for idx in range(nr_non_avgs):
                select_str, *_ = con_l.description[idx]
                if is_aggregate(select_str) and not is_avg_aggregate(select_str):
                    l = result_l[0][idx]
                    u = result_u[0][idx]
                    if l is None or u is None:
                        lus.append((float('-inf'), float('inf')))
                    else:
                        if l > u:
                            temp_val = l
                            l = u
                            u = temp_val
                        lus.append((l, u))
            for idx in range(nr_non_avgs, nr_selects, 2):
                l_s = result_l[0][idx]
                u_s = result_u[0][idx]
                l_c = result_l[0][idx + 1]
                u_c = result_u[0][idx + 1]
                if l_s is None or u_s is None or l_c is None or u_c is None or l_c == 0 or u_c == 0:
                    lus.append((float('-inf'), float('inf')))
                else:
                    if l_s > u_s:
                        temp_val = l_s
                        l_s = u_s
                        u_s = temp_val
                        temp_val = l_c
                        l_c = u_c
                        u_c = temp_val
                    assert l_c <= u_c
                    lus.append((l_s / u_c, u_s / l_c))
        else:
            l = min(query.limit, len(result_l))
            u = min(query.limit, len(result_u))
            lus.append((l, u))

        if print_result:
            print(f'LOWER BOUNDS:\n{result_l}')
            print(f'UPPER BOUNDS:\n{result_u}')

        errors = [1 if math.isnan(error) else error for error in ((u - l) / (u + l) if l != u else 0 for l, u in lus)]
        error_avg = sum(errors) / len(lus)
        if print_error:
            print(f'Error: {error_avg} {errors}, Bounds: {lus}')

        return error_avg, lus

    def query_to_compute_exact_bounds(self, query, nl_filters):
        thresholds = [(nl_filter.lower, nl_filter.upper) for nl_filter in nl_filters]
        sql_l, sql_u, nr_avgs = query.to_lower_upper_sqls(nl_filters, thresholds)
        con_l = self.con.execute(sql_l)
        result_l = con_l.fetchall()
        result_u = self.con.execute(sql_u).fetchall()
        print(f'LOWER RESULTS:\n{result_l}')
        print(f'UPPER RESULTS:\n{result_u}')
        lus = []
        if query.limit < 0:
            nr_selects = len(con_l.description)
            nr_non_avgs = nr_selects - 2 * nr_avgs
            # Aggregates including avgs.
            for idx in range(nr_non_avgs):
                select_str, *_ = con_l.description[idx]
                if is_aggregate(select_str):
                    l = result_l[0][idx]
                    u = result_u[0][idx]
                    if l is None or u is None:
                        lus.append((float('-inf'), float('inf')))
                    else:
                        if l > u:
                            temp_val = l
                            l = u
                            u = temp_val
                        lus.append((l, u))
        else:
            l = min(query.limit, len(result_l))
            u = min(query.limit, len(result_u))
            lus.append((l, u))
        return lus

    def run_baseline(self, query, ground_truths=None):
        # Initialize NL filters.
        nl_filters = [NLFilter(self.get_col_by_name(col), text) for col, text in query.nl_preds]
        # Process all unstructured data.
        preprocess_percent = 1.0
        start_process = time.time()
        for nl_filter in nl_filters:
            nl_filter.update(preprocess_percent)
        end_process = time.time()
        print(f'Time - Process All Images: {end_process - start_process}')

        result_info = {'estimated_cost': 0,
                       'processed': [preprocess_percent] * len(nl_filters),
                       'feedback': [0] * len(nl_filters)}
        # Collect user feedbacks by binary search.
        for fid, nl_filter in enumerate(nl_filters):
            nr_feedbacks = 0
            while True:
                ground_truth_threshold = None if ground_truths is None else ground_truths[nl_filter.text]
                nl_filter.collect_user_feedback(0.5, ground_truth_threshold)
                nr_feedbacks += 1
                if nl_filter.nr_unsure() == 0:
                    break
            result_info['feedback'][fid] = nr_feedbacks
            print(f'Threshold Found / Ground Truth: {nl_filter.upper} / {ground_truths}')

        # Run query.
        for fid, nl_filter in enumerate(nl_filters):
            self.con.execute(f"DROP TABLE IF EXISTS scores{fid}")
            self.con.execute(f"CREATE TABLE scores{fid}(sid INTEGER PRIMARY KEY, score FLOAT, processed BOOLEAN)")
            self.con.executemany(f"INSERT INTO scores{fid} VALUES (?, ?, ?)",
                                 [[key, val, True] for key, val in nl_filter.idx_to_score.items()])

        lus = self.query_to_compute_exact_bounds(query, nl_filters)
        errors = [1 if math.isnan(error) else error for error in ((u - l) / (u + l) if l != u else 0 for l, u in lus)]
        error_avg = sum(errors) / len(lus)
        print(f'Error: {error_avg} {errors}, Bounds: {lus}')
        result_info['error'] = error_avg

        return result_info

    def run_baseline_ordered(self, query, nl_permutation, ground_truths=None):
        is_disjuction = ' or ' in query.sql
        # Initialize NL filters.
        nl_filters = [NLFilter(self.get_col_by_name(col), text) for col, text in query.nl_preds]
        assert len(nl_filters) < 3
        # Reorder NL filters based on the given permutation.
        nl_filters = [nl_filters[idx] for idx in nl_permutation]
        preprocess_percent = 1.0
        result_info = {'estimated_cost': 0,
                       'processed': [preprocess_percent] * len(nl_filters),
                       'feedback': [0] * len(nl_filters)}
        prev_idxs = None
        start_process = time.time()
        for fid, nl_filter in enumerate(nl_filters):
            print(f'Processing {fid}th {nl_filter}')
            # Process all unstructured data
            ordering_tpl = None if prev_idxs is None else (prev_idxs, ('uniform',))
            nl_filter.update(preprocess_percent, ordering_tpl)
            # Collect user feedbacks by binary search.
            nr_feedbacks = 0
            while True:
                ground_truth_threshold = None if ground_truths is None else ground_truths[nl_filter.text]
                nl_filter.collect_user_feedback(0.5, ground_truth_threshold)
                nr_feedbacks += 1
                if nl_filter.nr_unsure() == 0:
                    break
            result_info['feedback'][fid] = nr_feedbacks
            print(f'Threshold Found / Ground Truth: {nl_filter.upper} / {ground_truths}')
            if fid == 0:
                # Prune row indexes to process.
                idxs = nl_filter.false_idxs() if is_disjuction else nl_filter.true_idxs()
                # When we need join.
                if 'furniture' in query.tables:
                    next_filter = nl_filters[1]
                    result = self.con.execute(f"SELECT {next_filter.col.name} FROM images, furniture WHERE images.aid = furniture.aid AND {nl_filter.col.name} IN ({','.join(str(idx) for idx in idxs)})").fetchall()
                    idxs = [row[0] for row in result]
                prev_idxs = idxs if prev_idxs is None else prev_idxs & idxs
        end_process = time.time()
        print(f'Time - Process: {end_process - start_process}')
        # Run query.
        for fid, nl_filter in enumerate(nl_filters):
            self.con.execute(f"DROP TABLE IF EXISTS scores{fid}")
            self.con.execute(f"CREATE TABLE scores{fid}(sid INTEGER PRIMARY KEY, score FLOAT, processed BOOLEAN)")
            self.con.executemany(f"INSERT INTO scores{fid} VALUES (?, ?, ?)",
                                 [[key, val, True] for key, val in nl_filter.idx_to_score.items()])

        lus = self.query_to_compute_exact_bounds(query, nl_filters)
        errors = [1 if math.isnan(error) else error for error in ((u - l) / (u + l) if l != u else 0 for l, u in lus)]
        error_avg = sum(errors) / len(lus)
        print(f'Error: {error_avg} {errors}, Bounds: {lus}')
        result_info['error'] = error_avg

        return result_info

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)
