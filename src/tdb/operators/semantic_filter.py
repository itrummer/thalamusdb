'''
Created on Jul 16, 2025

@author: immanueltrummer
'''
from tdb.operators.semantic_operator import SemanticOperator


class UnaryFilter(SemanticOperator):
    """ Base class for unary filters specified in natural language. """
    
    def __init__(self, db, operator_ID, batch_size, query, predicate):
        """
        Initializes the unary filter.
        
        Args:
            db: Database containing the filtered table.
            operator_ID (str): Unique identifier for the operator.
            batch_size (int): Number of items to process per call.
            query: Query containing the predicate.
            predicate: predicate expressed in natural language.
        """
        super().__init__(db, operator_ID, batch_size)
        self.query = query
        self.filtered_table = predicate.table
        self.filtered_alias = predicate.alias
        self.filtered_column = predicate.column
        self.filter_condition = predicate.condition
        self.filter_sql = predicate.sql
        self.tmp_table = f'ThalamusDB_{self.operator_ID}'
    
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
            f'"{self.filter_condition}"? '
            'Answer with 1 for yes, 0 for no.')
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
        messages = [message]
        model = self._select_model(messages)
        # print(messages)
        # print(model)
        response = self.llm.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1,
            logit_bias={15: 100, 16: 100},
            temperature=0.0
        )
        self.update_cost_counters(response)
        result = str(response.choices[0].message.content)
        # print(f'LLM response: {result}')
        return result == '1'
    
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
            f'SELECT base_{self.filtered_column} FROM {self.tmp_table} '
            'WHERE result IS NULL '
            f'{order_sql} LIMIT {nr_rows}')
        rows = self.db.execute2list(sql)
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
        
        create_table_sql = \
            f'CREATE OR REPLACE TEMPORARY TABLE {self.tmp_table}(' +\
            ', '.join(temp_schema_parts) + ')'
        self.db.execute2list(create_table_sql)
        
        # Use pure SQL predicates for pruning, if available
        other_filters = self.query.alias2unary_sql[self.filtered_alias]
        where_sql = (
            f'WHERE {other_filters.sql()} ' 
            f'AND {self.filtered_column} IS NOT NULL')
        fill_table_sql = \
            f'INSERT INTO {self.tmp_table} ' +\
            'SELECT NULL, NULL, ' +\
            ', '.join(c[0] for c in base_columns) + ' ' +\
            'FROM ' + self.filtered_table + ' ' +\
            where_sql
        self.db.execute2list(fill_table_sql)
        
        # Initialize count of unprocessed tasks
        count_sql = f'SELECT COUNT(*) FROM {self.tmp_table}'
        count_result = self.db.execute2list(count_sql)
        self.counters.unprocessed_tasks = count_result[0][0]
    
    def execute(self, order):
        """ Execute operator on a given number of ordered rows.
        
        Args:
            order (tuple): None or tuple (column, ascending flag).
        """
        # Retrieve nr_rows in sort order from temporary table
        items_to_process = self._retrieve_items(
            self.batch_size, order)
        # Process each row with LLM
        for item_text in items_to_process:
            result = self._evaluate_predicate(item_text)
            # Update temporary table with results
            escaped_item_text = item_text.replace("'", "''")
            update_sql = (
                f'UPDATE {self.tmp_table} '
                f'SET result = {result}, '
                f'simulated = {result} '
                f"WHERE base_{self.filtered_column} = '{escaped_item_text}'")
            self.db.execute2list(update_sql)
        
        # Update task counters
        self.counters.processed_tasks += len(items_to_process)
        self.counters.unprocessed_tasks -= len(items_to_process)