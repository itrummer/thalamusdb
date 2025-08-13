'''
Created on Aug 11, 2025

@author: immanueltrummer
'''
from tdb.queries.query import Query, UnaryPredicate, JoinPredicate
from test.test_util import cars_db


def test_limit():
    """ Tests the parsing of limit clauses (if any). """
    sql = """
    select * from cars C1, cars C2
    where nlfilter(C1.pic, 'is a red car') and
    nlfilter(C2.pic, 'is a blue car') and
    nljoin(C1.pic, C2.pic, 'are similar')
    limit 10;
    """
    query = Query(cars_db, sql)
    assert query.limit == 10
    assert 'limit' not in query.qualified_sql.lower()
    sql = """
    select * from cars C1, cars C2
    where nlfilter(C1.pic, 'is a red car')
    """
    query = Query(cars_db, sql)
    assert query.limit == float('inf')
    assert 'limit' not in query.qualified_sql.lower()
    sql = """
    select * from cars C1, cars C2
    where nlfilter(C1.pic, 'is a red car')
    limit (10 - 1);
    """
    query = Query(cars_db, sql)
    assert query.limit == float('inf')
    assert 'limit' in query.qualified_sql.lower()


def test_parsing():
    """ Tests the parsing of a query. """
    sql = """
    select * from cars C1, cars C2
    where nlfilter(C1.pic, 'is a red car') and
    nlfilter(C2.pic, 'is a blue car') and
    nljoin(C1.pic, C2.pic, 'are similar');
    """
    query = Query(cars_db, sql)
    assert query.alias2table == {'c1': 'cars', 'c2': 'cars'}
    assert len(query.semantic_predicates) == 3
    for sem_pred in query.semantic_predicates:
        if isinstance(sem_pred, UnaryPredicate):
            assert sem_pred.table == 'cars'
            assert sem_pred.alias in ['c1', 'c2']
            assert sem_pred.column == 'pic'
            assert sem_pred.condition in ['is a red car', 'is a blue car']
        elif isinstance(sem_pred, JoinPredicate):
            assert sem_pred.left_alias == 'c1'
            assert sem_pred.right_alias == 'c2'
            assert sem_pred.left_column == 'pic'
            assert sem_pred.right_column == 'pic'
            assert sem_pred.condition == 'are similar'