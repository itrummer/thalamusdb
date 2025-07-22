'''
Created on Jul 22, 2025

@author: immanueltrummer
'''
class PossibleResults():
    """ Contains a set of possible query results.
    
    As long as semantic operators are only evaluated
    on a subset of the data, multiple query results
    are possible.
    """
    def __init__(self, results):
        """
        Initializes the possible results with a list of results.
        
        Args:
            results (list): List of possible query results.
        """
        self.results = results
    
    def error(self):
        """
        Computes the error metric for the possible results.
        
        Returns:
            A numerical error value (zero for exact results).
        """
        raise NotImplementedError(
            'Use sub-classes for specific types of results!')
    
    def output(self):
        """ Output aggregate information about possible results. """
        raise NotImplementedError(
            'Use sub-classes for specific types of results!')


class AggregateResults(PossibleResults):
    """ Summarizes possible results for an aggregation query.
    
    In this context, an aggregation query is defined as a
    query that produces one single result row in all cases.
    Also, each field in each result must be numerical.
    """
    def __init__(self, results):
        """
        Initializes the aggregate results with a list of results.
        
        Args:
            results (list): List of aggregate results.
        """
        super().__init__(results)
        self.lower_bounds, self.upper_bounds = \
            self._results2bounds(results)
    
    def _results2bounds(self, results):
        """ Aggregate query results into lower and upper bounds.
        
        Args:
            results: List of possible query results.
        
        Returns:
            Tuple of lower and upper bounds for the results.
        """
        assert len(results) > 0, 'No results to aggregate!'
        # Calculate lower and upper bounds for each aggregate
        nr_aggregates = len(results[0])
        lower_bounds = [float('inf')] * nr_aggregates
        upper_bounds = [float('-inf')] * nr_aggregates
        for result in results:
            # print(f'Result: {result}')
            first_row = result[0]
            for i, value in enumerate(first_row):
                if value < lower_bounds[i]:
                    lower_bounds[i] = value
                if value > upper_bounds[i]:
                    upper_bounds[i] = value
        
        return lower_bounds, upper_bounds
    
    def error(self):
        """ Computes the error metric for the aggregate results.
        
        Returns:
            A numerical error value (zero for exact results).
        """
        lb_ub_zip = list(zip(self.lower_bounds, self.upper_bounds))
        assert all(lb <= ub for lb, ub in lb_ub_zip), \
            'Lower bounds must be less than or equal to upper bounds!'
        # Compute error as the sum of absolute differences
        error = sum(abs(lb - ub) for lb, ub in lb_ub_zip)
        return error
    
    def output(self):
        """ Outputs lower and upper bounds on query result. """
        print('Lower Bounds:', self.lower_bounds)
        print('Upper Bounds:', self.upper_bounds)


class RetrievalResults(PossibleResults):
    """ Summarizes all possible results of a retrieval query.
    
    In this context, a retrieval query is defined as a any query
    that does not qualify as an aggregation query. I.e., the
    query may produce multiple result rows or some of the result
    fields are not of numerical type.
    """
    def __init__(self, results):
        """
        Initializes the retrieval results with a list of results.
        
        Args:
            results (list): List of retrieval results.
        """
        super().__init__(results)
        self.intersection = self._intersect_results(results)
    
    def _intersect_results(self, results):
        """ Computes the intersection of all retrieval results.
        
        Args:
            results: List of possible query results.
        
        Returns:
            Set of common results across all retrieval results.
        """
        if not results:
            return set()
        common_results = set(results[0])
        for result in results[1:]:
            common_results.intersection_update(result)
        return common_results
    
    def error(self):
        """ Computes the error metric for the retrieval results.
        
        For retrieval query, the error is defined as the relative
        difference between the number of rows in the largest result
        and the number of rows in the intersection of all results.
        
        Returns:
            An error quantifying the quality of approximation.
        """
        if not self.results:
            return 0.0
        max_rows = max(len(result) for result in self.results)
        intersection_rows = len(self.intersection)
        if max_rows == 0:
            return 0.0
        error = (max_rows - intersection_rows) / max_rows
        return error
    
    def output(self):
        """ Outputs the intersection of all retrieval results. """
        print('Intersection of Results:')
        for result in self.intersection:
            print(result)
        print(f'Total #certain rows: {len(self.intersection)}')