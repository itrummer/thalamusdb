'''
Created on Jul 16, 2025

@author: immanueltrummer
'''
import time

from tdb.execution.nlfilter import NLFilter


class Profiler:
    """ Generates statistics for natural language predicates via profiling. """
    def __init__(self, engine):
        """ Initializes data profiling for a specific database. 
        
        Args:
            engine: an execution engine for the database.
        """
        self.engine = engine
    
    def profile(self, query, counters):
        """ Profile predicates of a given query.
        
        Args:
            query: an SQL-type query containing natural language predicates.
            counters: keeps track of execution costs.
        
        Returns:
            Tuple: list of NLFilter statistics, list of run times.
        """
        nl_filters = [
            NLFilter(self.engine.nldb.get_col_by_name(col), text) \
            for col, text in query.nl_preds]
        preprocess_percents = [
            nl_filter.default_process_percent \
            for nl_filter in nl_filters]
        # Create scores tables.
        print('About to add scores tables.')
        for fid, nl_filter in enumerate(nl_filters):
            print('Adding scores table for NL filter:', nl_filter.text)
            self.engine.execute_sql(f"DROP TABLE IF EXISTS scores{fid}", None)
            self.engine.execute_sql(f"CREATE TABLE scores{fid}(sid INTEGER PRIMARY KEY, score FLOAT, processed BOOLEAN)", None)
            if nl_filter.idx_to_score:
                self.engine.execute_sql(f"INSERT INTO scores{fid} VALUES {', '.join(f'({key}, {val}, TRUE)' for key, val in nl_filter.idx_to_score.items())}", None)
            self.engine.execute_sql(f"""
            INSERT INTO scores{fid} SELECT {nl_filter.col.name}, NULL, FALSE
            FROM (SELECT {nl_filter.col.name}, score FROM {nl_filter.col.table} LEFT JOIN scores{fid} ON {nl_filter.col.table}.{nl_filter.col.name} = scores{fid}.sid) AS temp_scores
            WHERE score IS NULL""", None)
        # Get all possible orderings.
        possible_orderings = [('uniform',)]
        for col_name in query.cols:
            possible_orderings.append(('min', col_name))
            possible_orderings.append(('max', col_name))
        # Preprocess some data.
        fid2runtime = []
        for fid, nl_filter in enumerate(nl_filters):
            start_nl_filter = time.time()
            # To prevent bias towards uniform sampling.
            percent_per_ordering = preprocess_percents[fid] / len(possible_orderings)
            for ordering in possible_orderings:
                action = ('i', 1, fid) if ordering == ('uniform',) else ('o', 1, query.cols.index(ordering[1]), ordering[0], fid)
                self.engine.process_unstructured(action, query, nl_filters, percent_per_ordering, None)
            end_nl_filter = time.time()
            time_nl_filter = end_nl_filter - start_nl_filter
            print(f'Unit process runtime: {time_nl_filter}')
            fid2runtime.append(time_nl_filter)
        
        return nl_filters, fid2runtime