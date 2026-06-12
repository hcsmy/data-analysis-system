"""
数据分析模块 (机器学习分析)
负责：K-Means聚类、肘部法则、轮廓系数评估
==============================================
【供其他模块调用接口】
    from modules.ml_analysis import kmeans_cluster, calculate_elbow_value
"""
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


def kmeans_cluster(df, n_clusters=3):
    """
    执行K-Means聚类分析
    参数:
        df: pandas DataFrame
        n_clusters: 聚类数量 (默认3)
    
    返回:
        (结果DataFrame, 轮廓系数, 各簇样本数)
    """
    # 提取数值列进行聚类
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if not numeric_cols:
        raise ValueError("数据中没有数值列，无法进行聚类")
    
    data = df[numeric_cols].dropna()
    
    # 数据标准化
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(data)
    
    # 执行K-Means聚类
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
    labels = kmeans.fit_predict(scaled_data)
    
    # 计算轮廓系数（评估聚类效果）
    score = silhouette_score(scaled_data, labels)
    
    # 将聚类结果添加到原数据
    result_df = df.copy()
    result_df['cluster'] = -1  # 默认标记为-1（未参与聚类的行）
    result_df.loc[data.index, 'cluster'] = labels
    
    # 统计各簇样本数
    cluster_counts = pd.Series(labels).value_counts().sort_index().to_dict()
    
    return result_df, round(score, 4), cluster_counts


def calculate_elbow_value(df, max_k=10):
    """
    计算肘部法则的SSE值（用于确定最佳K值）
    参数:
        df: pandas DataFrame
        max_k: 最大尝试的K值 (默认10)
    
    返回:
        SSE值列表（索引0对应K=1，索引i对应K=i+1）
    """
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if not numeric_cols:
        return []
    
    data = df[numeric_cols].dropna()
    
    # 数据标准化
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(data)
    
    sse_values = []
    for k in range(1, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init='auto')
        kmeans.fit(scaled_data)
        sse_values.append(int(kmeans.inertia_))
    
    return sse_values


def linear_regression(df, x_col, y_col):
    """
    执行简单线性回归分析
    参数:
        df: pandas DataFrame
        x_col: 自变量列名
        y_col: 因变量列名
    
    返回:
        dict: 包含斜率、截距、R²值
    """
    from sklearn.linear_model import LinearRegression
    
    data = df[[x_col, y_col]].dropna()
    X = data[x_col].values.reshape(-1, 1)
    y = data[y_col].values
    
    model = LinearRegression()
    model.fit(X, y)
    
    y_pred = model.predict(X)
    ss_tot = ((y - y.mean()) ** 2).sum()
    ss_res = ((y - y_pred) ** 2).sum()
    r2 = 1 - (ss_res / ss_tot)
    
    return {
        'slope': round(float(model.coef_[0]), 4),
        'intercept': round(float(model.intercept_), 4),
        'r2': round(r2, 4),
        'formula': f"y = {round(float(model.coef_[0]), 4)} * x + {round(float(model.intercept_), 4)}"
    }


def get_column_stats(df):
    """
    获取数据的基本统计信息
    """
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    
    stats = {}
    for col in numeric_cols:
        col_data = df[col].dropna()
        if len(col_data) > 0:
            stats[col] = {
                'mean': round(col_data.mean(), 2),
                'std': round(col_data.std(), 2),
                'min': round(col_data.min(), 2),
                'max': round(col_data.max(), 2),
                'median': round(col_data.median(), 2),
                'count': int(col_data.count()),
                'missing': int(df[col].isnull().sum())
            }
    
    return stats