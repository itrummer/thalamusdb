'''
Created on Jul 16, 2025

@author: immanueltrummer

Contains counters measuring execution costs.
'''
from dataclasses import dataclass


@dataclass
class TdbCounters:
    """ Contains counters measuring execution costs. """
    LLM_calls: int = 0
    """ Number of LLM calls made during the execution. """
    input_tokens: int = 0
    """ Number of input tokens in the LLM calls. """
    output_tokens: int = 0
    """ Number of output tokens in the LLM calls. """
    
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
            output_tokens=self.output_tokens + other_counter.output_tokens
        )