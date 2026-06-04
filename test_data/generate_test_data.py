import numpy as np
import pandas as pd
import os

np.random.seed(42)
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

n = 36
dates = pd.date_range('2025-01-01', periods=n, freq='W-MON')
categories = ['电子产品', '服装鞋帽', '图书音像', '家居用品']
regions = ['华东', '华南', '华北']
channels = ['线上', '线下']

df = pd.DataFrame({
    '日期': dates,
    '商品类别': np.random.choice(categories, n),
    '地区': np.random.choice(regions, n),
    '渠道': np.random.choice(channels, n),
    '单价': np.round(np.random.uniform(50, 2000, n), 2),
    '销量': np.random.randint(5, 80, n),
    '评分': np.round(np.clip(np.random.normal(4.0, 0.8, n), 1, 5), 1),
})
df['销售额'] = np.round(df['单价'] * df['销量'], 2)

pool = list(range(n))
missing_score = np.random.choice(pool, 4, replace=False)
pool = [i for i in pool if i not in missing_score]
missing_channel = np.random.choice(pool, 3, replace=False)
pool = [i for i in pool if i not in missing_channel]
outlier_indices = np.random.choice(pool, 2, replace=False)

df.loc[missing_score, '评分'] = np.nan
df.loc[missing_channel, '渠道'] = np.nan
df.loc[outlier_indices, '单价'] = df.loc[outlier_indices, '单价'] * 8

dup_rows = df.iloc[[2, 8, 20]]
df = pd.concat([df, dup_rows], ignore_index=True)

filename = 'test_data_demo.csv'
filepath = os.path.join(OUT_DIR, filename)
df.to_csv(filepath, index=False, encoding='utf-8-sig')
print(f'[OK] {filename} ({len(df)} 行, {len(df.columns)} 列)')
print(f'     缺失值总计: {df.isnull().sum().sum()} 个')
for col in df.columns:
    cnt = int(df[col].isnull().sum())
    if cnt > 0:
        print(f'       - {col}: {cnt} 个缺失')
print(f'     重复行: {df.duplicated().sum()} 行')
print(f'     异常值: 单价列有 2 个极值')
