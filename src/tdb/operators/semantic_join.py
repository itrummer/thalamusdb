'''
Created on Jul 20, 2025

@author: immanueltrummer
'''
import traceback

from litellm import completion
from tdb.operators.semantic_operator import SemanticOperator


class SemanticJoin(SemanticOperator):
    """ Represents a semantic join operator in a query. """
    
    def __init__(
            self, db, operator_ID, batch_size, 
            query, join_predicate):
        """
        Initializes the semantic join operator.
        
        Args:
            db: Database containing the joined tables.
            operator_ID (str): Unique identifier for the operator.
            batch_size (int): Number of items to process per call.
            query: Query containing the join predicate.
            join_predicate: Join predicate expressed in natural language.
        """
        super().__init__(db, operator_ID, batch_size)
        self.query = query
        self.pred = join_predicate
        self.tmp_table = f'ThalamusDB_{self.operator_ID}'
    
    def _get_join_candidates(self, order):
        """ Retrieves a given number of ordered row pairs in given order.
        
        Args:
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
            f'LIMIT {self.batch_size}')
        pairs = self.db.execute2list(retrieval_sql)
        return pairs

    def _filter_join_inputs(self):
        """ Use pure SQL predicates to filter join inputs.
        
        This method creates two temporary tables, containing
        the left and right join inputs after applying all
        unary predicates expressed in pure SQL.
        """
        left_alias = self.pred.left_alias
        left_table = self.pred.left_table
        left_column = self.pred.left_column
        right_alias = self.pred.right_alias
        right_table = self.pred.right_table
        right_column = self.pred.right_column
        for alias, table, col, side in [
            (left_alias, left_table, left_column, 'Left'),
            (right_alias, right_table, right_column, 'Right')]:
            pure_SQL_filters = self.query.alias2unary_sql[alias]
            filter_sql = (
                'CREATE OR REPLACE TEMPORARY TABLE '
                f'ThalamusDB_{side}JoinInputFiltered AS '
                f'SELECT * FROM {table} AS {alias} '
                f'WHERE {pure_SQL_filters.sql()} AND {col} IS NOT NULL;')
            self.db.execute2list(filter_sql)
        
    def _find_matches(self, pairs):
        """ Finds pairs satisfying the join condition.
        
        Args:
            pairs: List of key pairs to check for matches.
        
        Returns:
            list: List of key pairs that satisfy the join condition.
        """
        raise NotImplementedError(
            'Instantiate one of the sub-classes of SemanticJoin!')
    
    def execute(self, order):
        """ Executes the join on a given number of ordered rows.
        
        Args:
            order (str): None or tuple (table, column, ascending flag).
        """
        # Retrieve candidate pairs and set the result to NULL
        pairs = self._get_join_candidates(order)
        for left_key, right_key in pairs:
            escaped_left_key = left_key.replace("'", "''")
            escaped_right_key = right_key.replace("'", "''")
            update_sql = (
                f'UPDATE {self.tmp_table} '
                f'SET result = False, simulated = False '
                f"WHERE left_{self.pred.left_column} = '{escaped_left_key}' "
                f"AND right_{self.pred.right_column} = '{escaped_right_key}' "
                f'AND result IS NULL;')
            self.db.execute2list(update_sql)
        
        # Find matching pairs of keys
        matches = self._find_matches(pairs)
        
        # Update the temporary table with the results
        for left_key, right_key in matches:
            escaped_left_key = left_key.replace("'", "''")
            escaped_right_key = right_key.replace("'", "''")
            update_sql = (
                f'UPDATE {self.tmp_table} '
                f'SET result = TRUE, simulated = TRUE '
                f"WHERE left_{self.pred.left_column} = '{escaped_left_key}' "
                f"AND right_{self.pred.right_column} = '{escaped_right_key}';")
            self.db.execute2list(update_sql)
        
        # Count number of processed tasks
        count_processed_sql = (
            f'SELECT COUNT(*) FROM {self.tmp_table} '
            f'WHERE result IS NOT NULL;')
        count_processed = self.db.execute2list(count_processed_sql)
        self.counters.processed_tasks = count_processed[0][0]
        
        # Count number of unprocessed tasks
        count_unprocessed_sql = (
            f'SELECT COUNT(*) FROM {self.tmp_table} '
            f'WHERE result IS NULL;')
        count_unprocessed = self.db.execute2list(count_unprocessed_sql)
        self.counters.unprocessed_tasks = count_unprocessed[0][0]
    
    def prepare(self):
        """ Prepare for execution by creating a temporary table. """
        # Apply pure SQL filters to the left and right tables
        self._filter_join_inputs()
        
        left_columns = self.db.columns(self.pred.left_table)
        right_columns = self.db.columns(self.pred.right_table)
        temp_schema_parts = [
            'result BOOLEAN', 'simulated BOOLEAN',
            'batch_ID_left INT', 'batch_ID_right INT']
        for col_name, col_type in left_columns:
            tmp_col_name = f'left_{col_name}'
            temp_schema_parts.append(f'{tmp_col_name} {col_type}')
        for col_name, col_type in right_columns:
            tmp_col_name = f'right_{col_name}'
            temp_schema_parts.append(f'{tmp_col_name} {col_type}')
        
        create_table_sql = \
            f'CREATE OR REPLACE TEMPORARY TABLE {self.tmp_table} (' +\
            ', '.join(temp_schema_parts) + ');'
        self.db.execute2list(create_table_sql)

        left_alias = self.pred.left_alias
        right_alias = self.pred.right_alias
        left_filtered_table = 'ThalamusDB_LeftJoinInputFiltered'
        right_filtered_table = 'ThalamusDB_RightJoinInputFiltered'
        left_batch_ID_exp = (
            f'floor({left_alias}.rowid / ' 
            f'{self.batch_size})::INTEGER')
        right_batch_ID_exp = (
            f'floor({right_alias}.rowid / ' 
            f'{self.batch_size})::INTEGER')
        left_select_items = [
            f'{left_alias}.{col[0]} AS left_{col[0]}' \
            for col in left_columns]
        right_select_items = [
            f'{right_alias}.{col[0]} AS right_{col[0]}' \
            for col in right_columns]
        fill_table_sql = (
            f'INSERT INTO {self.tmp_table} '
            f'SELECT NULL AS result, NULL AS simulated, '
            f'{left_batch_ID_exp} AS batch_ID_left, '
            f'{right_batch_ID_exp} AS batch_ID_right, '
            + ', '.join(left_select_items) + ', '
            + ', '.join(right_select_items) + ' '
            f'FROM {left_filtered_table} {left_alias}, '
            f'{right_filtered_table} {right_alias};'
        )
        self.db.execute2list(fill_table_sql)
        
        # Initialize task counters        
        task_count = self.db.execute2list(
            f'SELECT COUNT(*) FROM {self.tmp_table};')
        self.counters.nr_unprocessed = task_count[0][0]


class NestedLoopJoin(SemanticJoin):
    """ Nested loop version of the semantic join operator.
        
    This is a simple implementation of the semantic join,
    invoking the LLM for each pair of rows to check
    (i.e., a nested loops join).
    """
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
            messages = [message]
            model = self._select_model(messages)
            response = completion(
                model=model,
                messages=messages
            )
            self.update_cost_counters(model, response)
            result = str(response.choices[0].message.content)
            if result == '1':
                matches.append((left_key, right_key))
        return matches


class BatchJoin(SemanticJoin):
    """ More efficient version of the semantic join operator.
    
    Uses one LLM call to identify multiple matches,
    including in the prompt batches of data from both tables.
    """
    def _create_prompt(self, left_items, right_items):
        """ Creates a prompt for the LLM to find matches.
        
        Args:
            left_items: List of left table items.
            right_items: List of right table items.
        
        Returns:
            dict: Prompt message for the LLM.
        """
        task = (
            'Identify pairs of items from the left and right tables '
            f'that satisfy the join condition "{self.pred.condition}". '
            'Write only the IDs of matching pairs (e.g., "L3-R5), '
            'separated by commas. Write "." after the last pair. '
            'Sample output: "L3-R5,L4-R2,L1-R1." The output may be empty.'
            )
        content = [{
            'type': 'text',
            'text': task
            }
        ]
        for table_id, items in [
            ('L', left_items), 
            ('R', right_items)]:
            for item_idx, item in enumerate(items):
                item_ID = f'{table_id}{item_idx}'
                ID_part = {'type':'text', 'text': f'{item_ID}:'}
                content.append(ID_part)
                content.append(item)
        
        message = {
            'role': 'user',
            'content': content
        }
        return message

    def _extract_matches(self, left_keys, right_keys, llm_response):
        """ Extracts matching pairs from the LLM response.
        
        Args:
            left_keys: List of keys from the left table.
            right_keys: List of keys from the right table.
            llm_response: The response from the LLM containing matches.
        
        Returns:
            list: List of matching keys (tuples).
        """
        content = llm_response.choices[0].message.content
        # print(content)
        matching_keys = []
        pairs_str = content.split(',')
        for pair_str in pairs_str:
            left_ref, right_ref = pair_str.split('-')
            left_idx = int(left_ref[1:])
            right_idx = int(right_ref[1:])
            left_key = left_keys[left_idx]
            right_key = right_keys[right_idx]
            key_pair = (left_key, right_key)
            matching_keys.append(key_pair)
        
        return matching_keys        

    def _find_matches(self, pairs):
        """ Finds pairs satisfying the join condition.
        
        Args:
            pairs: List of key pairs to check for matches.
        
        Returns:
            list: List of key pairs that satisfy the join condition.
        """
        # Get list of unique keys from both tables
        left_keys = sorted(set(left_key for left_key, _ in pairs))
        right_keys = sorted(set(right_key for _, right_key in pairs))
        # Prepare the items for the LLM prompt
        left_items = [
            self._encode_item(left_key) \
            for left_key in left_keys]
        right_items = [
            self._encode_item(right_key) \
            for right_key in right_keys]
        # If there are no keys, return empty list
        nr_left_items = len(left_items)
        nr_right_items = len(right_items)
        if nr_left_items == 0 or nr_right_items == 0:
            return []
        # print(f'Nr of left items: {nr_left_items}, ')
        # print(f'Nr of right items: {nr_right_items}')
        # Construct prompt for LLM
        prompt = self._create_prompt(left_items, right_items)
        messages = [prompt]
        model = self._select_model(messages)
        # print(prompt)
        # print(f'Left join batch size: {len(left_items)}')
        # print(f'Right join batch size: {len(right_items)}')
        # Create logit bias toward numbers, hyphens, and "L"/"R"
        
        response = completion(
            temperature=0, 
            model=model,
            messages=messages,
            stop=['.']
        )
        self.update_cost_counters(model, response)
        matching_keys = []
        try:
            matching_keys = self._extract_matches(
                left_keys, right_keys, response)
        except:
            print('Incorrect output format in LLM reply - continuing join.')
            # traceback.print_exc()
            
        return matching_keys

    def _get_join_candidates(self, order):
        """ Retrieves unprocessed join pairs for LLM-based evaluation.
        
        Currently, ordered retrieval is not supported. The
        retrieval function retrieves all join pairs that are
        associated with a specific combination of left and
        right batch IDs.
        
        Args:
            order (str): None or tuple (table, column, ascending flag).
        
        Returns:
            list: List of key pairs from the left and right table.
        """
        # Get unprocessed batch IDs for left and right tables
        find_batch_ids_sql = (
            'SELECT batch_ID_left, batch_ID_right '
            f'FROM {self.tmp_table} '
            'WHERE result IS NULL '
            'LIMIT 1;')
        batch_ids = self.db.execute2list(find_batch_ids_sql)
        if len(batch_ids) == 0:
            return []
        batch_ID_left, batch_ID_right = batch_ids[0]
        
        # Get all key pairs associated with the batch IDs
        left_key_col = f'left_{self.pred.left_column}'
        right_key_col = f'right_{self.pred.right_column}'
        pairs_sql = (
            f'SELECT {left_key_col}, {right_key_col} '
            f'FROM {self.tmp_table} '
            f'WHERE batch_ID_left = {batch_ID_left} '
            f'AND batch_ID_right = {batch_ID_right} '
            f'AND result IS NULL;')
        pairs = self.db.execute2list(pairs_sql)
        return pairs
    
    def _gpt_join_bias(self, model):
        """ Add logit bias on output tokens for GPT models.
        
        Args:
            model (str): Name of the model to use.
        
        Returns:
            dict: Logit bias to encourage specific outputs for GPT models.
        """
        logit_bias = {}
        if self.gpt4_style_model(model):
            for i in range(10):
                logit_bias[i + 15] = 100
            
            logit_bias[11] = 100 # ,
            logit_bias[12] = 100 # -
            logit_bias[13] = 100 # .
            logit_bias[43] = 100 # L
            logit_bias[49] = 100 # R
        
        return logit_bias