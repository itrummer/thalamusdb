'''
Created on Jul 22, 2025

@author: immanueltrummer
'''
import numpy as np
import pandas as pd

from tdb.ui.util import df2set, print_df


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
    
    def result(self):
        """ Aggregate all possible results into one likely result.
        
        Returns:
            One result representing our best guess.
        """
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
            results: List of possible query results (pandas data frames).
        
        Returns:
            Tuple of lower and upper bounds for the results.
        """
        assert len(results) > 0, 'No results to aggregate!'
        # Aggregate list of data frames into lower and upper bounds.
        lower_bounds = results[0].copy()
        upper_bounds = results[0].copy()
        for result in results[1:]:
            # Update lower and upper bounds from data frame
            lower_bounds = np.minimum(lower_bounds, result)
            upper_bounds = np.maximum(upper_bounds, result)
        
        return lower_bounds, upper_bounds
    
    def error(self):
        """ Computes the error metric for the aggregate results.
        
        Returns:
            A numerical error value (zero for exact results).
        """
        return (
            self.upper_bounds - self.lower_bounds).sum(
                axis=1).values[0]
    
    def output(self):
        """ Outputs lower and upper bounds on query result. """
        print_df(self.lower_bounds, 'Lower Bounds')
        print_df(self.upper_bounds,'Upper Bounds')
    
    def result(self):
        """ Take the average between lower and upper bounds.
        
        Returns:
            A list with our best guess value for each query aggregate.
        """
        return (self.lower_bounds + self.upper_bounds) / 2


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
        assert len(results) > 0, 'No results to intersect!'
        columns = results[0].columns
        common_results = df2set(results[0])
        for result in results[1:]:
            next_result = df2set(result)
            common_results = common_results.intersection(
                next_result)
        
        return pd.DataFrame(common_results, columns=columns)
    
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
        max_rows = max(len(df2set(result)) for result in self.results)
        intersection_rows = len(self.intersection)
        if max_rows == intersection_rows:
            return 0.0
        if intersection_rows == 0:
            return float('inf')
        # print('Results:')
        # for result in self.results:
        #     print(result)
        error = (max_rows - intersection_rows) / intersection_rows - 1
        return error
    
    def output(self):
        """ Outputs the intersection of all retrieval results. """
        print_df(
            self.intersection, 
            'Rows that Appear in Each Possible Result')
        print(f'Total #certain rows: {len(self.intersection)}')
    
    def result(self):
        """ Use the intersection as our best guess result.
        
        Returns:
            Rows that appear in all possible results.
        """
        return self.intersection