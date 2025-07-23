'''
Created on Jul 22, 2025

@author: immanueltrummer
'''
import argparse
import time

from tdb.data.relational import Database
from tdb.execution.engine import ExecutionEngine
from tdb.queries.query import Query


if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--db', type=str,
        help='Path to the DuckDB database file.')
    args = parser.parse_args()
    
    db = Database(args.db)
    engine = ExecutionEngine(db)
    
    cmd = ''
    while not (cmd.lower() == '\\q'):
        cmd = input('Enter query (or "\\q" to quit): ')
        if cmd.lower() == '\\q':
            break
        
        query = Query(db, cmd)
        if query.semantic_predicates:
            start_time = time.time()
            result, costs = engine.run(query, None)
            total_time = time.time() - start_time
            print(f'Query executed in {total_time:.2f} seconds.')
            print(f'Execution costs: {costs}')
            print(f'Result: {result}')
        else:
            result = db.execute(cmd)
            print(result)
    
    print('Execution finished. Exiting console.')