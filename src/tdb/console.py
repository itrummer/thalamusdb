'''
Created on Jul 22, 2025

@author: immanueltrummer
'''
import argparse
import time
import traceback

from tdb.data.relational import Database
from tdb.execution.engine import ExecutionEngine
from tdb.queries.query import Query


def print_welcome():
    """ Prints a welcome message for the console. """
    print(
'''Welcome to the ThalamusDB interactive console!

Use the following semantic predicates in your SQL queries (WHERE clause):
- NLfilter(table, column, condition): 
    filters rows based on a natural language condition
- NLjoin(table1, column1, table2, column2, condition):
    filters rows pairs based on a natural language join condition

Semantic predicates apply to columns of SQL type TEXT.
Those columns can contain paths of images. ThalamusDB
detects such cases by exploiting the file extension.
If a cell contains a path to an image, ThalamusDB treats
the cell content as an image and uses suitable LLMs.
''')


def run_console():
    """ Runs the interactive console for executing queries. """    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'db', type=str,
        help='Path to the DuckDB database file.')
    args = parser.parse_args()
    
    print_welcome()
    
    db = Database(args.db)
    engine = ExecutionEngine(db)
    
    cmd = ''
    while not (cmd.lower() == '\\q'):
        cmd = input('Enter query (or "\\q" to quit): ')
        if cmd.lower() == '\\q':
            break
        
        try:
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
        except Exception:
            print('Error processing query:')
            traceback.print_exc()
    
    print('Execution finished. Exiting console.')


if __name__ == "__main__":
    run_console()