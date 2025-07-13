import time

from torchvision import transforms
import numpy as np
import pandas as pd
import duckdb

import config_tdb
from datatype import AudioDataset, ImageDataset, DataType
from nlfilter import GPTImageProcessor, GPTTextProcessor, ImageProcessor, TextProcessor, AudioProcessor
from repository import ModelRepository
from schema import NLDatabase, NLTable, NLColumn

dfs = {}
repository = ModelRepository()


def get_df_by_name(table_name):
    if table_name in dfs:
        return dfs[table_name]
    else:
        if table_name == "furniture":
            df = read_csv_furniture()
        elif table_name == "furniture_imgs":
            df = read_csv_furniture_imgs()
        elif table_name == "youtube":
            df = read_csv_youtube()
        elif table_name == "movies":
            df = read_csv_netflix_movies()
        elif table_name == "ratings":
            df = read_csv_netflix_ratings()
        else:
            raise ValueError(f"Wrong table name: {table_name}")
        dfs[table_name] = df
        return df


def get_nldb_by_name(dbname):
    if dbname == "craigslist":
        return craigslist()
    elif dbname == "youtubeaudios":
        return youtubeaudios()
    elif dbname == "netflix":
        return netflix()
    else:
        raise ValueError(f"Wrong nldb name: {dbname}")


def read_csv_furniture():
    df = pd.read_csv("craigslist/furnitures.csv")
    df["title_u"] = np.arange(len(df))
    df["neighborhood_u"] = np.arange(len(df))
    df["url_u"] = np.arange(len(df))
    return df


def read_csv_furniture_imgs():
    df = pd.read_csv("craigslist/imgs.csv")
    return df


def read_csv_youtube():
    df = pd.read_csv("audiocaps/youtube.csv")
    df["description"] = df["description"].fillna("")
    df["likes"] = df["likes"].fillna(0)
    df["description_u"] = np.arange(len(df))
    df["audio"] = np.arange(len(df))
    return df


def read_csv_netflix_movies():
    df = pd.read_csv("netflix/movies_with_reviews.csv")
    df = df.drop("review_label", axis=1, errors="ignore")
    df["featured_review_u"] = np.arange(len(df))
    return df


def read_csv_netflix_ratings():
    df = pd.read_csv("netflix/ratings.csv")
    df.columns = [col.lower() for col in df.columns]
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
    t = transforms.Compose([transforms.ToPILImage()])
    dataset = ImageDataset(img_paths, t)
    if config_tdb.GUI:
        model = repository.get_gpt_model()
        processor = GPTImageProcessor(dataset, model)
    else:
        model, preprocess, t = repository.get_image_model()
        processor = ImageProcessor(dataset, model, preprocess, repository.device_id)
    df_images["img"] = np.arange(len(df_images))

    nr_imgs = len(dataset)
    print(f"len(images): {nr_imgs}")

    # For foreign key relationships, add an extra column.
    name2df = {"furniture": df_furniture, "images": df_images}
    relationships = [("furniture", "aid", "images", "aid")]
    name2df = add_count_columns(relationships, name2df)

    # Initialize tables in duckdb.
    con = duckdb.connect(database=":memory:")  # , check_same_thread=False)
    for name, df in name2df.items():
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
    con.execute("CREATE UNIQUE INDEX furniture_aid_idx ON furniture (aid)")
    print(f"len(furniture): {len(df_furniture)}")

    # Load text dataset and processor for the title column.
    if config_tdb.GUI:
        neighborhood_processor = GPTTextProcessor(df_furniture["neighborhood"], model)
        title_processor = GPTTextProcessor(df_furniture["title"], model)
        url_processor = GPTTextProcessor(df_furniture["url"], model)
    else:
        text_model = repository.get_text_model()
        neighborhood_processor = TextProcessor(df_furniture["neighborhood"], text_model, repository.device)
        title_processor = TextProcessor(df_furniture["title"], text_model, repository.device)
        url_processor = TextProcessor(df_furniture["url"], text_model, repository.device)

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


def youtubeaudios():
    print(f"Initializing NL Database: YoutubeAudios")

    # Read youtube table.
    df = get_df_by_name("youtube")
    # Load audio dataset and processor for the audio column. Only include valid audios.
    dataset = AudioDataset(valid_idxs=df["audio"])
    model, preprocess = repository.get_audio_model()
    processor = AudioProcessor(dataset, model, preprocess, repository.device_id)
    # model = get_audio_model(repository.device)
    # processor = AudioProcessor(dataset, model, repository.device)
    print(f"GPU - Audio Model: {next(model.parameters()).is_cuda}")

    # Register youtube table. Should be done after updating the audio column.
    con = duckdb.connect(database=":memory:")  # , check_same_thread=False)
    con.execute("CREATE TABLE youtube AS SELECT * FROM df")

    # Load text dataset and processor for the description column.
    text_model = repository.get_text_model()
    description_processor = TextProcessor(df["description"], text_model, repository.device)

    # Create NL database.
    youtube = NLTable("youtube")
    youtube.add(
        NLColumn("youtube_id", DataType.TEXT),
        NLColumn("audio", DataType.AUDIO, processor),
        NLColumn("title", DataType.TEXT),
        NLColumn("category", DataType.TEXT),
        NLColumn("viewcount", DataType.NUM),
        NLColumn("author", DataType.TEXT),
        NLColumn("length", DataType.NUM),
        NLColumn("duration", DataType.TEXT),
        NLColumn("likes", DataType.NUM),
        NLColumn("description", DataType.TEXT),
        NLColumn("description_u", DataType.NUM, description_processor),
    )
    nldb = NLDatabase("youtubeaudios", con)
    nldb.add(youtube)
    # Initialize metadata information.
    nldb.init_info()
    return nldb


def netflix():
    print(f"Initializing NL Database: Netflix")

    start = time.time()
    # Read movie table.
    df_movie = get_df_by_name("movies")
    # Read rating table.
    df_rating = get_df_by_name("ratings")
    end = time.time()
    print(f"Finished reading csv: {end - start}")

    # For foreign key relationships, add an extra column.
    name2df = {"movies": df_movie, "ratings": df_rating}
    relationships = [("movies", "movieid", "ratings", "movieid")]
    start = time.time()
    name2df = add_count_columns(relationships, name2df)
    end = time.time()
    print(f"Finished adding column for foreign key relationship: {end - start}")

    # Register tables.
    start = time.time()
    con = duckdb.connect(database=":memory:")  # , check_same_thread=False)
    for name, df in name2df.items():
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
    end = time.time()
    print(f"Finished registering tables: {end - start}")

    # Load text dataset and processor for the description column.
    text_model = repository.get_text_model()
    # print(f'GPU - Text Model: {next(text_model.parameters()).is_cuda}')
    title_processor = TextProcessor(df_movie["movietitle"], text_model, repository.device)
    featured_review_processor = TextProcessor(
        df_movie["featured_review"], text_model, repository.device
    )

    # Create NL database.
    movies = NLTable("movies")
    movies.add(
        NLColumn("movieid", DataType.NUM),
        NLColumn("releaseyear", DataType.NUM),
        NLColumn("movietitle", DataType.TEXT),
        NLColumn("movietitle_u", DataType.NUM, title_processor),
        NLColumn("featured_review", DataType.TEXT),
        NLColumn("featured_review_u", DataType.NUM, featured_review_processor),
    )
    ratings = NLTable("ratings")
    ratings.add(
        NLColumn("custid", DataType.NUM),
        NLColumn("rating", DataType.NUM),
        NLColumn("date", DataType.TEXT),
        NLColumn("movieid", DataType.NUM),
    )
    nldb = NLDatabase("netflix", con)
    nldb.add(movies, ratings)
    nldb.add_relationships(*relationships)
    for table_dim, col_dim, _, _ in relationships:
        nldb.tables[table_dim].add(NLColumn(f"{col_dim}_c", DataType.NUM))
    # Initialize metadata information.
    nldb.init_info()
    return nldb
