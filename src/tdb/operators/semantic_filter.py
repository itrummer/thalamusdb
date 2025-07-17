'''
Created on Jul 16, 2025

@author: immanueltrummer
'''
import base64

from tdb.operators.semantic_operator import SemanticOperator


class UnaryFilter(SemanticOperator):
    """ Base class for unary filters specified in natural language. """
    
    def __init__(
            self, db, operator_ID, 
            filtered_table, filtered_column, 
            filter_condition):
        """
        Initializes the unary filter.
        
        Args:
            db: Database containing the filtered table.
            operator_ID (str): Unique identifier for the operator.
            filtered_table (str): Name of the table to filter.
            filtered_column (str): Name of the column to filter.
            filter_condition (str): filter condition in natural language.
        """
        super().__init__(db, operator_ID)
        self.filtered_table = filtered_table
        self.filtered_column = filtered_column
        self.filter_condition = filter_condition
        self.tmp_table = f'ThalamusDB_{self.operator_ID}'
    
    def _encode_item(self, item_text):
        """ Encodes an item as message for LLM processing.
        
        Args:
            item_text (str): Text of the item to encode, can be a path.
        
        Returns:
            dict: Encoded item as a dictionary with 'role' and 'content'.
        """
        if item_text.endswith('.jpeg'):
            with open(item_text, 'rb') as image_file:
                image = base64.b64encode(
                    image_file.read()).decode('utf-8')
                
            return {
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/jpeg;base64,{image}',
                    'detail': 'low'
                    }
                }
        else:
            return {
                'type': 'text',
                'text': item_text
            }
    
    def _evaluate_predicate(self, item_text):
        """ Evaluates the filter condition using the LLM.
        
        Args:
            item_text (str): Text of the item to evaluate.
        
        Returns:
            True iff the item satisfies the filter condition.
        """
        item = self._encode_item(item_text)
        question = (
            'Does the following item satisfy the condition '
            f'"{self.filter_condition}"?')
        message = {
            'role': 'user',
            'content': [
                {
                    'type': 'text',
                    'text': question
                },
                item
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
        return result == 1
    
    def _retrieve_items(self, nr_rows, order):
        """ Retrieve items to process next from the filtered table.
        
        This method is used to retrieve items from the filtered table
        based on the specified number of rows and order.
        
        Args:
            nr_rows (int): Number of rows to retrieve.
            order (tuple): None or tuple (column, ascending flag).
        """
        # Retrieve items from the filtered table
        order_sql = '' if order is None \
            else f'ORDER BY {order[0]} {"ASC" if order[1] else "DESC"}'
        sql = (
            f'SELECT * FROM {self.filtered_table} '
            f'{order_sql} LIMIT {nr_rows}')
        rows = self.db.execute(sql)
        return [row[0] for row in rows]
    
    def prepare(self):
        """ Prepare for execution by creating intermediate result table.
        
        The temporary table contains the columns of the filtered table,
        as well as columns storing the result of filter evaluations (via
        LLMs) and a result used for simulating optimizer choices.
        """
        base_columns = self.db.columns(self.filtered_table)
        temp_schema_parts = ['result BOOLEAN', 'simulated BOOLEAN']
        for col_name, col_type in base_columns:
            tmp_col_name = f'base_{col_name}'
            temp_schema_parts.append(f'{tmp_col_name} {col_type}')
        
        temp_schema_definition = \
            f'CREATE TEMPORARY TABLE {self.tmp_table}(' +\
            ', '.join(temp_schema_parts) + ')'
        temp_src_data = \
            'SELECT NULL, NULL, ' +\
            ', '.join(c[0] for c in base_columns) +\
            'FROM ' + self.filtered_table
        temp_sql = f'{temp_schema_definition} AS {temp_src_data}'
        self.db.execute(temp_sql)
    
    def execute(self, nr_rows, order):
        """ Execute operator on a given number of ordered rows.
        
        Args:
            nr_rows (int): Number of rows to process.
            order (tuple): None or tuple (column, ascending flag).           
        """
        # Retrieve nr_rows in sort order from temporary table
        items_to_process = self._retrieve_items(nr_rows, order)
        # Process each row with LLM
        for item_text in items_to_process:
            result = self._evaluate_predicate(item_text)
            # Update temporary table with results
            update_sql = (
                f'UPDATE {self.tmp_table} '
                f'SET result = {result}, '
                f'simulated = {result} '
                f'WHERE base_{self.filtered_column} = {item_text}')
            self.db.execute(update_sql)
    
    def pure_sql(self, null_as):
        """ Transforms NL predicate into pure SQL.
        
        The SQL predicate refers to the temporary table
        containing results for a subset of rows.
        
        Args:
            null_as (str): default value to use for un-evaluated rows.
        
        Returns:
            str: SQL predicate for the temporary table.
        """
        true_items_sql = \
            f'select base_{self.filtered_column} ' \
            f'from {self.tmp_table} ' \
            f'where result = true'
        if null_as == True:
            true_items_sql += ' or results is NULL'
        return f'{self.filtered_column} IN ({true_items_sql})'