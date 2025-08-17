'''
Created on Jul 16, 2025

@author: immanueltrummer

Contains counters measuring execution costs.
'''
import pandas as pd

from dataclasses import dataclass, field
from tdb.ui.util import print_df, print_progress


@dataclass
class LLMCounters():
    """ Contains counters associated with one specific LLM. """
    LLM_calls: int = 0
    """ Number of LLM calls made during the execution. """
    input_tokens: int = 0
    """ Number of input tokens in the LLM calls. """
    text_input_tokens: int = 0
    """ Number of text input tokens in the LLM calls. """
    image_input_tokens: int = 0
    """ Number of image input tokens in the LLM calls. """
    audio_input_tokens: int = 0
    """ Number of audio input tokens in the LLM calls. """
    output_tokens: int = 0
    """ Number of output tokens in the LLM calls. """
    
    def __add__(self, other):
        """ Adds values for each counter.
        
        Args:
            other: another LLMCounters instance to add.
        
        Returns:
            A new LLMCounters instance with summed values.
        """
        assert isinstance(other, LLMCounters), \
            'Can only add LLMCounters instances!'
        return LLMCounters(
            LLM_calls=self.LLM_calls + other.LLM_calls,
            input_tokens=self.input_tokens + other.input_tokens,
            text_input_tokens=self.text_input_tokens + other.text_input_tokens,
            image_input_tokens=self.image_input_tokens + other.image_input_tokens,
            audio_input_tokens=self.audio_input_tokens + other.audio_input_tokens,
            output_tokens=self.output_tokens + other.output_tokens
        )
    
    def pretty_print(self, title='LLM Counters'):
        """ Prints LLM counters for updates during query execution.
        
        Args:
            title: Title for printed table.
        """
        counter_df = pd.DataFrame({
            'LLM Calls': [self.LLM_calls],
            'Input Tokens': [self.input_tokens],
            'Text Input Tokens': [self.text_input_tokens],
            'Image Input Tokens': [self.image_input_tokens],
            'Audio Input Tokens': [self.audio_input_tokens],
            'Output Tokens': [self.output_tokens],
            })
        print_df(counter_df, title=title)


@dataclass
class TdbCounters:
    """ Contains counters measuring execution costs and progress. """
    processed_tasks: int = 0
    """ Number of processed tasks requiring LLM invocations. """
    unprocessed_tasks: int = 0
    """ Number of unprocessed tasks that require LLM invocations. """
    model2counters: dict = field(default_factory=dict)
    """ Maps LLM model IDs to their respective counters. """
    
    def total_input_tokens(self):
        """ Returns total number of input tokens processed.
        
        Returns:
            Total number of input tokens across all models.
        """
        return sum(
            counters.input_tokens for counters \
            in self.model2counters.values())

    def total_LLM_calls(self):
        """ Returns total number of LLM calls made during execution.
        
        Returns:
            Total number of LLM calls across all models.
        """
        return sum(
            counters.LLM_calls for counters \
            in self.model2counters.values())
    
    def total_output_tokens(self):
        """ Returns total number of output tokens processed.
        
        Returns:
            Total number of output tokens across all models.
        """
        return sum(
            counters.output_tokens for counters \
            in self.model2counters.values())
    
    def __add__(self, other):
        """ Adds values for each counter.
        
        Args:
            other: another TdbCounters instance to add.
        
        Returns:
            A new TdbCounters instance with summed values.
        """
        assert isinstance(other, TdbCounters), \
            'Can only add TdbCounters instances!'
        processed_tasks=self.processed_tasks + other.processed_tasks
        unprocessed_tasks=self.unprocessed_tasks + other.unprocessed_tasks
        model2counters = self.model2counters.copy()
        for model_id, counters in other.model2counters.items():
            if model_id in model2counters:
                model2counters[model_id] += counters
            else:
                model2counters[model_id] = counters
        
        return TdbCounters(
            processed_tasks=processed_tasks,
            unprocessed_tasks=unprocessed_tasks,
            model2counters=model2counters
        )
    
    def pretty_print(self):
        """ Prints counters for updates during query execution. """
        print_progress(self.processed_tasks, self.unprocessed_tasks)
        for model_id, counters in self.model2counters.items():
            title = f'LLM Counters for {model_id}'
            counters.pretty_print(title=title)