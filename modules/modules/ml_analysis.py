# modules/ml_analysis.py
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

def get_numeric_data(df):
    num_df = df.select_dtypes(include=[np.number])
    return num_df, df

def kmeans_cluster(df, n_cluster):
    num_df, origin_df = get_numeric_data(df)
    if num_df.empty:
        return None, "无可用于聚类的数值数据", None
    km = KMeans(n_clusters=n_cluster, random_state=42)
    cluster_label = km.fit_predict(num_df)
    origin_df["聚类分组"] = cluster_label
    score = silhouette_score(num_df, cluster_label)
    group_count = origin_df["聚类分组"].value_counts().to_dict()
    return origin_df, round(score,4), group_count

def calculate_elbow_value(df, max_k=10):
    num_df,_ = get_numeric_data(df)
    sse_list = []
    for k in range(1,max_k+1):
        km = KMeans(n_clusters=k,random_state=42)
        km.fit(num_df)
        sse_list.append(km.inertia_)
    return sse_list
