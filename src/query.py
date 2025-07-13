import re

from sqlglot import parse_one, exp


class NLQuery:
    """Query object with support for natural language predicates on unstructured data.

    RL-based optimizer takes this object as input.
    """

    def __init__(self, sql):
        self.sql = sql
        # Finds case-insensitive matches and extract arguments as tuples, e.g., [(col_name, nl_text), ...].
        self.arg_strs = [arg_str[1:] for arg_str in re.findall(r'(?i)[ \(]nl\(.+?, .+?\)', sql)]
        self.nl_preds = [tuple(arg.replace("'", '').replace('"', '').strip() for arg in arg_str[3:-1].split(',')) for
                         arg_str in self.arg_strs]
        # Find all tables and columns.
        self.parsed = parse_one(sql)
        self.cols = sorted(set([col.alias_or_name for col in self.parsed.find_all(exp.Column)]))
        self.tables = sorted(set([table.name for table in self.parsed.find_all(exp.Table)]))
        print(f'Columns: {self.cols}, Tables: {self.tables}')
        # Check if query has limit.
        limit_exps = list(self.parsed.find_all(exp.Limit))
        assert len(limit_exps) <= 1
        self.limit = -1 if len(limit_exps) == 0 else int(limit_exps[0].args['expression'].this)

    def to_lower_upper_sqls(self, nl_filters, thresholds):
        assert len(nl_filters) >= 1
        # Replace nl predicates with predicates on similarity scores.
        sql_l, sql_u = self.sql, self.sql
        join_conditions = []
        for fid, nl_filter in enumerate(nl_filters):
            lower, upper = thresholds[fid]
            predicate_l = f"scores{fid}.score >= {upper}"
            predicate_u = f"(scores{fid}.score IS NULL OR scores{fid}.score > {lower})"
            prev_str = self.arg_strs[fid]
            sql_l = sql_l.replace(prev_str, predicate_l)
            sql_u = sql_u.replace(prev_str, predicate_u)
            join_conditions.append(f"scores{fid}.sid = {nl_filter.col.name}")
        # Add scores tables.
        join_condition = ' AND '.join(join_conditions)
        scores_tables = [f'scores{fid}' for fid in range(len(nl_filters))]
        parsed_l = parse_one(sql_l).from_(*scores_tables).where(join_condition)
        parsed_u = parse_one(sql_u).from_(*scores_tables).where(join_condition)
        # Add sum and count if there is avg.
        avgs = [select for select in self.parsed.selects if type(select) is exp.Avg]
        if len(avgs) > 0:
            for avg in avgs:
                col_name = avg.this.alias_or_name
                parsed_l = parsed_l.select(f'sum({col_name})').select(f'count({col_name})')
                parsed_u = parsed_u.select(f'sum({col_name})').select(f'count({col_name})')
        sql_l = parsed_l.sql()
        sql_u = parsed_u.sql()
        return sql_l, sql_u, len(avgs)

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


class NLQueryInfo:
    """Query information for cost-based optimization.

    Currently, supports star schema. Assumes that the query has only one select.
    """

    def __init__(self, query, nldb):
        self.query = query
        # Find relevant query components.
        assert sum(1 for _ in query.parsed.find_all(exp.Select)) == 1, 'Subquery not yet supported.'
        assert type(query.parsed) is exp.Select, f'Query should start with SELECT: {type(query.parsed)}.'
        # Collect aggregates.
        # Limit info is already in self.query.
        assert len(query.parsed.selects) == 1
        agg = query.parsed.selects[0]
        if agg.alias_or_name == '*':
            self.agg_func = None
            self.agg_col = '*'
        else:
            self.agg_func = agg.key
            self.agg_col = agg.this.alias_or_name
        # Collect predicates.
        wheres = list(query.parsed.find_all(exp.Where))
        assert len(wheres) <= 1
        self.where = None if len(wheres) == 0 else wheres[0].this
        # Add columns for foreign key relationships.
        self.cols_count = nldb.get_count_columns_for_foreign_key(query)
        for col in self.cols_count:
            if col not in query.cols:
                self.query.cols.append(col)
        print(f'Columns (Added Count Column): {self.query.cols}')

    def __str__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


if __name__ == "__main__":
    sql = "select * from images, furniture where images.aid = furniture.aid and nl(img, 'blue chair') and nl(title_u, 'good condition') limit 10"
    query = NLQuery(sql)




