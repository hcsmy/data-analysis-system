"""
测试数据生成脚本
"""
import numpy as np
import pandas as pd
import os

np.random.seed(42)
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

n1 = 200
categories = ['电子产品', '服装鞋帽', '图书音像', '家居用品', '食品饮料', '办公用品']
regions = ['华东', '华南', '华北', '华中', '西南', '西北']
channels = ['线上-APP', '线上-小程序', '线下-门店', '线下-分销']

sales_data = pd.DataFrame({
    '订单ID': [f'ORD{10000 + i}' for i in range(n1)],
    '日期': pd.date_range('2025-01-01', periods=n1, freq='D'),
    '商品类别': np.random.choice(categories, n1),
    '地区': np.random.choice(regions, n1),
    '销售渠道': np.random.choice(channels, n1),
    '单价': np.round(np.random.uniform(10, 5000, n1), 2),
    '销量': np.random.randint(1, 100, n1),
    '折扣率': np.round(np.random.uniform(0, 0.5, n1), 2),
    '用户评分': np.round(np.random.uniform(1, 5, n1), 1),
})
sales_data['销售额'] = np.round(sales_data['单价'] * sales_data['销量'] * (1 - sales_data['折扣率']), 2)
sales_data['利润'] = np.round(sales_data['销售额'] * np.random.uniform(0.1, 0.4, n1), 2)

sales_data.to_csv(os.path.join(OUT_DIR, 'test_sales_data.csv'), index=False, encoding='utf-8-sig')
print(f'[OK] 电商销售数据: test_sales_data.csv ({n1} 行, {len(sales_data.columns)} 列)')

n2 = 150
departments = ['技术部', '市场部', '销售部', '财务部', '人事部', '运营部']
positions = ['初级', '中级', '高级', '专家']
genders = ['男', '女']
education = ['本科', '硕士', '博士', '大专']

perf_data = pd.DataFrame({
    '员工ID': [f'EMP{1000 + i}' for i in range(n2)],
    '姓名': [f'员工_{i:03d}' for i in range(n2)],
    '部门': np.random.choice(departments, n2),
    '职位级别': np.random.choice(positions, n2, p=[0.3, 0.35, 0.25, 0.1]),
    '性别': np.random.choice(genders, n2),
    '学历': np.random.choice(education, n2, p=[0.4, 0.3, 0.15, 0.15]),
    '年龄': np.random.randint(22, 55, n2),
    '工龄': np.round(np.random.uniform(0.5, 20, n2), 1),
    '月薪': np.round(np.random.uniform(5000, 35000, n2), 0),
    '绩效评分': np.round(np.clip(np.random.normal(75, 15, n2), 30, 100), 1),
    '项目完成数': np.random.randint(1, 30, n2),
    '加班时长': np.round(np.random.uniform(0, 80, n2), 1),
    '请假天数': np.round(np.random.uniform(0, 30, n2), 1),
})
perf_data['年薪'] = np.round(perf_data['月薪'] * (12 + np.random.randint(1, 5, n2)), 0)

perf_data.to_csv(os.path.join(OUT_DIR, 'test_employee_data.csv'), index=False, encoding='utf-8-sig')
print(f'[OK] 员工绩效数据: test_employee_data.csv ({n2} 行, {len(perf_data.columns)} 列)')

print('\n两组测试数据已生成。')
