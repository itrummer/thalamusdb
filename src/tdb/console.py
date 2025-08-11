'''
Created on Jul 22, 2025

@author: immanueltrummer
'''
import argparse
import sys
import time
import traceback

from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.rule import Rule
from tdb.data.relational import Database
from tdb.execution.constraints import Constraints
from tdb.execution.engine import ExecutionEngine
from tdb.queries.query import Query
from tdb.ui.util import print_df


def _is_terminal():
    """ Checks if both stdin and stdout are attached to a TTY.
    
    Returns:
        True if both stdin and stdout are TTYs, False otherwise.
    """
    return sys.stdin.isatty() and sys.stdout.isatty()


def _get_input(history):
    """ Gets input from the user, either via prompt_toolkit or standard input.
    
    Args:
        history: History object for storing input history.
    
    Returns:
        The input string from the user.
    """
    if _is_terminal():
        return prompt('Enter query (or "\\q" to quit): ', history=history)
    else:
        return input('Enter query (or "\\q" to quit): ')


def _print_welcome():
    """ Prints a welcome message for the console. """
    print(
'''Welcome to the ThalamusDB interactive console!

Use the following semantic predicates in your SQL queries (WHERE clause):
- NLfilter(table.column, condition): 
    filters rows based on a natural language condition
- NLjoin(table1.column1, table2.column2, condition):
    filters rows pairs based on a natural language join condition

Semantic predicates apply to columns of SQL type TEXT.
Those columns can contain paths of images or audio files.
ThalamusDB detects such cases based on file extensions.
E.g., if a cell contains a path to an image, ThalamusDB treats
the cell content as an image and uses suitable LLMs.
''')


def _process_query(db, engine, constraints, cmd):
    """ Processes a semantic SQL query command.
    
    Args:
        db: Database instance to execute the query on.
        engine: Execution engine to run the query.
        constraints: Constraints on query execution.
        cmd: SQL command string containing the query.
    """
    console = Console()
    try:
        query = Query(db, cmd)
        if query.semantic_predicates:
            start_time = time.time()
            result, counters = engine.run(query, constraints)
            total_time = time.time() - start_time
            console.print(Rule('Query Processing Summary'))
            print(f'Query executed in {total_time:.2f} seconds.')
            counters.pretty_print()
            print_df(result)
        else:
            result = db.execute2df(cmd)
            print_df(result)
    except Exception:
        print('Error processing query:')
        traceback.print_exc()


def run_console():
    """ Runs the interactive console for executing queries. """    
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'db', type=str,
        help='Path to the DuckDB database file.')
    args = parser.parse_args()
    
    db = Database(args.db)
    engine = ExecutionEngine(db)
    constraints = Constraints()
    history = InMemoryHistory()
    
    cmd = ''
    while not (cmd.lower() == '\\q'):
        cmd = _get_input(history)
        if cmd.lower() == '\\q':
            break
        elif cmd.startswith('set'):
            constraints.update(cmd)
        else:
            _process_query(
                db, engine, constraints, cmd)
    
    print('Execution finished. Exiting console.')


if __name__ == "__main__":
    run_console()