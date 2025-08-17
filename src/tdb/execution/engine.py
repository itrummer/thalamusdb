'''
Created on Jul 16, 2025

@author: immanueltrummer
'''
import time

from pandas.api.types import is_numeric_dtype
from rich.console import Console
from rich.rule import Rule
from tdb.execution.results import AggregateResults, RetrievalResults
from tdb.operators.semantic_filter import UnaryFilter
from tdb.operators.semantic_join import BatchJoin
from tdb.queries.query import JoinPredicate, UnaryPredicate
from tdb.queries.rewriter import QueryRewriter
from tdb.execution.counters import TdbCounters


class ExecutionEngine:
    """ Execution engine for processing SQL queries with NL predicates. """

    def __init__(self, db, dop):
        """ Initializes the execution engine with a database and connection.
        
        Args:
            db: Relational database instance.
            dop: Degree of parallelism for query execution.
        """
        self.db = db
        self.dop = dop
    
    def _aggregate_counters(self, semantic_operators):
        """ Aggregate counters from all semantic operators.
        
        Args:
            semantic_operators: List of semantic operators used in the query.
        
        Returns:
            Counters representing the sum of all operator counters.
        """
        sum_counters = TdbCounters()
        for op in semantic_operators:
            op_counters = op.counters
            sum_counters += op_counters

        return sum_counters
    
    def _create_operators(self, query):
        """ Create semantic operators needed to execute query.
        
        Args:
            query: Represents a query with semantic operators.
        
        Returns:
            List of semantic operators.
        """
        semantic_operators = []
        for predicate_id, predicate in enumerate(
            query.semantic_predicates):
            if isinstance(predicate, UnaryPredicate):
                # Create a unary filter operator
                operator_id = f'UnaryFilter{predicate_id}'
                semantic_filter = UnaryFilter(
                    self.db, operator_id, self.dop, query, predicate)
                semantic_operators.append(semantic_filter)
            
            elif isinstance(predicate, JoinPredicate):
                # Create a semantic join operator
                operator_id = f'Join{predicate_id}'
                semantic_join = BatchJoin(
                    self.db, operator_id, 10, query, predicate)
                semantic_operators.append(semantic_join)
            else:
                raise ValueError(
                    f'Unknown predicate type: {type(predicate)}')

        return semantic_operators
    
    def _is_agg_results(self, results):
        """ Checks if results are consistent with aggregation query.
        
        Specifically, the method checks if all results contain
        one single row and if each cell in each result is of
        numerical type.
        
        Args:
            results: List of query results.
        
        Returns:
            bool: True if results are consistent with aggregation query.
        """
        # Check if all results have one row
        if any(len(result) != 1 for result in results):
            return False
        
        # Check if all cells in the results are numerical
        for result in results:
            all_numerical = result.apply(
                lambda x: is_numeric_dtype(x)).all()
            if not all_numerical:
                return False
        
        return True
    
    def _results(self, query, semantic_filters):
        """ Computes multiple possible query results.
        
        This method tries all combinations of default values for
        semantic filters and computes the corresponding results.
        
        Args:
            query: Represents a query with semantic operators.
            semantic_filters: List of semantic filters.
        
        Returns:
            List of possible results, obtained with different default values.
        """
        # Try all combinations of default values
        results = []
        nr_operators = len(semantic_filters)
        for i in range(2 ** nr_operators):
            # Get default value for each semantic filter
            default_vals = [(i >> j) & 1 for j in range(nr_operators)]
            # Compute result with default values
            result = self._result_with_defaults(
                query, semantic_filters, default_vals)
            # Add result to set of results
            results.append(result)
        
        return results
    
    def _result_with_defaults(self, query, semantic_filters, default_values):
        """ Computes result with default values for semantic filters.
        
        Args:
            query: Represents a query with semantic operators.
            semantic_filters: List of semantic filters.
            default_values: List of default values for each filter.
        
        Returns:
            Query results when using default values for unevaluated rows.
        """
        rewriter = QueryRewriter(self.db, query)
        op2default = {}
        for op, default_val in zip(semantic_filters, default_values):
            op2default[op] = default_val
        
        rewritten_query = rewriter.pure_sql(op2default)
        result = self.db.execute2df(rewritten_query)
        return result

    def run(self, query, constraints):
        """ Run an SQL query with natural language components.
        
        Args:
            query: Represents a query with semantic operators.
            constraints: defines termination conditions.
        
        Returns:
            Tuple query result and cost counters.
        """
        start_s = time.time()
        console = Console()
        
        semantic_operators = self._create_operators(query)
        for operator in semantic_operators:
            operator.prepare()
        
        error = float('inf')
        while error > 0:
            # Process more rows for each operator
            for op in semantic_operators:
                op.execute(None)
            
            results = self._results(query, semantic_operators)
            
            if self._is_agg_results(results):
                aggregate_results = AggregateResults(results)
            else:
                aggregate_results = RetrievalResults(results)
                nr_certain_rows = len(aggregate_results.intersection)
                if nr_certain_rows >= query.limit:
                    console.print(
                        Rule('Query Limit Reached'),
                        style='bold red')
                    break
            
            console.print(Rule('Query Progress Updates'))
            aggregate_results.output()
            error = aggregate_results.error()
            print(f'Error: {error}')
            
            total_s = time.time() - start_s
            counter_sum = self._aggregate_counters(semantic_operators)
            counter_sum.pretty_print()
            if constraints.terminate(
                counter_sum, total_s, error):
                break
        
        # Depending on the termination condition, we may
        # have processed only a subset of the data. In that
        # case, we return a query result that seems likely.
        best_guess_result = aggregate_results.result()
        counters = self._aggregate_counters(semantic_operators)
        return best_guess_result, counters