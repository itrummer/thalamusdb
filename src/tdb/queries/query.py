'''
Created on Jul 17, 2025

@author: immanueltrummer
'''
import sqlglot

from dataclasses import dataclass
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify


@dataclass
class UnaryPredicate():
    """ Represents a semantic predicate in a query. """
    table: str
    """ Name of the table to which the predicate applies. """
    column: str
    """ Name of the column to which the predicate applies. """
    condition: str
    """ Natural language condition for the predicate. """
    sql: str
    """ SQL representation of the predicate. """


@dataclass
class JoinPredicate():
    """ Represents a semantic join predicate in a query. """
    left_table: str
    """ Name of the left table in the join. """
    right_table: str
    """ Name of the right table in the join. """
    left_column: str
    """ Name of the column in the left table to which the predicate applies. """
    right_column: str
    """ Name of the column in the right table to which the predicate applies. """
    condition: str
    """ Natural language condition for the join predicate. """
    sql: str
    """ SQL representation of the join predicate. """


class Query():
    """ Represents an SQL query with semantic operators. """
    
    def __init__(self, db, sql):
        """ Preprocessing for given SQL query.
        
        Args:
            db: represents the underlying database.
            sql (str): SQL query with operators described in text.
        """
        schema = db.schema()
        ast = sqlglot.parse_one(sql)
        qualified_sql = qualify(ast, schema=schema)
        self.semantic_predicates = self._collect_predicates(qualified_sql)
        self.qualified_sql = qualified_sql.sql()
    
    def _collect_predicates(self, qualified_sql):
        """ Collects semantic filters from the query.
        
        Args:
            qualified_sql (exp.Expression): fully qualified SQL query.
        
        Returns:
            List of natural language predicates.
        """
        predicates = []
        for expr in qualified_sql.find_all(exp.Anonymous):
            if expr.args.get('this', None) == 'NLfilter':
                expressions = expr.args.get('expressions', [])
                qualified_column = expressions[0]
                column = qualified_column.args['this'].name
                table = qualified_column.args['table'].name
                condition = expressions[1].this
                sql = expr.sql()
                predicate = UnaryPredicate(
                    table, column, 
                    condition, sql)
                predicates.append(predicate)
            elif expr.args.get('this', None) == 'NLjoin':
                expressions = expr.args.get('expressions', [])
                left_column = expressions[0].this.name
                right_column = expressions[1].this.name
                left_table = expressions[0].args['table'].name
                right_table = expressions[1].args['table'].name
                condition = expressions[2].this
                sql = expr.sql()
                predicate = JoinPredicate(
                    left_table, right_table, 
                    left_column, right_column, 
                    condition, sql)
                predicates.append(predicate)
        
        return predicates


if __name__ == "__main__":
    from tdb.data.relational import Database
    db = Database('elephants.db')
    query = Query(db, "SELECT NLfilter(ImagePath, 'Is it an elephant?') FROM images")
    print(query.semantic_predicates)