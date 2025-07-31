'''
Created on Jul 31, 2025

@author: immanueltrummer
'''
from rich.console import Console
from rich.table import Table


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