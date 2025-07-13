from datatype import DataType


class NLColumnInfo:
    def __init__(self, col, con):
        self.col = col
        if col.datatype == DataType.NUM:
            result = con.execute(f"SELECT min({col.name}), max({col.name}), avg({col.name}) from {col.table}").fetchall()
            row = result[0]
            self.min_val = row[0]
            self.max_val = row[1]
            self.avg_val = row[2]
            print(f'Avg, Min, Max for {col.table}.{col.name}: {self.avg_val}, {self.min_val}, {self.max_val}')

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


class NLTableInfo:
    def __init__(self, table, con):
        self.table = table
        self.cols = {col.name: NLColumnInfo(col, con) for col in table.cols.values()}
        result = con.execute(f"SELECT count(*) from {table.name}").fetchall()
        self.nr_rows = result[0][0]
        print(f'# of rows for {table.name}: {self.nr_rows}')

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)


class NLDatabaseInfo:
    """Metadata about database. Can change when data change."""
    def __init__(self, nldb):
        self.tables = {table.name: NLTableInfo(table, nldb.con) for table in nldb.tables.values()}

    def __repr__(self):
        return str(self.__class__) + ": " + str(self.__dict__)

    def get_col_info_by_name(self, name):
        col_infos = [table.cols[name] for table in self.tables.values() if name in table.cols]
        nr_cols = len(col_infos)
        if nr_cols == 1:
            return col_infos[0]
        elif nr_cols > 2:
            raise ValueError(f'Multiple columns with the same name: {name} in {", ".join(col_info.col.table for col_info in col_infos)}')
        else:
            raise ValueError(f'No such column: {name}')


