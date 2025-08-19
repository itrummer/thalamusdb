'''
Created on Jul 31, 2025

@author: immanueltrummer
'''
from rich.console import Console
from rich.table import Table


def df2set(df):
    """ Converts a pandas data frame to a set of tuples.
    
    Args:
        df: a pandas data frame.
    
    Returns:
        A set of tuples representing the rows of the data frame.
    """
    return set(tuple(row) for row in df.values)


def print_df(df, title='Query Result'):
    """ Prints a pandas data frame as a table.
    
    Args:
        df: a pandas data frame.
        title: title of the table (default is 'Query Result').
    """
    match title:
        case 'Execution Counters':
            style = 'blue'
        case 'Query Result':
            style = 'red'
        case _:
            style = 'black'

    table = Table(title=title, expand=True, style=style)
    for col in df.columns:
        table.add_column(col, justify='left')
    
    for row in df.itertuples(index=False):
        table.add_row(*[str(item) for item in row])
    
    console = Console()
    console.print(table)


def print_progress(nr_processed, nr_unprocessed):
    """ Print execution progress updates.
    
    Args:
        nr_processed: number of processed tasks.
        nr_unprocessed: number of unprocessed tasks.
    """
    nr_total = nr_processed + nr_unprocessed
    console = Console()
    console.print(f'Processed {nr_processed}/{nr_total} (max) tasks.')