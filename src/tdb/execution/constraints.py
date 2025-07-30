'''
Created on Jul 23, 2025

@author: immanueltrummer
'''
from dataclasses import dataclass


@dataclass
class Constraints():
    """ Represents constraints on query execution costs. """
    max_seconds: int = 600
    """ Maximum execution time in seconds. """
    max_calls: int = 1000
    """ Maximum number of LLM calls. """
    max_tokens: int = 1000000
    """ Maximum number of LLM tokens processed. """
    max_error: float = 0
    """ Maximum error allowed in the results. """
    
    def update(self, command):
        """ Updates the constraints based on a command.
        
        Args:
            command: Command containing new constraints.
        """
        if 'max_seconds' in command:
            self.max_seconds = int(command.split('=')[1])
            print(f'Updated max_seconds to {self.max_seconds}')
        if 'max_calls' in command:
            self.max_calls = int(command.split('=')[1])
            print(f'Updated max_calls to {self.max_calls}')
        if 'max_tokens' in command:
            self.max_tokens = int(command.split('=')[1])
            print(f'Updated max_tokens to {self.max_tokens}')
        if 'max_error' in command:
            self.max_error = float(command.split('=')[1])
            print(f'Updated max_error to {self.max_error}')
    
    def terminate(self, counters, seconds, error):
        """ Checks if the execution should be terminated based on constraints.
        
        Args:
            counters: Current execution cost counters.
            seconds: Elapsed time in seconds.
            error: Current error in the results.
        
        Returns:
            True if execution should be terminated, False otherwise.
        """
        if counters.LLM_calls > self.max_calls:
            print('Execution terminated due to max LLM calls exceeded.')
            return True
        
        total_tokens = counters.input_tokens + counters.output_tokens
        if total_tokens > self.max_tokens:
            print('Execution terminated due to max tokens exceeded.')
            return True
        
        if seconds > self.max_seconds:
            print('Execution terminated due to max seconds exceeded.')
            return True
        
        if error < self.max_error:
            print('Execution terminated due to acceptable error level.')
            return True

        return False