'''
Created on Jul 17, 2025

@author: immanueltrummer
'''
import duckdb


class Database():
    """ Represents a relational database (DuckDB). """
    
    def __init__(self, database_name):
        """
        Initializes the database connection.

        Args:
            database_name (str): Name of the database file or ':memory:'.
        """
        self.con = duckdb.connect(database=database_name)
    
    def columns(self, table_name):
        """
        Retrieves the columns of a table.

        Args:
            table_name (str): Name of the table.

        Returns:
            List of column names and column types.
        """
        query = f'PRAGMA table_info({table_name})'
        result = self.con.execute(query).fetchall()
        return [(col[1], col[2]) for col in result]
    
    def execute2df(self, query):
        """
        Executes a SQL query on the database.

        Args:
            query (str): SQL query to execute.

        Returns:
            Result of the query execution as pandas data frame.
        """
        # print(f'Executing: {query}')
        return self.con.execute(query).df()
    
    def execute2list(self, query):
        """
        Executes a SQL query and returns the result as a list.

        Args:
            query (str): SQL query to execute.

        Returns:
            List of results from the query execution.
        """
        # print(f'Executing: {query}')
        return self.con.execute(query).fetchall()
    
    def schema(self):
        """ Retrieves the schema of the DuckDB database.

        Returns:
            Schema representation suitable for SQLglot library.
        """
        tables = self.tables()
        schema = {}
        for table in tables:
            table_schema = {}
            columns = self.columns(table)
            for col_name, col_type in columns:
                table_schema[col_name] = col_type
            schema[table] = table_schema
        return schema
    
    def tables(self):
        """ Retrieves the names of all tables in the DuckDB database.

        Returns:
            List of table names.
        """
        query = "SELECT table_name FROM duckdb_tables()"
        result = self.con.execute(query).fetchall()
        return [table[0] for table in result]


if __name__ == "__main__":
    db = Database('elephants.db')
    schema = db.schema()
    print(db.schema())
    import sqlglot
    from sqlglot.optimizer.qualify import qualify
    expression = sqlglot.parse_one("SELECT NL(ImagePath, 'Is it an elephant?') FROM images", read="duckdb")
    # print(expression.to_s())
    from sqlglot import exp
    qualified = qualify(expression, schema=schema)
    print(qualified.sql())
    print(list(qualified.find_all(exp.Anonymous)))