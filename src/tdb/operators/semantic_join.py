'''
Created on Jul 20, 2025

@author: immanueltrummer
'''
import traceback

from sqlglot import exp
from tdb.operators.semantic_operator import SemanticOperator


class SemanticJoin(SemanticOperator):
    """ Represents a semantic join operator in a query. """
    
    def __init__(self, db, operator_ID, query, join_predicate):
        """
        Initializes the semantic join operator.
        
        Args:
            db: Database containing the joined tables.
            operator_ID (str): Unique identifier for the operator.
            query: Query containing the join predicate.
            join_predicate: Join predicate expressed in natural language.
        """
        super().__init__(db, operator_ID)
        self.query = query
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
        raise NotImplementedError(
            'Instantiate one of the sub-classes of SemanticJoin!')
    
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
                f"AND right_{self.pred.right_column} = '{right_key}' "
                f'AND result IS NULL;')
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

        left_alias = self.pred.left_alias
        right_alias = self.pred.right_alias        
        left_select_items = [
            f'{left_alias}.{col[0]} AS left_{col[0]}' \
            for col in left_columns]
        right_select_items = [
            f'{right_alias}.{col[0]} AS right_{col[0]}' \
            for col in right_columns]
        other_filters_left = self.query.alias2unary_sql[left_alias]
        other_filters_right = self.query.alias2unary_sql[right_alias]
        other_filters = exp.And(
            this=other_filters_left,
            expression=other_filters_right)
        where_sql = 'WHERE ' + other_filters.sql()
        fill_table_sql = (
            f'INSERT INTO {self.tmp_table} '
            f'SELECT NULL AS result, NULL AS simulated, '
            + ', '.join(left_select_items) + ', '
            + ', '.join(right_select_items) + ' '
            f'FROM {self.pred.left_table} {left_alias}, '
            f'{self.pred.right_table} {right_alias} '
            ' ' + where_sql + ';'
        )
        self.db.execute(fill_table_sql)


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
            f'that satisfy the join condition "{self.pred.condition}".'
            'Write only the IDs of matching pairs (e.g., "L3-R5), '
            'separated by commas. Write "." after the last pair.'
            'Sample output: "L3-R5,L4-R2,L1-R1." The output may be empty.'
            )
        content = [task]
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
        print(content)
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
        # Construct prompt for LLM
        prompt = self._create_prompt(left_items, right_items)
        print(f'Left join batch size: {len(left_items)}')
        print(f'Right join batch size: {len(right_items)}')
        # Create logit bias toward numbers, hyphens, and "L"/"R"
        logit_bias = {}
        for i in range(10):
            logit_bias[i + 15] = 100
        
        logit_bias[11] = 100 # ,
        logit_bias[12] = 100 # -
        logit_bias[13] = 100 # .
        logit_bias[43] = 100 # L
        logit_bias[49] = 100 # R
        
        # Determine maximal number of tokens
        max_tokens = len(left_items) * len(right_items) * 10
        response = self.llm.chat.completions.create(
            model='gpt-4o',
            messages=[prompt],
            max_tokens=max_tokens,
            logit_bias=logit_bias,
            temperature=0.0,
            stop=['.']
        )
        matching_keys = []
        try:
            matching_keys = self._extract_matches(
                left_keys, right_keys, response)
        except:
            print('Incorrect output format in LLM reply - error:')
            traceback.print_exc()
            
        return matching_keys

    def _get_join_candidates(self, nr_keys, order):
        """ Retrieves up to a given number of join keys from each table.
        
        Currently, ordered retrieval is not supported. The
        function returns the Cartesian product of left and
        right keys (for compatibility with matching function).
        Each key that appears in the result has at least one
        unprocessed pair in the temporary table.
        
        Args:
            nr_keys (int): Number of keys to retrieve.
            order (str): None or tuple (table, column, ascending flag).
        
        Returns:
            list: List of key pairs from the left and right table.
        """
        # Query for unprocessed join pairs
        left_key_col = f'left_{self.pred.left_column}'
        right_key_col = f'right_{self.pred.right_column}'
        pairs_to_process_sql = (
            f'SELECT {left_key_col}, {right_key_col} '
            f'FROM {self.tmp_table} '
            f'WHERE result IS NULL ')
        
        # Retrieve requested number of keys from both tables
        keys_by_col = []
        for key_col in [left_key_col, right_key_col]:
            get_keys_sql = (
                f'WITH ThalamusDB_pairs AS ({pairs_to_process_sql}) '
                f'SELECT DISTINCT {key_col} FROM ThalamusDB_pairs '
                f'LIMIT {nr_keys}')
            print(get_keys_sql)
            keys = self.db.execute(get_keys_sql)
            keys_by_col.append(keys)
            
        # Create pairs of keys from both tables
        pairs = []
        for left_key in keys_by_col[0]:
            for right_key in keys_by_col[1]:
                pairs.append((left_key[0], right_key[0]))
                
        return pairs