'''
Created on Jul 16, 2025

@author: immanueltrummer
'''
from tdb.operators.semantic_filter import UnaryFilter
from tdb.operators.semantic_join import BatchJoin
from tdb.queries.query import JoinPredicate, UnaryPredicate
from tdb.queries.rewriter import QueryRewriter


class ExecutionEngine:
    """ Execution engine for processing SQL queries with NL predicates. """

    def __init__(self, db):
        """ Initializes the execution engine with a database and connection.
        
        Args:
            db: Relational database instance.
        """
        self.db = db
    
    def _aggregate_results(self, results):
        """ Aggregate results obtained via different default values.
        
        Args:
            results: List of results obtained from different default values.
        
        Returns:
            Tuple of lower and upper bounds for the results.
        """
        assert len(results) > 0, 'No results to aggregate!'
        # Calculate lower and upper bounds for each aggregate
        nr_aggregates = len(results[0])
        lower_bounds = [float('inf')] * nr_aggregates
        upper_bounds = [float('-inf')] * nr_aggregates
        for result in results:
            print(f'Result: {result}')
            first_row = result[0]
            for i, value in enumerate(first_row):
                if value < lower_bounds[i]:
                    lower_bounds[i] = value
                if value > upper_bounds[i]:
                    upper_bounds[i] = value
        
        return lower_bounds, upper_bounds
    
    def _result_bounds(self, query, semantic_filters):
        """ Computes lower and upper bounds for the query result.
        
        Args:
            query: Represents a query with semantic operators.
            semantic_filters: List of semantic filters.
        
        Returns:
            Tuple of lower and upper bounds.
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
        
        return self._aggregate_results(results)
    
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
        result = self.db.execute(rewritten_query)
        return result
    
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
                    self.db, operator_id, query, predicate)
                semantic_operators.append(semantic_filter)
            
            elif isinstance(predicate, JoinPredicate):
                # Create a semantic join operator
                operator_id = f'Join{predicate_id}'
                semantic_join = BatchJoin(
                    self.db, operator_id, query, predicate)
                semantic_operators.append(semantic_join)
            else:
                raise ValueError(
                    f'Unknown predicate type: {type(predicate)}')

        return semantic_operators

    def _bounds2error(self, bounds):
        """ Measures error for current bounds.
        
        Args:
            bounds: Tuple of lower and upper bounds for the query result.
        
        Returns:
            Error metric (numerical value).
        """
        assert all(lb <= ub for lb, ub in zip(bounds[0], bounds[1])), \
            'Lower bounds must be less than or equal to upper bounds!'
        # Compute error as the sum of absolute differences
        error = sum(abs(lb - ub) for lb, ub in zip(bounds[0], bounds[1]))
        return error

    def run(self, query, constraint):
        """ Run an SQL query with natural language components.
        
        Args:
            query: Represents a query with semantic operators.
            constraint: defines termination conditions.
        
        Returns:
            dict: Information about the execution, including error and LUs.
        """
        semantic_operators = self._create_operators(query)
        for operator in semantic_operators:
            operator.prepare()
        
        # Continue processing until error is sufficiently low
        error = float('inf')
        while error > 0.1:
            # Process more rows for each operator
            for op in semantic_operators:
                op.execute(10, None)
            
            bounds = self._result_bounds(query, semantic_operators)
            print(bounds)
            error = self._bounds2error(bounds)