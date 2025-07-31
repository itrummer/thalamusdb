'''
Created on Jul 17, 2025

@author: immanueltrummer

Note that the query parsing logic is currently simple.
In particular, it assumes that table aliases are unique
across different sub-queries.
'''
import sqlglot

from dataclasses import dataclass
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify
from sqlglot.optimizer.scope import Scope, traverse_scope


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
        alias2table = self._alias2table(qualified_exp)
        scope = Scope(qualified_exp)
        semantic_predicates = \
            self._collect_semantic_predicates(
            qualified_exp, alias2table)
        
        self.qualified_exp = qualified_exp
        self.qualified_sql = qualified_exp.sql()
        self.scope = scope
        self.alias2table = alias2table
        aliases = alias2table.keys()
        self.alias2unary_sql = self._collect_unary_sql_predicates(
            qualified_exp, aliases)
        self.semantic_predicates = semantic_predicates
    
    def _alias2table(self, qualified_exp):
        """ Maps table aliases to table names.

        Args:
            qualified_exp (exp.Expression): Fully qualified SQL expression.
        
        Returns:
            Dictionary mapping table aliases to their names.
        """
        alias2table = {}
        for scope in traverse_scope(qualified_exp):            
            for table in scope.tables:
                alias = table.alias
                table_name = table.name
                if not alias:
                    alias = table_name
                
                alias2table[alias] = table_name
        
        return alias2table

    def _collect_conjuncts_rec(self, conjunction_ast):
        """ Recursively collects conjuncts from the AST.
        
        Args:
            conjunction_ast: SQL expression to analyze.
        
        Returns:
            List of conjuncts as expressions.
        """
        conjuncts = []
        if isinstance(conjunction_ast, exp.And):
            left_input = conjunction_ast.this
            right_input = conjunction_ast.expression
            conjuncts.extend(self._collect_conjuncts_rec(left_input))
            conjuncts.extend(self._collect_conjuncts_rec(right_input))
        else:
            conjuncts.append(conjunction_ast)
        
        return conjuncts

    def _collect_semantic_predicates(self, qualified_sql, alias2table):
        """ Collects semantic filters from the query.
        
        Args:
            qualified_sql (exp.Expression): fully qualified SQL query.
            alias2table (dict): Mapping of table aliases to table names.
        
        Returns:
            List of natural language predicates.
        """
        predicates = []
        for expr in qualified_sql.find_all(exp.Anonymous):
            if expr.args.get('this', None).lower() == 'nlfilter':
                expressions = expr.args.get('expressions', [])
                qualified_column = expressions[0]
                column = qualified_column.args['this'].name
                table = qualified_column.args['table'].name
                alias = alias2table[table]
                condition = expressions[1].this
                sql = expr.sql()
                predicate = UnaryPredicate(
                    table=table, alias=alias, 
                    column=column, condition=condition, 
                    sql=sql)
                predicates.append(predicate)
            elif expr.args.get('this', None).lower() == 'nljoin':
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
    
    def _collect_unary_sql_predicates(self, qualified_sql, aliases):
        """ Collects unary predicates (pure SQL) from the query.
        
        Args:
            qualified_sql (exp.Expression): fully qualified SQL query.
            aliases: List of table aliases in root query scope.
        
        Returns:
            Dictionary mapping table aliases to unary SQL predicates.
        """
        alias2preds = {
            alias : exp.Boolean(this=True) \
            for alias in aliases
            }
        # Collect all queries to analyze (including sub-queries)
        queries2analyze = [qualified_sql]
        scope = Scope(qualified_sql)
        queries2analyze.extend(scope.subqueries)
        # Iterate over queries and analyze SELECT clauses
        for query in queries2analyze:
            where_clause = query.args.get('where')
            if where_clause is not None:
                where_content = where_clause.this
                conjuncts = self._collect_conjuncts_rec(
                    where_content)
                for conjunct in conjuncts:
                    alias = self._get_unary_alias(conjunct)
                    if alias is not None and alias in aliases:
                        prior_pred = alias2preds[alias]
                        new_pred = exp.And(
                            this=prior_pred, 
                            expression=conjunct)
                        alias2preds[alias] = new_pred
        
        return alias2preds
    
    def _get_unary_alias(self, expression):
        """ Return associated alias if this is a unary predicate.
        
        Args:
            expression (exp.Expression): SQL expression to check.
        
        Returns:
            Table alias or None.
        """
        if isinstance(expression, exp.Binary):
            left_input = expression.this
            right_input = expression.expression
            if isinstance(left_input, exp.Column) and \
                  isinstance(right_input, exp.Literal):
                return left_input.table
            elif isinstance(left_input, exp.Literal) and \
                  isinstance(right_input, exp.Column):
                return right_input.table
            elif isinstance(left_input, exp.Column) and \
                isinstance(right_input, exp.Column):
                left_table = left_input.table
                right_table = right_input.table
                if (left_table == right_table):
                    return left_table
                
        elif isinstance(expression, exp.Unary):
            referenced_cols = expression.find_all(exp.Column)
            if len(referenced_cols) == 1:
                referenced_col = referenced_cols[0]
                alias = referenced_col.table
                return alias
        
        return None

if __name__ == "__main__":
    from tdb.data.relational import Database
    # db = Database('elephants.db')
    # query = Query(db, "SELECT NLfilter(ImagePath, 'Is it an elephant?') FROM images")
    db = Database('detective3.db')
    # query = Query(db, "SELECT NLfilter(ImagePath, 'Is it an elephant?') FROM images"
    #query = Query(db, "select S.FaceImage, M.FaceImage from ShopCams S, ShopCams M, TrafficCams where NLjoin(S.faceimage, M.faceimage, 'The pictures show the same person') and S.CameraLocation = 'Starbucks' and M.CameraLocation = 'McDonalds' and EXISTS (select * from shopcams as SC) and S.CameraLocation = 'test' and S.CameraLocation = S.FaceImage;")
    query = Query(db, "select D.ownername from DMV D, Evidence E where D.carmodel = E.cardescription and exists (select * from ShopCams S where S.cameralocation = 'Starbucks' and S.person = D.ownername) and exists (select * from ShopCams S where S.cameralocation = 'McDonalds' and S.person = D.ownername) and exists (select * from ShopCams S where S.cameralocation = 'Deli' and S.person = D.ownername);")
    print(query.qualified_sql)
    from sqlglot.optimizer.eliminate_subqueries import eliminate_subqueries
    eliminate_subqueries(query.qualified_exp)
    print(query.semantic_predicates)
    print(query.alias2unary_sql)