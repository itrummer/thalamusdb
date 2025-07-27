'''
Created on Jul 16, 2025

@author: immanueltrummer
'''
import base64

from tdb.execution.counters import TdbCounters
from openai import OpenAI


class SemanticOperator:
    """ Base class for semantic operators. """
    
    def __init__(self, db, operator_ID):
        """
        Initializes the semantic operator with a unique identifier.
        
        The unique operator identifier is used to create a temporary
        table in the database to store the results of the operator.
        
        Args:
            db: Represents the source database.
            operator_ID (str): Unique identifier for the operator.
        """
        self.db = db
        self.operator_ID = operator_ID
        self.counters = TdbCounters()
        self.llm = OpenAI()

    def _encode_item(self, item_text):
        """ Encodes an item as message for LLM processing.
        
        Args:
            item_text (str): Text of the item to encode, can be a path.
        
        Returns:
            dict: Encoded item as a dictionary with 'role' and 'content'.
        """
        image_extensions = ['.png', '.jpg', '.jpeg']
        if any(
            item_text.endswith(extension) \
            for extension in image_extensions):
            with open(item_text, 'rb') as image_file:
                image = base64.b64encode(
                    image_file.read()).decode('utf-8')
                
            return {
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/jpeg;base64,{image}',
                    'detail': 'low'
                    }
                }
        else:
            return {
                'type': 'text',
                'text': item_text
            }
    
    def execute(self, nr_rows, order):
        """ Execute operator on a given number of ordered rows.
        
        Args:
            nr_rows (int): Number of rows to process.
            order (tuple): None or tuple with column name and "ascending" flag.            
        """
        raise NotImplementedError()
    
    def prepare(self):
        """ Prepare for execution by creating the temporary table. """
        raise NotImplementedError()
    
    def update_cost_counters(self, llm_reply):
        """ Update cost-related counters from LLM reply.
        
        Args:
            llm_reply: The reply from the LLM (currently only OpenAI).
        """
        self.counters.LLM_calls += 1
        self.counters.input_tokens += llm_reply.usage.prompt_tokens
        self.counters.output_tokens += llm_reply.usage.completion_tokens