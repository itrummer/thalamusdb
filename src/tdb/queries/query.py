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
        self.qualitifed_query = qualified_sql.sql()
    
    def _collect_predicates(self, qualified_sql):
        """ Collects semantic filters from the query.
        
        Args:
            qualified_sql (exp.Expression): fully qualified SQL query.
        
        Returns:
            List of UnaryPredicate objects representing the predicates.
        """
        predicates = []
        for expr in qualified_sql.find_all(exp.Anonymous):
            if expr.args.get('this', None) == 'NL':
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
        
        return predicates


if __name__ == "__main__":
    from tdb.data.relational import Database
    db = Database('elephants.db')
    query = Query(db, "SELECT NL(ImagePath, 'Is it an elephant?') FROM images")
    print(query.semantic_predicates)