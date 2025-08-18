'''
Created on Aug 6, 2025

@author: immanueltrummer
'''
from litellm.types.utils import ModelResponse, Choices, Message
from tdb.data.relational import Database
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent
cars_db_path = Path(root_dir, 'data', 'cars', 'cars.db')
model_config_path = Path(root_dir, 'config', 'models.json')
cars_db = Database(database_name=str(cars_db_path))


def create_response(content):
    """ Creates a mock response object for LLM calls.
    
    Args:
        content: Content of the response message.
    
    Returns:
        ModelResponse object with the specified content.
    """
    message = Message(content=content)
    choices = Choices(message=message)
    response = ModelResponse(
        choices=[choices],
        usage={
            'prompt_tokens': 10,
            'completion_tokens': 7,
            'total_tokens': 3
        }
    )
    return response


def mock_evaluate_predicate_False(item_text, kwargs):
    """ Mocks predicate evaluation and always returns False.
    
    Args:
        item_text: Item in text representation.
        kwargs: kwyword arguments for LLM call.
    
    Returns:
        Tuple: (item_text, response indicating not satisfied).
    """
    response = create_response('0')
    return item_text, response


def mock_evaluate_predicate_True(item_text, kwargs):
    """ Mocks predicate evaluation and always returns True.
    
    Args:
        item_text: Item in text representation.
        kwargs: Keyword arguments for LLM call.
    
    Returns:
        Tuple: (item_text, True).
    """
    response = create_response('1')
    return item_text, response


def set_mock_filter(mocker, default_value):
    """ Mocks the NLfilter function to return a default value.
    
    Args:
        mocker: Mocker fixture for creating mock objects.
        default_value: The value to return when the filter is applied.
    """
    mock_eval = lambda self, item_texts: \
        [(i, default_value) for i in item_texts]
    target = 'tdb.operators.semantic_filter.UnaryFilter._evaluate_predicate_parallel'
    mocker.patch(target, mock_eval)