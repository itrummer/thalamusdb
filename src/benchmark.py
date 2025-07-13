import datetime
import itertools
import random
import re
import string
import time

import pandas as pd

import config_tdb
from constraint import TDBConstraint
import nldbs
from query import NLQuery


def queries_craigslist():
    templates = [
        "select * from images where {i_pred} limit 10",
        "select {agg} from images, furniture where {any_pred} and images.aid = furniture.aid",
        "select * from images, furniture where {any_pred} and images.aid = furniture.aid limit 10",
        "select {agg} from images, furniture where ({i_pred} and {f_pred}) and images.aid = furniture.aid",
        "select * from images, furniture where ({i_pred} and {f_pred}) and images.aid = furniture.aid limit 10",
        "select {agg} from images, furniture where ({i_pred} or {f_pred}) and images.aid = furniture.aid",
        "select * from images, furniture where ({i_pred} or {f_pred}) and images.aid = furniture.aid limit 10",
    ]
    col2conditions = {
        "img": [
            "blue chair"
        ],  # ['leather sofa', 'wooden chair', 'dining table', 'sofa', 'table', 'wooden'],
        "title_u": ["wood"],
    }
    col2preds = {
        col: [f"nl({col}, '{condition}')" for condition in conditions]
        for col, conditions in col2conditions.items()
    }
    agg_funcs = ["min", "max", "sum", "avg"]
    agg_cols = ["price"]
    aggs = ["count(*)"] + [
        f"{func}({col})" for func, col in itertools.product(agg_funcs, agg_cols)
    ]
    type2preds = {
        "agg": aggs,
        "f_pred": col2preds["title_u"],
        "i_pred": col2preds["img"],
        "any_pred": col2preds["title_u"] + col2preds["img"],
    }
    queries = []
    for template in templates:
        var_types = [
            v[1] for v in string.Formatter().parse(template) if v[1] is not None
        ]
        for var_instances in itertools.product(
            *[type2preds[var_type] for var_type in var_types]
        ):
            query = re.sub("\{.*?\}", "{}", template).format(*var_instances)
            print(query)
            queries.append(query)
    print(len(queries))
    return queries


def queries_youtubeaudios():
    templates = [
        "select {agg} from youtube where {any_pred}",
        "select * from youtube where {any_pred} limit 10",
        "select {agg} from youtube where {a_pred} and {d_pred}",
        "select * from youtube where {a_pred} and {d_pred} limit 10",
        "select {agg} from youtube where {a_pred} or {d_pred}",
        "select * from youtube where {a_pred} or {d_pred} limit 10",
    ]
    col2conditions = {
        "audio": ["voices"],
        "description_u": ["cooking"],
    }
    col2preds = {
        col: [f"nl({col}, '{condition}')" for condition in conditions]
        for col, conditions in col2conditions.items()
    }
    agg_funcs = ["min", "max", "sum", "avg"]
    agg_cols = ["likes"]
    aggs = ["count(*)"] + [
        f"{func}({col})" for func, col in itertools.product(agg_funcs, agg_cols)
    ]
    type2preds = {
        "agg": aggs,
        "a_pred": col2preds["audio"],
        "d_pred": col2preds["description_u"],
        "any_pred": col2preds["audio"] + col2preds["description_u"],
    }
    queries = []
    for template in templates:
        var_types = [
            v[1] for v in string.Formatter().parse(template) if v[1] is not None
        ]
        for var_instances in itertools.product(
            *[type2preds[var_type] for var_type in var_types]
        ):
            query = re.sub("\{.*?\}", "{}", template).format(*var_instances)
            print(query)
            queries.append(query)
    print(len(queries))
    return queries


def queries_netflix():
    templates = [
        "select {agg} from ratings, movies where {any_pred} and ratings.movieid = movies.movieid",
        "select * from ratings, movies where {any_pred} and ratings.movieid = movies.movieid limit 10",
    ]
    col2conditions = {
        "featured_review_u": ["positive"],  #
    }
    col2preds = {
        col: [f"nl({col}, '{condition}')" for condition in conditions]
        for col, conditions in col2conditions.items()
    }
    agg_funcs = ["min", "max", "sum", "avg"]
    agg_cols = ["rating"]
    aggs = ["count(*)"] + [
        f"{func}({col})" for func, col in itertools.product(agg_funcs, agg_cols)
    ]
    type2preds = {
        "agg": aggs,
        "f_pred": col2preds["featured_review_u"],
        "any_pred": col2preds["featured_review_u"],
    }
    queries = []
    for template in templates:
        var_types = [
            v[1] for v in string.Formatter().parse(template) if v[1] is not None
        ]
        for var_instances in itertools.product(
            *[type2preds[var_type] for var_type in var_types]
        ):
            query = re.sub("\{.*?\}", "{}", template).format(*var_instances)
            print(query)
            queries.append(query)
    print(len(queries))
    return queries


ground_truths = {
    "blue chair": 27.054,  # ResNet50: 21.63, # craigslist
    "good condition": 0.3201,  # craigslist
    "wood": 0.9013 if config_tdb.USE_BART else 0.351764,  # craigslist
    "cooking": 0.8506 if config_tdb.USE_BART else 0.28863,  # youtubeaudios
    "voices": -28.57,  # ATR: -32.8471, # youtubeaudios
    "driving": 0.2256,  # youtubeaudios
    "galaxy": 0.3538,  # netflix
    "positive": 0.5380 if config_tdb.USE_BART else -0.01698,  # netflix
}


def main():
    # (constrained metric, value, ratio versus runtime)
    temp_constraints = [('error', 0.1, 1), ('error', 0.1, 10000), ('runtime', 10, 1), ('runtime', 10, 10000), ('feedback', 5, 1), ('feedback', 5, 10000)]
    constraints = [TDBConstraint(*constraint) for constraint in temp_constraints]
    methods = ["local"]
    shuffle_queries = False
    random.seed(1)

    sqls_craigslist = queries_craigslist()
    if shuffle_queries:
        random.shuffle(sqls_craigslist)
        for sql in sqls_craigslist:
            print(sql)

    sqls_youtubeaudios = queries_youtubeaudios()
    if shuffle_queries:
        random.shuffle(sqls_youtubeaudios)
        for sql in sqls_youtubeaudios:
            print(sql)

    sqls_netflix = queries_netflix()
    if shuffle_queries:
        random.shuffle(sqls_netflix)
        for sql in sqls_netflix:
            print(sql)

    dbname_to_sqls = {
        "craigslist": sqls_craigslist,
        "youtubeaudios": sqls_youtubeaudios,
        "netflix": sqls_netflix,
    }

    dict_csv = {
        "timestamp": [],
        "db": [],
        "method": [],
        "constraint": [],
        "sql": [],
        "total_time": [],
        "time_optimize": [],
        "time_sql": [],
        "time_ml": [],
        "error": [],
        "estimated_cost": [],
        "percent_processed": [],
        "nr_feedbacks": [],
        "nr_actions": [],
        "cost": [],
    }
    pd.DataFrame(dict_csv).to_csv("log/benchmark.csv", mode="a", index=False)
    for constraint in constraints:
        for dbname, sqls in dbname_to_sqls.items():
            for method in methods:
                for sql in sqls:
                    nl_permutations = (
                        itertools.permutations(range(0, len(NLQuery(sql).nl_preds)))
                        if method == "ordered"
                        else range(0, 1)
                    )
                    for nl_permutation in nl_permutations:
                        print(sql)
                        query = NLQuery(sql)
                        nldb = nldbs.get_nldb_by_name(dbname)
                        start = time.time()
                        if method == "naive":
                            info = nldb.run_baseline(query, ground_truths)
                        elif method == "ordered":
                            info = nldb.run_baseline_ordered(
                                query, nl_permutation, ground_truths
                            )
                        elif (
                            method == "rl"
                            or method == "random"
                            or method == "local"
                            or method[0] == "cost"
                        ):
                            info = nldb.run(query, constraint, ground_truths, method)
                        else:
                            raise ValueError(f"Unknown method name: {method}")
                        end = time.time()
                        total_time = end - start
                        print(
                            f"RESULT {method} {constraint} {sql} - TIME/COST/IMAGES/FEEDBACKS: {total_time} {info['estimated_cost']} {info['processed']} {info['feedback']}"
                        )

                        dict_csv["timestamp"].append(str(datetime.datetime.now()))
                        dict_csv["db"].append(dbname)
                        dict_csv["method"].append(method)
                        dict_csv["constraint"].append(str(constraint))
                        dict_csv["sql"].append(sql)
                        dict_csv["total_time"].append(total_time)
                        dict_csv["time_optimize"].append(info.get("time_optimize"))
                        dict_csv["time_sql"].append(info.get("time_sql"))
                        dict_csv["time_ml"].append(info.get("time_ml"))
                        dict_csv["error"].append(info["error"])
                        dict_csv["estimated_cost"].append(info["estimated_cost"])
                        dict_csv["percent_processed"].append(info["processed"])
                        dict_csv["nr_feedbacks"].append(info["feedback"])
                        dict_csv["nr_actions"].append(info.get("nr_actions"))
                        cost = constraint.cost(
                            info["error"], sum(info["feedback"]), total_time
                        )
                        dict_csv["cost"].append(cost)

                        pd.DataFrame(dict_csv).iloc[-1:].to_csv(
                            "log/benchmark.csv", mode="a", header=False, index=False
                        )


if __name__ == "__main__":
    main()
