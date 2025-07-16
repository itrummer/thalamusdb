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
    execution_time: int = 0
    """ Total execution time in seconds. """