from tdb.data.datatype import DataType
from tdb.optimization.stats import NLDatabaseInfo

class NLColumn:
    def __init__(self, name, datatype, processor=None):
        self.name = name
        self.datatype = datatype
        self.processor = processor
        assert not (DataType.is_unstructured_except_text(self.datatype) and self.processor is None)
        # table is initialized when column is added to table.
        self.table = None

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


class NLTable:
    def __init__(self, name):
        self.name = name
        self.cols = {}
        self.db = None

    def add(self, *cols):
        for col in cols:
            col.table = self.name
            self.cols[col.name] = col

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


class NLDatabase:
    def __init__(self, name, con):
        self.name = name
        self.con = con
        self.tables = {}
        self.info = None
        # Join on two tables, e.g., {(table1, table2): (table1, col1, table2, col2)}.
        self.__relationships = {}

    def add(self, *tables):
        for table in tables:
            table.db = self.name
            self.tables[table.name] = table

    def add_relationships(self, *relationships):
        for relationship in relationships:
            table1, col1, table2, col2 = relationship
            assert table1 != table2
            key = (table1, table2) if table1 < table2 else (table2, table1)
            self.__relationships[key] = relationship

    def get_count_columns_for_foreign_key(self, query):
        cols_count = []
        for table1, col1, table2, col2 in self.__relationships.values():
            if table1 in query.tables and table2 in query.tables:
                cols_count.append(col1 + "_c")
        return cols_count

    def init_info(self):
        self.info = NLDatabaseInfo(self)

    def get_col_by_name(self, name):
        cols = [table.cols[name] for table in self.tables.values() if name in table.cols]
        nr_cols = len(cols)
        if nr_cols == 1:
            return cols[0]
        elif nr_cols > 2:
            raise ValueError(f'Multiple columns with the same name: {name} in {", ".join(col.table for col in cols)}')
        else:
            raise ValueError(f'No such column: {name}')

    def get_table_by_col_from_query(self, col_name, query):
        for table_name in query.tables:
            if col_name in self.tables[table_name].cols:
                return table_name
        raise ValueError(f'No table with such column: {col_name}')

    def _get_relationship_cols(self, table1, table2):
        assert table1 != table2
        key = (table1, table2) if table1 < table2 else (table2, table1)
        table1, col1, table2, col2 = self.__relationships[key]
        return (col1, col2) if table1 == key[0] else (col2, col1)