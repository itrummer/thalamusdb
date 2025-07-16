'''
Created on Jul 16, 2025

@author: immanueltrummer
'''
import math
import random
import time

from tdb.optimization.constraint import TDBMetric
from tdb.optimization.optimizer import CostOptimizer
from tdb.optimization.profiler import Profiler
from tdb.queries.query import NLQueryInfo, is_aggregate, is_avg_aggregate


class ExecutionEngine:
    """ Execution engine for processing SQL queries with NL predicates. """

    def __init__(self, nldb, con):
        """ Initializes the execution engine with a database and connection.
        
        Args:
            nldb: The natural language database to execute queries against.
            con: The database connection object.
        """
        self.nldb = nldb
        self.con = con
    
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
            table_name = self.nldb.get_table_by_col_from_query(col_name, query)
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

    def process(self, query, constraint, nl_filters, fid2runtime, result_info, start_time, ground_truths=None, optimizer_mode='local'):
        # Run query.
        action_queue = []
        no_improvement = False
        while True:
            error, lus = self.query_to_compute_error(query, nl_filters, print_error=True, result_info=result_info)
            cur_nr_feedbacks = sum(result_info['feedback'])
            cur_runtime = time.time() - start_time

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
                        query_info = NLQueryInfo(query, self.nldb)
                        optimizer = CostOptimizer(self, fid2runtime, constraint.weight)
                        possible_actions = optimizer.get_all_possible_actions(len(nl_filters), len(query_info.query.cols))
                        print('Randomly selecting next action.')
                        action = random.choice(possible_actions)
                        action_queue.append(action)
                    elif optimizer_mode == 'local':
                        query_info = NLQueryInfo(query, self.nldb)
                        optimizer = CostOptimizer(self, fid2runtime, constraint.weight)
                        max_nr_total = max([self.nldb.info.tables[name].nr_rows for name in query.tables])
                        actions, *_ = optimizer.optimize_local_search(query_info, nl_filters, max_nr_total, constraint, cur_nr_feedbacks, cur_runtime)
                        if not actions:
                            no_improvement = True
                        action_queue.extend(actions)
                    elif optimizer_mode[0] == 'cost':
                        # One-shot, Multi-shots (i.e., thinking multiple steps ahead)
                        look_ahead = optimizer_mode[1]
                        query_info = NLQueryInfo(query, self.nldb)
                        optimizer = CostOptimizer(self, fid2runtime, constraint.weight)
                        max_nr_total = max([self.nldb.info.tables[name].nr_rows for name in query.tables])
                        actions = optimizer.optimize(query_info, nl_filters, max_nr_total, look_ahead, constraint, cur_nr_feedbacks, cur_runtime)
                        action_queue.extend(actions)
                    else:
                        raise ValueError(f'No such optimizer mode: {optimizer_mode}')
                    end_optimize = time.time()
                    time_optimize = end_optimize - start_optimize
                    print(f'Current optimization time: {time_optimize}')
                    result_info['time_optimize'] += time_optimize

                if action_queue:
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
        
        yield result_info

    def run_yield(self, query, constraint, ground_truths=None, optimizer_mode='local'):
        start_time = time.time()
        profiler = Profiler(self)
        nl_filters, fid2runtime = profiler.profile(query, None)
        result_info = {'error': 0,
                       'lus': [],
                       'time_optimize': 0,
                       'time_sql': 0,
                       'time_ml': 0,
                       'estimated_cost': 0,
                       'processed': [0] * len(nl_filters),
                       'feedback': [0] * len(nl_filters),
                       'nr_actions': 0}
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