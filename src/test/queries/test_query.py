'''
Created on Aug 11, 2025

@author: immanueltrummer
'''
from tdb.queries.query import Query, UnaryPredicate, JoinPredicate
from test.test_util import cars_db


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