import math

from sqlglot import exp


class TFUCardinality:
    """ Ternary (+ processed) cardinality.

    The semantics of unsure is different from counts of true, false, and unsure.
    That is, here, unsure includes unprocessed while, for counts, unsure only
    refers to processed items."""
    def __init__(self, s_true, s_false, s_unsure, p_true, p_false, p_unsure, nr_total, ordering_to_ratio, is_nl_pred=True):
        self.s_t = s_true
        self.s_f = s_false
        self.s_u = s_unsure
        self.p_t = p_true
        self.p_f = p_false
        self.p_u = p_unsure
        self.nr_total = nr_total
        self.ordering_to_ratio = ordering_to_ratio
        self.is_nl_pred = is_nl_pred

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    @property
    def s_tu(self):
        return self.s_t + self.s_u

    @property
    def s_fu(self):
        return self.s_f + self.s_u

    @property
    def p_tu(self):
        return self.p_t + self.p_u

    @property
    def p_fu(self):
        return self.p_f + self.p_u

    def not_eval(self):
        return TFUCardinality(self.s_f, self.s_t, self.s_u, self.f, self.t, self.u, self.nr_total, self.ordering_to_ratio)

    def composite_ordering_to_ratio(self, other):
        if self.ordering_to_ratio is None:
            return other.ordering_to_ratio
        elif other.ordering_to_ratio is None:
            return self.ordering_to_ratio
        else:
            key_intersection = self.ordering_to_ratio.keys() & other.ordering_to_ratio.keys()
            return {key: min(self.ordering_to_ratio[key], other.ordering_to_ratio[key]) for key in key_intersection}

    def and_correlated(self, other, p_p):
        p_true = (self.s_t * other.s_t) * p_p
        p_false = (self.s_f + other.s_f - self.s_f * other.s_f) * p_p
        p_unsure = (self.s_u * other.s_u + self.s_t * other.s_u + self.s_u * other.s_t) * p_p
        return p_true, p_false, p_unsure

    def and_independent(self, other, p_p):
        p_remaining = 1 - p_p
        p_true = (self.p_t * other.p_t) * p_remaining
        p_false = (self.p_f + other.p_f - self.p_f * other.p_f) * p_remaining
        p_unsure = (self.p_u * other.p_u + self.p_t * other.p_u + self.p_u * other.p_t) * p_remaining
        return p_true, p_false, p_unsure

    def and_eval(self, other):
        ordering_to_ratio = self.composite_ordering_to_ratio(other)
        ratio_sum = sum(ordering_to_ratio.values())
        # Same ordering: so.
        p_true_so, p_false_so, p_unsure_so = self.and_correlated(other, ratio_sum)
        assert math.isclose(sum([p_true_so, p_false_so, p_unsure_so]), ratio_sum), f'{p_true_so}, {p_false_so}, {p_unsure_so}, {sum([p_true_so, p_false_so, p_unsure_so])}, {ratio_sum}'
        # Remaining: r.
        p_true_r, p_false_r, p_unsure_r = self.and_independent(other, ratio_sum)
        assert math.isclose(sum([p_true_r, p_false_r, p_unsure_r]), 1 - ratio_sum), f'{p_true_r}, {p_false_r}, {p_unsure_r}, {sum([p_true_r, p_false_r, p_unsure_r])}, {1 - ratio_sum}'
        # Overall.
        s_true = self.s_t * other.s_t
        s_false = self.s_f + other.s_f - self.s_f * other.s_f
        s_unsure = self.s_tu * other.s_tu - s_true
        assert math.isclose(sum([s_true, s_false, s_unsure]), 1), f'{s_true}, {s_false}, {s_unsure}, {sum([s_true, s_false, s_unsure])}'
        p_true = p_true_so + p_true_r
        p_false = p_false_so + p_false_r
        p_unsure = p_unsure_so + p_unsure_r
        assert math.isclose(sum([p_true, p_false, p_unsure]), 1), f'{p_true,}, {p_false}, {p_unsure}, {sum([p_true, p_false, p_unsure])}'
        return TFUCardinality(s_true, s_false, s_unsure, p_true, p_false, p_unsure, self.nr_total, ordering_to_ratio)

    def or_correlated(self, other, p_p):
        p_false = (self.s_f * other.s_f) * p_p
        p_true = (self.s_t + other.s_t - self.s_t * other.s_t) * p_p
        p_unsure = (self.s_u * other.s_u + self.s_f * other.s_u + self.s_u * other.s_f) * p_p
        return p_true, p_false, p_unsure

    def or_independent(self, other, p_p):
        p_remaining = 1 - p_p
        p_false = (self.p_f * other.p_f) * p_remaining
        p_true = (self.p_t + other.p_t - self.p_t * other.p_t) * p_remaining
        p_unsure = (self.p_u * other.p_u + self.p_f * other.p_u + self.p_u * other.p_f) * p_remaining
        return p_true, p_false, p_unsure

    def or_eval(self, other):
        ordering_to_ratio = self.composite_ordering_to_ratio(other)
        ratio_sum = sum(ordering_to_ratio.values())
        # Same ordering: so.
        p_true_so, p_false_so, p_unsure_so = self.or_correlated(other, ratio_sum)
        assert math.isclose(sum([p_true_so, p_false_so, p_unsure_so]), ratio_sum), f'{p_true_so}, {p_false_so}, {p_unsure_so}, {sum([p_true_so, p_false_so, p_unsure_so])}, {ratio_sum}'
        # Remaining: r.
        p_true_r, p_false_r, p_unsure_r = self.or_independent(other, ratio_sum)
        assert math.isclose(sum([p_true_r, p_false_r, p_unsure_r]), 1 - ratio_sum), f'{p_true_r}, {p_false_r}, {p_unsure_r}, {sum([p_true_r, p_false_r, p_unsure_r])}, {1 - ratio_sum}'
        # Overall.
        s_false = self.s_f * other.s_f
        s_unsure = self.s_fu * other.s_fu - s_false
        s_true = 1 - s_false - s_unsure
        assert math.isclose(sum([s_true, s_false, s_unsure]), 1), f'{s_true}, {s_false}, {s_unsure}, {sum([s_true, s_false, s_unsure])}'
        p_true = p_true_so + p_true_r
        p_false = p_false_so + p_false_r
        p_unsure = p_unsure_so + p_unsure_r
        assert math.isclose(sum([p_true, p_false, p_unsure]), 1), f'{p_true,}, {p_false}, {p_unsure}, {sum([p_true, p_false, p_unsure])}'
        return TFUCardinality(s_true, s_false, s_unsure, p_true, p_false, p_unsure, self.nr_total, ordering_to_ratio)


class CardinalityModel:
    """Cardinality model for ternary (i.e., true, false, unsure) predicate evaluation.

    We need to create a new object for each specific query."""

    def __init__(self, query_info, max_nr_total):
        self.node = query_info.where
        self.query = query_info.query
        self.max_nr_total = max_nr_total
        self.f_nrss = None

    def eval(self, f_nrss):
        self.f_nrss = f_nrss
        return self._eval(self.node)

    @staticmethod
    def _is_nl_pred(node):
        return type(node) is exp.Anonymous and node.this.lower() == 'nl'

    def _get_fid(self, node):
        #nl_filter_sql_str = str(node).lower()
        nl_filter_sql_str = str(node)
        print(self.query.arg_strs)
        fid = self.query.arg_strs.index(nl_filter_sql_str)
        return fid

    def _eval(self, node):
        """Evaluates cardinality for the given predicate node."""
        node_type = type(node)
        if node_type is exp.Paren:
            # Parenthesis.
            return self._eval(node.this)
        elif node_type is exp.Not:
            cardi = self._eval(node.this)
            if not cardi.is_nl_pred:
                return cardi
            else:
                return cardi.not_eval()
        elif node_type is exp.And:
            cardi_left = self._eval(node.left)
            cardi_right = self._eval(node.right)
            if not cardi_left.is_nl_pred:
                return cardi_right
            elif not cardi_right.is_nl_pred:
                return cardi_left
            else:
                return cardi_left.and_eval(cardi_right)
        elif node_type is exp.Or:
            cardi_left = self._eval(node.left)
            cardi_right = self._eval(node.right)
            if not cardi_left.is_nl_pred:
                return cardi_right
            elif not cardi_right.is_nl_pred:
                return cardi_left
            else:
                return cardi_left.or_eval(cardi_right)
        elif node_type is exp.Anonymous:
            # Check keyword for natural language predicate.
            if not CardinalityModel._is_nl_pred(node):
                raise ValueError(f'Unknown user-defined function: {node.this}.')
            # TODO: Better way to refer to NLFilter.
            # Get ternary cardinality.
            fid = self._get_fid(node)
            nrs = self.f_nrss[fid]
            s_true = nrs.t / nrs.processed
            s_false = nrs.f / nrs.processed
            s_unsure = nrs.u / nrs.processed
            p_true = nrs.t / nrs.nr_total
            p_false = nrs.f / nrs.nr_total
            p_unsure = 1 - p_true - p_false
            ordering_to_ratio = {k: v / nrs.nr_total for k, v in nrs.ordering_to_cnt.items()}
            return TFUCardinality(s_true, s_false, s_unsure, p_true, p_false, p_unsure, self.max_nr_total, ordering_to_ratio)
        # TODO: Support more predicate types.
        elif node_type is exp.EQ:
            return TFUCardinality(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, self.max_nr_total, None, is_nl_pred=False)
        elif node_type is exp.LT or node_type is exp.LTE:
            return TFUCardinality(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, self.max_nr_total, None, is_nl_pred=False)
        elif node_type is exp.GT or node_type is exp.GTE:
            return TFUCardinality(1.0, 0.0, 0.0, 1.0, 0.0, 0.0, self.max_nr_total, None, is_nl_pred=False)
        else:
            raise Exception(f'Unsupported predicate type: {node_type}, {node}.')

