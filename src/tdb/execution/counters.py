'''
Created on Jul 16, 2025

@author: immanueltrummer

Contains counters measuring execution costs.
'''
import pandas as pd

from dataclasses import dataclass
from tdb.ui.util import print_df


@dataclass
class TdbCounters:
    """ Contains counters measuring execution costs and progress. """
    LLM_calls: int = 0
    """ Number of LLM calls made during the execution. """
    input_tokens: int = 0
    """ Number of input tokens in the LLM calls. """
    output_tokens: int = 0
    """ Number of output tokens in the LLM calls. """
    processed_tasks: int = 0
    """ Number of processed tasks requiring LLM invocations. """
    unprocessed_tasks: int = 0
    """ Number of unprocessed tasks that require LLM invocations. """
    
    def __add__(self, other_counter):
        """ Adds values for each counter.
        
        Args:
            other_counter: another TdbCounters instance to add.
        
        Returns:
            A new TdbCounters instance with summed values.
        """
        assert isinstance(other_counter, TdbCounters), \
            'Can only add TdbCounters instances!'
        return TdbCounters(
            LLM_calls=self.LLM_calls + other_counter.LLM_calls,
            input_tokens=self.input_tokens + other_counter.input_tokens,
            output_tokens=self.output_tokens + other_counter.output_tokens,
            processed_tasks=self.processed_tasks + other_counter.processed_tasks,
            unprocessed_tasks=self.unprocessed_tasks + other_counter.unprocessed_tasks
        )
    
    def pretty_print(self):
        """ Prints counters for updates during query execution. """
        counter_df = pd.DataFrame({
            'LLM Calls': [self.LLM_calls],
            'Input Tokens': [self.input_tokens],
            'Output Tokens': [self.output_tokens],
            'Processed Tasks': [self.processed_tasks],
            'Unprocessed Tasks': [self.unprocessed_tasks]
            })
        print_df(counter_df, title='Execution Counters')