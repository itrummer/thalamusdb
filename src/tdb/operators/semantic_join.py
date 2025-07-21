'''
Created on Jul 20, 2025

@author: immanueltrummer
'''
from tdb.operators.semantic_operator import SemanticOperator


class SemanticSimpleJoin(SemanticOperator):
    """ Represents a semantic join operator in a query. 
    
    This is a simple implementation of the semantic join,
    invoking the LLM for each pair of rows to check
    (i.e., a nested loops join).
    """
    
    def __init__(self, db, operator_ID, join_predicate):
        """
        Initializes the semantic join operator.
        
        Args:
            db: Database containing the joined tables.
            operator_ID (str): Unique identifier for the operator.
            join_predicate: Join predicate expressed in natural language.
        """
        super().__init__(db, operator_ID)
        self.pred = join_predicate
        self.tmp_table = f'ThalamusDB_{self.operator_ID}'
    
    def _get_join_candidates(self, nr_pairs, order):
        """ Retrieves a given number of ordered row pairs in given order.
        
        Args:
            nr_pairs (int): Number of row pairs to retrieve.
            order (str): None or tuple (table, column, ascending flag).
        
        Returns:
            list: List of unprocessed row pairs from the left and right tables.
        """
        left_key_col = f'left_{self.pred.left_column}'
        right_key_col = f'right_{self.pred.right_column}'
        retrieval_sql = (
            f'SELECT {left_key_col}, {right_key_col} '
            f'FROM {self.tmp_table} '
            f'WHERE result IS NULL '
            f'LIMIT {nr_pairs}')
        pairs = self.db.execute(retrieval_sql)
        return pairs
        
    def _find_matches(self, pairs):
        """ Finds pairs satisfying the join condition.
        
        Args:
            pairs: List of key pairs to check for matches.
        
        Returns:
            list: List of key pairs that satisfy the join condition.
        """
        matches = []
        for left_key, right_key in pairs:
            left_item = self._encode_item(left_key)
            right_item = self._encode_item(right_key)
            question = (
                'Do the following items satisfy the join condition '
                f'"{self.pred.condition}"? '
                'Answer with 1 for yes, 0 for no.')
            message = {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': question},
                    left_item,
                    right_item
                ]
            }
            response = self.llm.chat.completions.create(
                model='gpt-4o',
                messages=[message],
                max_tokens=1,
                logit_bias={15: 100, 16: 100},
                temperature=0.0
            )
            self.update_counters(response)
            result = int(response.choices[0].message.content)
            if result == 1:
                matches.append((left_key, right_key))
        return matches
    
    def execute(self, nr_pairs, order):
        """ Executes the join on a given number of ordered rows.
        
        Args:
            nr_pairs (int): Number of row pairs to process.
            order (str): None or tuple (table, column, ascending flag).
        """
        # Retrieve candidate pairs and set the result to NULL
        pairs = self._get_join_candidates(nr_pairs, order)
        for left_key, right_key in pairs:
            update_sql = (
                f'UPDATE {self.tmp_table} '
                f'SET result = False, simulated = False '
                f"WHERE left_{self.pred.left_column} = '{left_key}' "
                f"AND right_{self.pred.right_column} = '{right_key}';")
            self.db.execute(update_sql)
        
        # Find matching pairs of keys
        matches = self._find_matches(pairs)
        
        # Update the temporary table with the results
        for left_key, right_key in matches:
            update_sql = (
                f'UPDATE {self.tmp_table} '
                f'SET result = TRUE, simulated = TRUE '
                f"WHERE left_{self.pred.left_column} = '{left_key}' "
                f"AND right_{self.pred.right_column} = '{right_key}';")
            self.db.execute(update_sql)
    
    def prepare(self):
        """ Prepare for execution by creating a temporary table. """
        left_columns = self.db.columns(self.pred.left_table)
        right_columns = self.db.columns(self.pred.right_table)
        temp_schema_parts = ['result BOOLEAN', 'simulated BOOLEAN']
        for col_name, col_type in left_columns:
            tmp_col_name = f'left_{col_name}'
            temp_schema_parts.append(f'{tmp_col_name} {col_type}')
        for col_name, col_type in right_columns:
            tmp_col_name = f'right_{col_name}'
            temp_schema_parts.append(f'{tmp_col_name} {col_type}')
        
        create_table_sql = \
            f'CREATE TEMPORARY TABLE {self.tmp_table} (' +\
            ', '.join(temp_schema_parts) + ');'
        self.db.execute(create_table_sql)
        
        left_select_items = [
            f'L.{col[0]} AS left_{col[0]}' \
            for col in left_columns]
        right_select_items = [
            f'R.{col[0]} AS right_{col[0]}' \
            for col in right_columns]
        fill_table_sql = (
            f'INSERT INTO {self.tmp_table} '
            f'SELECT NULL AS result, NULL AS simulated, '
            + ', '.join(left_select_items) + ', '
            + ', '.join(right_select_items) + ' '
            f'FROM {self.pred.left_table} L, {self.pred.right_table} R '
        )
        self.db.execute(fill_table_sql)