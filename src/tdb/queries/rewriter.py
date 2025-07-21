'''
Created on Jul 18, 2025

@author: immanueltrummer
'''
from tdb.operators.semantic_filter import UnaryFilter
from tdb.operators.semantic_join import SemanticSimpleJoin


class QueryRewriter():
    """ Class for rewriting queries with semantic operators. """
    
    def __init__(self, db, query):
        """
        Initializes the query rewriter for a specific database and query.
        
        Args:
            db: Database containing the tables to rewrite queries for.
            query (str): SQL query with natural language operators.
        """
        self.db = db
        self.query = query
    
    def filter2sql(self, filter_op, null_as):
        """ Transforms NL predicate into pure SQL.
        
        The SQL predicate refers to the temporary table
        containing results for a subset of rows.
        
        Args:
            filter_op: semantic filter operator.
            null_as: default value to use for un-evaluated rows.
        
        Returns:
            str: SQL predicate for the temporary table.
        """
        true_items_sql = \
            f'select base_{filter_op.filtered_column} ' \
            f'from {filter_op.tmp_table} ' \
            f'where result = true'
        if null_as == True:
            true_items_sql += ' or result is NULL'
        return f'{filter_op.filtered_column} IN ({true_items_sql})'
    
    def join2sql(self, join_op, null_as):
        """ Transforms NL join predicate into pure SQL.
        
        The SQL predicate refers to the temporary table
        containing results for a subset of rows.
        
        Args:
            join_op: semantic join operator.
            null_as: default value to use for un-evaluated rows.
        
        Returns:
            str: SQL predicate for the temporary table.
        """
        join_pred = join_op.pred
        true_items_sql = (
            f'select left_{join_pred.left_column}, '
            f'right_{join_pred.right_column} '
            f'from {join_op.tmp_table} '
            f'where result = true')
        if null_as == True:
            true_items_sql += ' or result is NULL'
        return (
            f' ({join_pred.left_alias}.{join_pred.left_column}, ' 
            f'{join_pred.right_alias}.{join_pred.right_column}) '
            f' IN ({true_items_sql}) ')
    
    def pure_sql(self, op2default):
        """ Transforms the query with semantic operators into pure SQL.
        
        Args:
            op2default: maps semantic operators to default values.
        
        Returns:
            str: Pure SQL query without semantic operators.
        """
        query = self.query.qualified_sql
        for op, default_value in op2default.items():
            if isinstance(op, UnaryFilter):
                filter_sem_sql = op.filter_sql
                filter_pure_sql = self.filter2sql(op, default_value)
                query = query.replace(filter_sem_sql, filter_pure_sql)
            elif isinstance(op, SemanticSimpleJoin):
                join_sem_sql = op.pred.sql
                join_pure_sql = self.join2sql(op, default_value)
                query = query.replace(join_sem_sql, join_pure_sql)
            else:
                raise NotImplementedError('Unsupported operator type!')

        return query