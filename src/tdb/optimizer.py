import copy
import itertools
import math
import random
import time

import tdb.config_tdb
from tdb.cardinality import CardinalityModel
from tdb.constraint import TDBMetric


class CostOptimizer:
    def __init__(self, nldb, fid2runtime, metric_ratio):
        self.nldb = nldb
        # Set costs of image processing and collecting user feedback.
        # self.process_cost = 1.0
        # self.user_feedback_cost = 10.0
        self.process_percent_multiple = 1
        self.user_feedback_opts = [0.5]
        self.fid2runtime = fid2runtime
        self.metric_ratio = metric_ratio

    @staticmethod
    def error_metric(l, u):
        error = (u - l) / (u + l) if l != u else 0
        return 1 if math.isnan(error) else error

    @staticmethod
    def bounds_count(cardi, nr_limit):
        l = cardi.p_t * cardi.nr_total
        u = (1 - cardi.p_f) * cardi.nr_total
        if nr_limit >= 0:
            l = min(nr_limit, l)
            u = min(nr_limit, u)
        return l, u

    @staticmethod
    def bounds_sum(cardi, col_info):
        # Bounds for prioritized.
        ordering = ('max', col_info.col.name)
        ratio = None if cardi.ordering_to_ratio is None else cardi.ordering_to_ratio.get(ordering)
        # print(f'ratio: {ordering} {ratio}')
        if ratio is None or ratio == 0:
            l = col_info.avg_val * cardi.p_t * cardi.nr_total
            u = col_info.avg_val * cardi.p_tu * cardi.nr_total
        else:
            n_t = cardi.s_t * ratio * cardi.nr_total
            l = n_t * (col_info.max_val - (col_info.max_val - col_info.min_val) * (n_t - 1) / (2 * (cardi.nr_total - 1))) \
                + col_info.avg_val * max(0, cardi.p_t * cardi.nr_total - n_t)
            n_tu = cardi.s_tu * ratio * cardi.nr_total
            u = n_tu * (col_info.max_val - (col_info.max_val - col_info.min_val) * (n_tu - 1) / (2 * (cardi.nr_total - 1))) \
                + col_info.avg_val * max(0, cardi.p_tu * cardi.nr_total - n_tu)
        return l, u

    @staticmethod
    def min_expected_value(start_i, p, k, n, col_info):
        if p == 0:
            return 0
            # return col_info.max_val
        d = (col_info.max_val - col_info.min_val) / (n - 1)
        min_v = col_info.min_val + d * start_i
        ak = min_v + d * (k - 1)
        ev = min_v - ak * pow(1 - p, k)
        # Plus below.
        ev += (d * ((1 - p) - pow(1 - p, k))) / p
        return ev

    @staticmethod
    def bounds_from_p_min(start_i, p_l, p_u, k, nr_total, col_info):
        l = CostOptimizer.min_expected_value(start_i, p_l, k, nr_total, col_info)
        u = CostOptimizer.min_expected_value(start_i, p_u, k, nr_total, col_info)
        return l, u

    @staticmethod
    def bounds_min(cardi, col_info):
        ordering = ('min', col_info.col.name)
        ratio = None if cardi.ordering_to_ratio is None else cardi.ordering_to_ratio.get(ordering)
        # print(f'ratio: {ordering} {ratio}')
        # print(p_l, p_u)
        if ratio is None or ratio == 0:
            # Bounds for uniform.
            p_l = cardi.p_tu
            p_u = cardi.p_t
            l_uni, u_uni = CostOptimizer.bounds_from_p_min(0, p_l, p_u, cardi.nr_total, cardi.nr_total, col_info)
            if p_l == 0:
                l_uni = col_info.min_val
            if p_u == 0:
                u_uni = col_info.max_val
            return l_uni, u_uni
        else:
            # Bounds for prioritized.
            p_l_o = cardi.s_tu
            p_u_o = cardi.s_t
            nr_rows = ratio * cardi.nr_total
            l_o, u_o = CostOptimizer.bounds_from_p_min(0, p_l_o, p_u_o, nr_rows, cardi.nr_total, col_info)

            p_l = cardi.p_tu
            p_u = cardi.p_t
            n = cardi.nr_total - nr_rows
            l_uni, u_uni = CostOptimizer.bounds_from_p_min(nr_rows, p_l, p_u, n, cardi.nr_total, col_info)

            l = l_o + l_uni * pow(1 - p_l_o, nr_rows)
            u = u_o + u_uni * pow(1 - p_u_o, nr_rows)
            if p_l_o == 0 and p_l == 0:
                l = col_info.min_val
            if p_u_o == 0 and p_u == 0:
                u = col_info.max_val
            return l, u

    @staticmethod
    def max_expected_value(start_i, p, k, n, col_info):
        if p == 0:
            return 0
            # return col_info.min_val
        d = (col_info.max_val - col_info.min_val) / (n - 1)
        max_v = col_info.max_val - d * start_i
        ak = max_v - d * (k - 1)
        ev = max_v - ak * pow(1 - p, k)
        # Minus below.
        ev -= (d * ((1 - p) - pow(1 - p, k))) / p
        return ev

    @staticmethod
    def bounds_from_p_max(start_i, p_l, p_u, k, nr_total, col_info):
        l = CostOptimizer.max_expected_value(start_i, p_l, k, nr_total, col_info)
        u = CostOptimizer.max_expected_value(start_i, p_u, k, nr_total, col_info)
        return l, u

    @staticmethod
    def bounds_max(cardi, col_info):
        ordering = ('max', col_info.col.name)
        ratio = None if cardi.ordering_to_ratio is None else cardi.ordering_to_ratio.get(ordering)
        # print(f'ratio: {ordering} {ratio}')
        # print(cardi.ordering_to_ratio)
        if ratio is None or ratio == 0:
            # Bounds for uniform.
            p_l = cardi.p_t
            p_u = cardi.p_tu
            l_uni, u_uni = CostOptimizer.bounds_from_p_max(0, p_l, p_u, cardi.nr_total, cardi.nr_total, col_info)
            if p_l == 0:
                l_uni = col_info.min_val
            if p_u == 0:
                u_uni = col_info.max_val
            return l_uni, u_uni
        else:
            # Bounds for prioritized.
            p_l_o = cardi.s_t
            p_u_o = cardi.s_tu
            nr_rows = ratio * cardi.nr_total
            l_o, u_o = CostOptimizer.bounds_from_p_max(0, p_l_o, p_u_o, nr_rows, cardi.nr_total, col_info)

            p_l = cardi.p_t
            p_u = cardi.p_tu
            n = cardi.nr_total - nr_rows
            l_uni, u_uni = CostOptimizer.bounds_from_p_max(nr_rows, p_l, p_u, n, cardi.nr_total, col_info)

            l = l_o + l_uni * pow(1 - p_l_o, nr_rows)
            u = u_o + u_uni * pow(1 - p_u_o, nr_rows)
            if p_l_o == 0 and p_l == 0:
                l = col_info.min_val
            if p_u_o == 0 and p_u == 0:
                u = col_info.max_val
            return l, u

    def bounds_agg(self, cardi, query_info):
        if query_info.query.limit >= 0:
            l, u = CostOptimizer.bounds_count(cardi, query_info.query.limit)
        elif query_info.agg_func == 'count':
            if len(query_info.cols_count) > 0:
                if len(query_info.cols_count) > 1:
                    raise ValueError(f'Currently, only support one count column: {query_info.cols_count}')
                col_info = self.nldb.info.get_col_info_by_name(query_info.cols_count[0])
                l, u = CostOptimizer.bounds_sum(cardi, col_info)
            else:
                l, u = CostOptimizer.bounds_count(cardi, query_info.query.limit)
        else:
            col_info = self.nldb.info.get_col_info_by_name(query_info.agg_col)
            if query_info.agg_func == 'sum':
                l, u = CostOptimizer.bounds_sum(cardi, col_info)
            elif query_info.agg_func == 'avg':
                l_s, u_s = CostOptimizer.bounds_sum(cardi, col_info)
                query_info_count = copy.copy(query_info)
                query_info_count.agg_func = 'count'
                l_c, u_c = self.bounds_agg(cardi, query_info_count)
                l = l_s / u_c
                u = u_s / l_c if l_c != 0 else float('inf')
            elif query_info.agg_func == 'min':
                # prioritized = ordering is not None and ordering[0] == 'min' and ordering[1] == col_info.col.name
                l, u = CostOptimizer.bounds_min(cardi, col_info)
            elif query_info.agg_func == 'max':
                # prioritized = ordering is not None and ordering[0] == 'max' and ordering[1] == col_info.col.name
                l, u = CostOptimizer.bounds_max(cardi, col_info)
            else:
                raise ValueError(f'Unknown aggregation function: {query_info}')
        return l, u

    def error_agg(self, cardi, query_info):
        l, u = self.bounds_agg(cardi, query_info)
        return CostOptimizer.error_metric(l, u)

    def error_process(self, action, query_info, nl_filters, f_nrss, c_model):
        action_type = action[0]
        fid = action[-1]
        process_percent_multiple = action[1]

        f_nrss_estimated = f_nrss.copy()
        process_percent = nl_filters[fid].default_process_percent * process_percent_multiple
        if action_type == 'i':
            f_nrss_estimated[fid] = f_nrss[fid].estimate(process_percent)
        elif action_type == 'o':
            (_, _, col_idx, min_max, _) = action
            col = query_info.query.cols[col_idx]
            ordering = (min_max, col)
            f_nrss_estimated[fid] = f_nrss[fid].estimate(process_percent, ordering)

        cardi_estimated = c_model.eval(f_nrss_estimated)
        error = self.error_agg(cardi_estimated, query_info)  # , ordering)
        return error, cardi_estimated

    def error_feedback(self, action, query_info, nl_filters, f_nrss, c_model):
        (_, user_feedback_opt, fid) = action
        nrs_yes, nrs_no = nl_filters[fid].estimate_nrs_tfu(user_feedback_opt)
        # When user feedback is yes.
        f_nrss_yes = f_nrss.copy()
        f_nrss_yes[fid] = nrs_yes
        cardi_yes = c_model.eval(f_nrss_yes)
        error_yes = self.error_agg(cardi_yes, query_info)
        # When user feedback is no.
        f_nrss_no = f_nrss.copy()
        f_nrss_no[fid] = nrs_no
        cardi_no = c_model.eval(f_nrss_no)
        error_no = self.error_agg(cardi_no, query_info)

        error = error_yes * user_feedback_opt + error_no * (1 - user_feedback_opt)
        return error, cardi_yes, cardi_no

    def error_action(self, action, query_info, nl_filters, f_nrss, c_model):
        action_type = action[0]
        if action_type == 'i' or action_type == 'o':  # or action_type == 'c':
            return self.error_process(action, query_info, nl_filters, f_nrss, c_model)
        elif action_type == 'u':
            return self.error_feedback(action, query_info, nl_filters, f_nrss, c_model)
        else:
            raise ValueError(f'Our action is out of scope: {action}')

    def get_all_possible_actions(self, nr_nl_filters, nr_cols):
        actions = []
        for fid in range(nr_nl_filters):
            # Uniform sampling.
            actions.append(('i', self.process_percent_multiple, fid))
            # Prioritized processing.
            for col_idx in range(nr_cols):
                for min_max in ['min', 'max']:
                    actions.append(('o', self.process_percent_multiple, col_idx, min_max, fid))
            # Correlated processing.
            # for other_fid in range(nr_nl_filters):
            #     if fid != other_fid:
            #         actions.append(('c', self.process_percent_multiple, other_fid, fid))
            # User feedback.
            if not tdb.config_tdb.GUI:
                for user_feedback_opt in self.user_feedback_opts:
                    actions.append(('u', user_feedback_opt, fid))
        return actions

    @staticmethod
    def meaningful_actions(possible_actions, nl_filters, action2cnt):
        fid2cnt_process = {}
        for action, cnt in action2cnt.items():
            fid = action[-1]
            if action[0] != 'u':
                fid2cnt_process[fid] = fid2cnt_process.get(fid, 0) + cnt
        has_process = bool(fid2cnt_process)

        filtered = []
        for action in possible_actions:
            fid = action[-1]
            nl_filter = nl_filters[fid]
            if action[0] == 'u':
                if nl_filter.nr_unsure() > 0 or has_process:
                    filtered.append(action)
            else:
                processed_percent = len(nl_filter.idx_to_score) / nl_filter.col.processor.nr_total
                processed_percent += fid2cnt_process.get(fid, 0) * nl_filter.default_process_percent
                if processed_percent < 1:
                    filtered.append(action)
        return filtered

    def error_actions(self, action2cnt, query_info, nl_filters, f_nrss, c_model):
        action2cnt_feedback = {action: cnt for action, cnt in action2cnt.items() if action[0] == 'u'}
        assert all(action[1] == 0.5 for action in action2cnt_feedback.keys()), f'Currently, only support 0.5 for user feedback opt: {action2cnt_feedback}'
        action2cnt_process = {action: cnt for action, cnt in action2cnt.items() if action[0] != 'u'}

        # Constant estimation time for error. We assume fixed number of thresholds for all predicates.
        nr_total_thresholds = 16  # 100
        nr_thresholds_per_fid = math.ceil(nr_total_thresholds ** (1 / len(nl_filters)))

        fid_to_feedback_cnt = {}
        for action, cnt in action2cnt_feedback.items():
            fid = action[-1]
            fid_to_feedback_cnt[fid] = fid_to_feedback_cnt.get(fid, 0) + cnt

        fid_to_nrs_per_split = {}
        for fid, feedback_cnt in fid_to_feedback_cnt.items():
            nl_filter = nl_filters[fid]
            # Find actions for this filter.
            action2cnt_process_fid = {action: cnt for action, cnt in action2cnt_process.items() if action[-1] == fid}
            # Find the number of splits.
            nr_splits = pow(2, feedback_cnt)
            diff = (nl_filter.upper - nl_filter.lower) / nr_splits
            # Iterate over each threshold.
            nrs_per_split = []
            visited_split_idxs = set()
            for threhsold_idx in range(1, nr_thresholds_per_fid + 1):
                split_idx = math.floor(threhsold_idx * nr_splits / (nr_thresholds_per_fid + 1))
                if split_idx not in visited_split_idxs:
                    visited_split_idxs.add(split_idx)
                    lower = nl_filter.lower + split_idx * diff
                    upper = nl_filter.lower + (split_idx + 1) * diff if split_idx < nr_splits - 1 else nl_filter.upper
                    nrs = nl_filter.nrs_with_temp_bounds(lower, upper)
                    # Process actions for this filter.
                    for action, cnt in action2cnt_process_fid.items():
                        (action_type, process_percent_multiple, *_) = action
                        process_percent = cnt * nl_filter.default_process_percent * process_percent_multiple
                        if action_type == 'i':
                            nrs = nrs.estimate(process_percent)
                        elif action_type == 'o':
                            (_, _, col_idx, min_max, _) = action
                            col = query_info.query.cols[col_idx]
                            ordering = (min_max, col)
                            nrs = nrs.estimate(process_percent, ordering)   
                    nrs_per_split.append(nrs)
            fid_to_nrs_per_split[fid] = nrs_per_split

        # Process filters with no additional feedback actions.
        f_nrss = f_nrss.copy()
        for fid, nrs in enumerate(f_nrss):
            if fid not in fid_to_feedback_cnt:
                # Find actions for this filter.
                action2cnt_process_fid = {action: cnt for action, cnt in action2cnt_process.items() if action[-1] == fid}
                # Process actions for this filter.
                for action, cnt in action2cnt_process_fid.items():
                    (action_type, process_percent_multiple, *_) = action
                    process_percent = cnt * nl_filters[fid].default_process_percent * process_percent_multiple
                    if action_type == 'i':
                        nrs = nrs.estimate(process_percent)
                    elif action_type == 'o':
                        (_, _, col_idx, min_max, _) = action
                        col = query_info.query.cols[col_idx]
                        ordering = (min_max, col)
                        nrs = nrs.estimate(process_percent, ordering)
                f_nrss[fid] = nrs

        errors = []
        generator = range(1) if not fid_to_nrs_per_split else itertools.product(*fid_to_nrs_per_split.values())
        for nrs_per_fid in generator:
            f_nrss_estimated = f_nrss.copy()
            for idx_fid, fid in enumerate(fid_to_nrs_per_split.keys()):
                f_nrss_estimated[fid] = nrs_per_fid[idx_fid]
            cardi_estimated = c_model.eval(f_nrss_estimated)
            temp_error = self.error_agg(cardi_estimated, query_info)  # , ordering)
            errors.append(temp_error)
        return sum(errors) / len(errors)
    
    def runtime_nr_feedbacks(self, action2cnt):
        nr_feedbacks = sum(cnt for action, cnt in action2cnt.items() if action[0] == 'u')
        runtime = sum(cnt * self.fid2runtime[action[-1]] for action, cnt in action2cnt.items() if action[0] == 'i' or action[0] == 'o')
        return runtime, nr_feedbacks
    
    def all_cost_metrics(self, action2cnt, query_info, nl_filters, f_nrss, c_model, constraint):
        runtime, nr_feedbacks = self.runtime_nr_feedbacks(action2cnt)
        error = self.error_actions(action2cnt, query_info, nl_filters, f_nrss, c_model)
        cost = constraint.cost(error, nr_feedbacks, runtime)
        return runtime, nr_feedbacks, error, cost

    def optimize_local_search(self, query_info, nl_filters, max_nr_total, constraint, cur_nr_feedbacks, cur_runtime):
        start_time = time.time()
        c_model = CardinalityModel(query_info, max_nr_total)
        f_nrss = [nl_filter.idxs_tfu().nrs() for nl_filter in nl_filters]
        possible_actions = self.get_all_possible_actions(len(nl_filters), len(query_info.query.cols))
        # Find a sequence, i.e., set of random actions that satisfies the constraint.
        mul_factor = 1.01
        cur_factor = 1
        step_size = int(cur_factor)
        is_first = True
        action2cnt = {}
        while True:
            accumulated_time = time.time() - start_time
            if not is_first:
                cur_factor *= mul_factor
                step_size = int(cur_factor)
            is_first = False
            cur_nr_actions = sum(action2cnt.values())
            if accumulated_time > 20:  # or cur_nr_actions >= 10:
                print(f'TIMEOUT - Building sequence: {accumulated_time} {cur_nr_actions}')
                break
            runtime, nr_feedbacks = self.runtime_nr_feedbacks(action2cnt)
            error = self.error_actions(action2cnt, query_info, nl_filters, f_nrss, c_model)
            print(f'{accumulated_time} {step_size} {cur_nr_actions} {error} {cur_runtime} Building sequence: {[f"{cnt}:{action}~{query_info.query.cols[action[2]]}" if action[0] == "o" else f"{cnt}: {action}" for action, cnt in action2cnt.items()]}')
            if constraint.satisfies(error, nr_feedbacks + cur_nr_feedbacks, runtime + cur_runtime, len(nl_filters)):
                break
            if constraint.metric == TDBMetric.RUNTIME:
                # Means that none of the action is cheap enough in terms of runtime to be processed.
                break
            max_improve = float("-inf")
            best_actions = []
            meaningful_actions = CostOptimizer.meaningful_actions(possible_actions, nl_filters, action2cnt)
            for action in meaningful_actions:
                modified = action2cnt.copy()
                modified[action] = modified.get(action, 0) + step_size  # 1
                runtime, nr_feedbacks, error, cost = self.all_cost_metrics(modified, query_info, nl_filters, f_nrss, c_model, constraint)
                # print(f'{action} {error} {modified}')
                if constraint.metric == TDBMetric.ERROR:
                    # Lower error the better.
                    improve = -error
                elif constraint.metric == TDBMetric.FEEDBACK:
                    # Does not really matter because never should come here.
                    improve = -nr_feedbacks
                elif constraint.metric == TDBMetric.RUNTIME:
                    # Does not really matter because never should come here.
                    improve = -runtime
                
                if improve > max_improve:
                    max_improve = improve
                    best_actions = [action]
                elif improve == max_improve:
                    best_actions.append(action)
            if not best_actions:
                break
            # if len(best_actions) > 1:
            #     print(f'WARNING: multiple best actions {max_improve}: {best_actions} {meaningful_actions}')
            action = best_actions[0] if len(best_actions) == 1 else random.choice(best_actions)
            action2cnt[action] = action2cnt.get(action, 0) + step_size  # 1
        # Local search to optimize the sequence.
        # 1. Swap an action.
        # 2. Delete one action.
        # 3. Add one action.
        cur_factor = 1
        step_size = int(cur_factor)
        is_first = True
        is_timeout = False
        while True:
            accumulated_time = time.time() - start_time
            if not is_first:
                cur_factor *= mul_factor
                step_size = int(cur_factor)
            is_first = False
            cur_nr_actions = sum(action2cnt.values())
            print(f'{accumulated_time} {step_size} {cur_nr_actions} {cur_runtime} Current action sequence: {[f"{cnt}:{action}~{query_info.query.cols[action[2]]}" if action[0] == "o" else f"{cnt}: {action}" for action, cnt in action2cnt.items()]}')
            if time.time() - start_time > 100:
                print(f'TIMEOUT - Local search: {accumulated_time}')
                break
            # if not is_first and cur_nr_actions == 0:
            #     break
            prev_runtime, prev_nr_feedbacks, prev_error, prev_cost = self.all_cost_metrics(action2cnt, query_info, nl_filters, f_nrss, c_model, constraint)
            prev_not_satisfied = not constraint.satisfies(prev_error, prev_nr_feedbacks + cur_nr_feedbacks, prev_runtime + cur_runtime, len(nl_filters))
            print(f'Current estimated cost metrics: {(prev_runtime, prev_nr_feedbacks, prev_error, prev_cost)}')
            if prev_not_satisfied and constraint.metric == TDBMetric.RUNTIME:
                # Means that none of the action is cheap enough in terms of runtime to be processed.
                break
            is_modified = False
            cur_cost = prev_cost
            cur_error = prev_error
            # 1. Swap an action.
            nr_to_swap = min(cur_nr_actions, step_size)
            if nr_to_swap >= 1:
                for modified in CostOptimizer.swap_action(action2cnt, possible_actions, nr_to_swap):
                    if time.time() - start_time > 100:
                        print(f'TIMEOUT - Local search: {time.time() - start_time}')
                        is_timeout = True
                        break
                    runtime, nr_feedbacks, error, cost = self.all_cost_metrics(modified, query_info, nl_filters, f_nrss, c_model, constraint)
                    if prev_not_satisfied or constraint.satisfies(error, nr_feedbacks + cur_nr_feedbacks, runtime + cur_runtime, len(nl_filters)):
                        if cost < cur_cost or (constraint.metric == TDBMetric.ERROR and cost == cur_cost and error < cur_error):
                            cur_cost = cost
                            cur_error = error
                            action2cnt = modified
                            is_modified = True
                            # break
            if is_timeout:
                break
            if is_modified:
                continue
            # 2. Delete an action.
            if cur_nr_actions >= 1:
                nr_to_delete = min(cur_nr_actions, step_size)
                # for modified in CostOptimizer.delete_k_actions(nr_to_delete, action2cnt):
                for modified in CostOptimizer.delete_action(action2cnt, nr_to_delete):
                    if time.time() - start_time > 100:
                        print(f'TIMEOUT - Local search: {time.time() - start_time}')
                        is_timeout = True
                        break
                    runtime, nr_feedbacks, error, cost = self.all_cost_metrics(modified, query_info, nl_filters, f_nrss, c_model, constraint)
                    if prev_not_satisfied or constraint.satisfies(error, nr_feedbacks + cur_nr_feedbacks, runtime + cur_runtime, len(nl_filters)):
                        if cost < cur_cost or (constraint.metric == TDBMetric.ERROR and cost == cur_cost and error < cur_error):
                            cur_cost = cost
                            cur_error = error
                            action2cnt = modified
                            is_modified = True
                            # break
            if is_timeout:
                break
            if is_modified:
                continue
            # 3. Add an action.
            # for modified in CostOptimizer.add_k_actions(cur_factor, action2cnt, possible_actions):
            for modified in CostOptimizer.add_action(action2cnt, possible_actions, step_size):
                if time.time() - start_time > 100:
                    print(f'TIMEOUT - Local search: {time.time() - start_time}')
                    is_timeout = True
                    break
                runtime, nr_feedbacks, error, cost = self.all_cost_metrics(modified, query_info, nl_filters, f_nrss, c_model, constraint)
                # print(f'{cur_runtime} Adding action sequence: {[f"{cnt}:{action}~{query_info.query.cols[action[2]]}" if action[0] == "o" else f"{cnt}: {action}" for action, cnt in modified.items()]}')
                # print(f'Adding - estimated cost metrics: {(runtime, nr_feedbacks, error, cost)}')
                if prev_not_satisfied or constraint.satisfies(error, nr_feedbacks + cur_nr_feedbacks, runtime + cur_runtime, len(nl_filters)):
                    if cost < cur_cost or (constraint.metric == TDBMetric.ERROR and cost == cur_cost and error < cur_error):
                        cur_cost = cost
                        cur_error = error
                        action2cnt = modified
                        is_modified = True
                        # break
            if is_timeout:
                break
            if is_modified:
                continue
            break
        return [action for action, cnt in sorted(action2cnt.items()) for _ in range(cnt)], cur_cost, cur_error

    @staticmethod
    def delete_action(action2cnt, k=1):
        # Delete an action k times. If cnt is less than k, then delete the entire action.
        for key in action2cnt:
            modified = {action: cnt - k if action == key else cnt for action, cnt in action2cnt.items() if
                        not (action == key and cnt <= k)}
            yield modified

    @staticmethod
    def add_action(action2cnt, possible_actions, k=1):
        for key in possible_actions:
            modified = action2cnt.copy()
            modified[key] = modified.get(key, 0) + k
            yield modified

    @staticmethod
    def swap_action(action2cnt, possible_actions, k):
        for key in action2cnt:
            deleted = {action: cnt - k if action == key else cnt for action, cnt in action2cnt.items() if
                        not (action == key and cnt <= k)}
            cnt_changed = action2cnt[key] - deleted.get(key, 0)
            for key2 in possible_actions:
                if key != key2:
                    modified = deleted.copy()
                    modified[key2] = modified.get(key2, 0) + cnt_changed
                    yield modified

    def optimize(self, query_info, nl_filters, max_nr_total, look_ahead, constraint, cur_nr_feedbacks, cur_runtime):
        # Action: user feedback + process more (e.g., uniform)
        # prev_error = 1 if prev_error is None else prev_error
        # Get filter results which contain the counts for each of the true, false, unsure.
        f_nrss = []
        for nl_filter in nl_filters:
            temp_nrs = nl_filter.idxs_tfu().nrs()
            f_nrss.append(temp_nrs)
            print(f'{nl_filter} - # of t, f, u, processed, total, ordering_to_cnt: {temp_nrs.t}, {temp_nrs.f}, {temp_nrs.u}, {temp_nrs.processed}, {temp_nrs.nr_total} {nl_filter.ordering_to_cnt}')

        c_model = CardinalityModel(query_info, max_nr_total)
        cardi = c_model.eval(f_nrss)
        print(f'Selectivity/Probability of t, f, u: {cardi.s_t}, {cardi.s_f}, {cardi.s_u} {cardi.p_t}, {cardi.p_f}, {cardi.p_u}')

        possible_actions = self.get_all_possible_actions(len(nl_filters), len(query_info.query.cols))
        possible_actions = CostOptimizer.meaningful_actions(possible_actions, nl_filters, {})
        assert len(possible_actions) > 0
        action_sets = itertools.combinations_with_replacement(possible_actions, look_ahead)

        prev_error = self.error_actions({}, query_info, nl_filters, f_nrss, c_model)
        print(f'Current estimated error: {prev_error}')
        max_improve = float("-inf")
        best_action_sets = []
        error_per_action = []
        # TODO: Add runtime metric.
        if constraint.metric == TDBMetric.ERROR:
            for actions in action_sets:
                action2cnt = {}
                for action in actions:
                    action2cnt[action] = action2cnt.get(action, 0) + 1

                runtime, nr_feedbacks = self.runtime_nr_feedbacks(action2cnt)
                cost = runtime + nr_feedbacks * self.metric_ratio
                error = self.error_actions(action2cnt, query_info, nl_filters, f_nrss, c_model)
                improve = (prev_error - error) / cost
                error_per_action.append((error, f'Error of {[f"{cnt}: {action}~{query_info.query.cols[action[2]]}" if action[0] == "o" else f"{cnt}: {action}" for action, cnt in action2cnt.items()]}: {error} {cost} {improve}'))
                if improve > max_improve:
                    max_improve = improve
                    best_action_sets = [action2cnt]
                elif improve == max_improve:
                    best_action_sets.append(action2cnt)
        elif constraint.metric == TDBMetric.FEEDBACK:
            feedback_constraint = (len(nl_filters) * constraint.threshold)
            for actions in action_sets:
                action2cnt = {}
                for action in actions:
                    action2cnt[action] = action2cnt.get(action, 0) + 1

                runtime, nr_feedbacks = self.runtime_nr_feedbacks(action2cnt)
                nr_remaining_feedback = feedback_constraint - cur_nr_feedbacks
                if nr_feedbacks > nr_remaining_feedback:
                    continue
                error = self.error_actions(action2cnt, query_info, nl_filters, f_nrss, c_model)
                cost = runtime + (prev_error - error) * self.metric_ratio
                improve = -cost
                error_per_action.append((error, f'Error of {[f"{cnt}: {action}~{query_info.query.cols[action[2]]}" if action[0] == "o" else f"{cnt}: {action}" for action, cnt in action2cnt.items()]}: {error} {cost} {improve}'))
                if improve > max_improve:
                    max_improve = improve
                    best_action_sets = [action2cnt]
                elif improve == max_improve:
                    best_action_sets.append(action2cnt)
        else:
            raise ValueError(f'Unimplemented constraint option {constraint}')

        error_per_action.sort(key=lambda x: x[0])
        for temp_tuple in error_per_action:
            print(temp_tuple[1])

        best_action_set = best_action_sets[0] if len(best_action_sets) == 1 else random.choice(best_action_sets)
        print(f'Max improvement based on constraint: {constraint} {max_improve} {best_action_set} {best_action_sets}')
        return [action for action, cnt in best_action_set.items() for _ in range(cnt)]
