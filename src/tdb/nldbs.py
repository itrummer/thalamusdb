import time

import numpy as np
import pandas as pd
import duckdb

import tdb.config_tdb
from tdb.datatype import ImageDataset, DataType
from tdb.nlfilter import GPTImageProcessor, GPTTextProcessor
from tdb.schema import NLDatabase, NLTable, NLColumn
from openai import OpenAI

dfs = {}


def get_df_by_name(table_name):
    if table_name in dfs:
        return dfs[table_name]
    else:
        if table_name == "furniture":
            df = read_csv_furniture()
        elif table_name == "furniture_imgs":
            df = read_csv_furniture_imgs()
        else:
            raise ValueError(f"Wrong table name: {table_name}")
        dfs[table_name] = df
        return df


def get_nldb_by_name(dbname):
    if dbname == "craigslist":
        return craigslist()
    else:
        raise ValueError(f"Wrong nldb name: {dbname}")


def read_csv_furniture():
    df = pd.read_csv("benchmarks/craigslist/furnitures.csv")
    df["title_u"] = np.arange(len(df))
    df["neighborhood_u"] = np.arange(len(df))
    df["url_u"] = np.arange(len(df))
    return df


def read_csv_furniture_imgs():
    df = pd.read_csv("benchmarks/craigslist/imgs.csv")
    return df


def add_count_columns(relationships, name2df):
    for table_dim, col_dim, table_fact, col_fact in relationships:
        df_fact = name2df[table_fact]
        df_counts = df_fact[col_fact].value_counts().reset_index()
        col_count = col_dim + "_c"
        df_counts.columns = [col_dim, col_count]

        df_dim = name2df[table_dim]
        merged_df = df_dim.merge(df_counts, on=col_dim, how="left")
        merged_df[col_count] = merged_df[col_count].fillna(0)
        name2df[table_dim] = merged_df
    return name2df


def craigslist():
    print(f"Initializing NL Database: Craigslist")

    # Read furniture table from csv.
    df_furniture = get_df_by_name("furniture")

    df_images = get_df_by_name("furniture_imgs").copy()
    img_paths = df_images["img"]
    dataset = ImageDataset(img_paths, [])
    model = OpenAI()
    processor = GPTImageProcessor(dataset, model)
    df_images["img"] = np.arange(len(df_images))

    nr_imgs = len(dataset)
    print(f"len(images): {nr_imgs}")

    # For foreign key relationships, add an extra column.
    name2df = {"furniture": df_furniture, "images": df_images}
    relationships = [("furniture", "aid", "images", "aid")]
    name2df = add_count_columns(relationships, name2df)

    # Initialize tables in DuckDB.
    con = duckdb.connect(database=":memory:")  # , check_same_thread=False)
    # con = duckdb.connect('craigslist.db')
    for name, df in name2df.items():
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
    con.execute("CREATE UNIQUE INDEX furniture_aid_idx ON furniture (aid)")
    print(f"len(furniture): {len(df_furniture)}")

    # Load text dataset and processor for the title column.
    neighborhood_processor = GPTTextProcessor(df_furniture["neighborhood"], model)
    title_processor = GPTTextProcessor(df_furniture["title"], model)
    url_processor = GPTTextProcessor(df_furniture["url"], model)

    # Create NL database.
    furniture = NLTable("furniture")
    furniture.add(
        NLColumn("aid", DataType.NUM),
        NLColumn("time", DataType.NUM),
        NLColumn("neighborhood", DataType.TEXT),
        NLColumn("neighborhood_u", DataType.NUM, neighborhood_processor),
        NLColumn("title", DataType.TEXT),
        NLColumn("title_u", DataType.NUM, title_processor),
        NLColumn("url", DataType.TEXT),
        NLColumn("url_u", DataType.NUM, url_processor),
        NLColumn("price", DataType.NUM),
    )
    images = NLTable("images")
    images.add(NLColumn("img", DataType.IMG, processor), NLColumn("aid", DataType.NUM))
    nldb = NLDatabase("craigslist", con)
    nldb.add(furniture, images)
    nldb.add_relationships(*relationships)
    for table_dim, col_dim, _, _ in relationships:
        nldb.tables[table_dim].add(NLColumn(f"{col_dim}_c", DataType.NUM))
    # Initialize metadata information.
    nldb.init_info()
    return nldb