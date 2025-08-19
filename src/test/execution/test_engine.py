'''
Created on Aug 6, 2025

@author: immanueltrummer

End-to-end tests for the query execution engine.
'''
from tdb.execution.engine import ExecutionEngine
from tdb.execution.constraints import Constraints
from tdb.queries.query import Query
from test.test_util import set_mock_filter
from test.test_util import cars_db, model_config_path


def test_retrieval(mocker):
    """ Tests query execution engine for retrieval queries.
    
    Args:
        mocker: mocker fixture for creating mock objects.
    """
    query_str = "SELECT * FROM cars WHERE NLfilter(pic, 'a car');"
    query = Query(cars_db, query_str)
    
    # Should return all tuples if predicate evaluates to True
    set_mock_filter(mocker, True)
    constraints = Constraints()
    engine = ExecutionEngine(cars_db, 1, model_config_path)
    result, counters = engine.run(query, constraints)
    assert len(result) == 5
    assert counters.processed_tasks == 5
    assert counters.unprocessed_tasks == 0
    
    # Should return no tuples if predicate evaluates to False
    set_mock_filter(mocker, False)
    result, counters = engine.run(query, constraints)
    assert len(result) == 0
    assert counters.processed_tasks == 5
    assert counters.unprocessed_tasks == 0


def test_limit(mocker):
    """ Test retrieval queries with LIMIT clauses.
    
    Args:
        mocker: mocker fixture for creating mock objects.
    """
    query_str = "SELECT * FROM cars WHERE NLfilter(pic, 'a car') LIMIT 2;"
    query = Query(cars_db, query_str)

    # Should return at least two tuples
    set_mock_filter(mocker, True)
    constraints = Constraints()
    engine = ExecutionEngine(cars_db, 1, model_config_path)
    result, _ = engine.run(query, constraints)
    assert len(result) >= 2
    
    # Should return no tuples if predicate evaluates to False
    set_mock_filter(mocker, False)
    result, _ = engine.run(query, constraints)
    assert len(result) == 0


def test_aggregation(mocker):
    """ Tests query execution engine for aggregation queries.
    
    Args:
        mocker: mocker fixture for creating mock objects.
    """
    query_str = "SELECT COUNT(*) FROM cars WHERE NLfilter(pic, 'a car');"
    query = Query(cars_db, query_str)
    
    # Should return count of all tuples if predicate evaluates to True
    set_mock_filter(mocker, True)
    constraints = Constraints()
    engine = ExecutionEngine(cars_db, 1, model_config_path)
    result, counters = engine.run(query, constraints)
    assert result.iloc[0, 0] == 5
    assert counters.processed_tasks == 5
    assert counters.unprocessed_tasks == 0
    
    # Should return count of no tuples if predicate evaluates to False
    set_mock_filter(mocker, False)
    result, counters = engine.run(query, constraints)
    assert result.iloc[0, 0] == 0
    assert counters.processed_tasks == 5
    assert counters.unprocessed_tasks == 0