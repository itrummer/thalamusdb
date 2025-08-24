'''
Created on Jul 16, 2025

@author: immanueltrummer

@rewrite: Jiale Lao
Rewritten to use multi-threading (ThreadPoolExecutor) instead of multi-processing.
'''
import litellm
from concurrent.futures import ThreadPoolExecutor

from litellm import completion
from tdb.operators.semantic_operator import SemanticOperator


def _filter_completion_wrapper(item_text, kwargs):
    """Invoke completion function with given keyword arguments.

    Args:
        item_text (str): Text representation of the item.
        kwargs (dict): Keyword arguments for the completion function.

    Returns:
        tuple: (item_text, kwargs, LLM response).
    """
    # Ensure parameters are dropped for logging where applicable
    litellm.drop_params = True
    response = completion(**kwargs)
    return item_text, kwargs, response


class UnaryFilter(SemanticOperator):
    """Base class for unary filters specified in natural language."""

    def __init__(
            self, db, operator_ID, batch_size,
            config_path, query, predicate):
        """
        Initializes the unary filter.

        Args:
            db: Database containing the filtered table.
            operator_ID (str): Unique identifier for the operator.
            batch_size (int): Number of items to process per call.
            config_path (str): Path to the configuration file for models.
            query: Query containing the predicate.
            predicate: predicate expressed in natural language.
        """
        super().__init__(db, operator_ID, batch_size, config_path)
        self.query = query
        self.filtered_table = predicate.table
        self.filtered_alias = predicate.alias
        self.filtered_column = predicate.column
        self.filter_condition = predicate.condition
        self.filter_sql = predicate.sql
        self.tmp_table = f'ThalamusDB_{self.operator_ID}'

    def _evaluate_predicate_parallel(self, item_texts):
        """Evaluates the filter conditions using the LLM concurrently (threads).

        Args:
            item_texts: List of items to evaluate.

        Returns:
            List of tuples (item_text, result) where result is True or False.
        """
        # Prepare keyword inputs for completion function
        inputs = []
        for item_text in item_texts:
            messages = [self._message(item_text)]
            base = self._best_model_args(messages)['filter']
            kwargs = {**base, 'messages': messages}
            inputs.append((item_text, kwargs))

        # Use a thread pool to evaluate predicates concurrently
        # Threads are appropriate here since LLM calls are I/O-bound.
        with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
            futures = [executor.submit(_filter_completion_wrapper, it, kw)
                       for (it, kw) in inputs]
            inputs_outputs = [f.result() for f in futures]

        # Update cost counters
        for _, kwargs, response in inputs_outputs:
            model = kwargs['model']
            self.update_cost_counters(model, response)

        # Extract evaluation results
        results = []
        for item_text, _, response in inputs_outputs:
            result = str(response.choices[0].message.content)
            results.append((item_text, result == '1'))

        return results

    def _gpt_filter_bias(self, model):
        """Add logit bias on output tokens for GPT models.

        Args:
            model (str): Name of the model to use.

        Returns:
            dict: Logit bias to encourage 0/1 outputs for GPT models.
        """
        if self._gpt4_style_model(model):
            return {15: 100, 16: 100}
        else:
            return {}

    def _message(self, item_text):
        """Create a message for the LLM describing the evaluation task.

        Args:
            item_text (str): Text representation of the item.

        Returns:
            dict: Message for the LLM.
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
        return message

    def _retrieve_items(self, nr_rows, order):
        """Retrieve items to process next from the filtered table.

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
        """Prepare for execution by creating intermediate result table.

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
            f'CREATE OR REPLACE TEMPORARY TABLE {self.tmp_table}(' + \
            ', '.join(temp_schema_parts) + ')'
        self.db.execute2list(create_table_sql)

        # Use pure SQL predicates for pruning, if available
        other_filters = self.query.alias2unary_sql[self.filtered_alias]
        where_sql = (
            f'WHERE {other_filters.sql()} '
            f'AND {self.filtered_column} IS NOT NULL')
        fill_table_sql = \
            f'INSERT INTO {self.tmp_table} ' + \
            'SELECT NULL, NULL, ' + \
            ', '.join(c[0] for c in base_columns) + ' ' + \
            'FROM ' + self.filtered_table + ' ' + \
            where_sql
        self.db.execute2list(fill_table_sql)

        # Initialize count of unprocessed tasks
        count_sql = f'SELECT COUNT(*) FROM {self.tmp_table}'
        count_result = self.db.execute2list(count_sql)
        self.counters.unprocessed_tasks = count_result[0][0]

    def execute(self, order):
        """Execute operator on a given number of ordered rows.

        Args:
            order (tuple): None or tuple (column, ascending flag).
        """
        # Retrieve nr_rows in sort order from temporary table
        items_to_process = self._retrieve_items(self.batch_size, order)
        # Evaluate predicates on different items concurrently (threads)
        results = self._evaluate_predicate_parallel(items_to_process)
        # Update results in the temporary table
        for item_text, result in results:
            # Escape single quotes in item text for SQL
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
