'''
Created on Jul 17, 2025

@author: immanueltrummer
'''
import sqlglot

from dataclasses import dataclass
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope


@dataclass
class UnaryPredicate():
    """ Represents a semantic predicate in a query. """
    table: str
    """ Name of the table to which the predicate applies. """
    alias: str
    """ Table alias within the relevant query scope. """
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
    left_alias: str
    """ Alias of the left table in the join. """
    right_table: str
    """ Name of the right table in the join. """
    right_alias: str
    """ Alias of the right table in the join. """
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
        qualified_exp = qualify(ast, schema=schema)
        scope = Scope(qualified_exp)
        alias2table = self._alias2table(scope)
        semantic_predicates = self._collect_predicates(
            qualified_exp, alias2table)
        
        self.qualified_sql = qualified_exp.sql()
        self.scope = Scope(qualified_exp)
        self.alias2table = alias2table        
        self.semantic_predicates = semantic_predicates
    
    def _alias2table(self, scope):
        """ Maps table aliases to table names.

        Args:
            scope (Scope): Scope containing the tables.
        
        Returns:
            Dictionary mapping table aliases to their names.
        """
        alias2table = {}
        for table in scope.tables:
            alias = table.alias
            alias2table[alias] = table.name
        return alias2table
    
    def _collect_predicates(self, qualified_sql, alias2table):
        """ Collects semantic filters from the query.
        
        Args:
            qualified_sql (exp.Expression): fully qualified SQL query.
            alias2table (dict): Mapping of table aliases to table names.
        
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
                alias = self.alias2table[table]
                condition = expressions[1].this
                sql = expr.sql()
                predicate = UnaryPredicate(
                    table=table, alias=alias, 
                    column=column, condition=condition, 
                    sql=sql)
                predicates.append(predicate)
            elif expr.args.get('this', None) == 'NLjoin':
                expressions = expr.args.get('expressions', [])
                left_column = expressions[0].this.name
                right_column = expressions[1].this.name
                left_alias = expressions[0].args['table'].name
                right_alias = expressions[1].args['table'].name
                left_table = alias2table[left_alias]
                right_table = alias2table[right_alias]
                condition = expressions[2].this
                sql = expr.sql()
                predicate = JoinPredicate(
                    left_table=left_table, left_alias=left_alias, 
                    right_table=right_table, right_alias=right_alias, 
                    left_column=left_column, right_column=right_column, 
                    condition=condition, sql=sql)
                predicates.append(predicate)
        
        return predicates


if __name__ == "__main__":
    from tdb.data.relational import Database
    # db = Database('elephants.db')
    # query = Query(db, "SELECT NLfilter(ImagePath, 'Is it an elephant?') FROM images")
    db = Database('detective3.db')
    # query = Query(db, "SELECT NLfilter(ImagePath, 'Is it an elephant?') FROM images"
    query = Query(db, "select S.FaceImage, M.FaceImage from ShopCams S, ShopCams M, TrafficCams where NLjoin(S.faceimage, M.faceimage, 'The pictures show the same person') and S.CameraLocation = 'Starbucks' and M.CameraLocation = 'McDonalds' and EXISTS (select * from shopcams as SC);")
    print(query.semantic_predicates)