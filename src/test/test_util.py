'''
Created on Aug 6, 2025

@author: immanueltrummer
'''
from tdb.data.relational import Database
from pathlib import Path

root_dir = Path(__file__).parent.parent.parent
cars_db_path = Path(root_dir, 'data', 'cars', 'cars.db')
cars_db = Database(database_name=str(cars_db_path))


def mock_evaluate_predicate_False(self, item):
    """ Mocks predicate evaluation and always returns False.
    
    Args:
        item: The item to evaluate.
    
    Returns:
        bool: Always returns False.
    """
    return False


def mock_evaluate_predicate_True(self, item):
    """ Mocks predicate evaluation and always returns True.
    
    Args:
        item: The item to evaluate.
    
    Returns:
        bool: Always returns True.
    """
    return True


def set_mock_filter(mocker, default_value):
    """ Mocks the NLfilter function to return a default value.
    
    Args:
        mocker: Mocker fixture for creating mock objects.
        default_value: The value to return when the filter is applied.
    """
    mocker.patch(
        'tdb.operators.semantic_filter.UnaryFilter._evaluate_predicate',
        lambda self, _: default_value
    )