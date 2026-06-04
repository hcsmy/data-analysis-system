"""
数据清洗模块
负责：缺失值处理、异常值检测、自动化清洗规则配置
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field, asdict
from typing import Literal
import json


# ==================== 缺失值分析 ====================

def get_missing_info(df: pd.DataFrame) -> dict:
    """获取缺失值统计信息"""
    missing_count = df.isnull().sum()
    missing_percent = (missing_count / len(df) * 100).round(2)
    total_missing = int(missing_count.sum())
    total_cells = df.shape[0] * df.shape[1]
    overall_percent = round(total_missing / total_cells * 100, 2) if total_cells > 0 else 0

    columns_missing = []
    for col in df.columns:
        cnt = int(missing_count[col])
        if cnt > 0:
            columns_missing.append({
                'column': col,
                'missing_count': cnt,
                'missing_percent': float(missing_percent[col]),
                'dtype': str(df[col].dtype)
            })

    return {
        'total_missing': total_missing,
        'overall_percent': overall_percent,
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'columns_missing': columns_missing
    }


# ==================== 缺失值处理 ====================

FillMethod = Literal['drop', 'mean', 'median', 'mode', 'custom']


def handle_missing(df: pd.DataFrame, columns: list[str],
                   method: FillMethod = 'mean', fill_value: str = '') -> tuple[pd.DataFrame, str]:
    """
    处理缺失值
    参数:
        df: 原始 DataFrame
        columns: 需要处理的列名列表
        method: 处理方法 (drop/mean/median/mode/custom)
        fill_value: 自定义填充值 (method='custom' 时使用)
    返回: (处理后的 DataFrame, 操作描述)
    """
    df_result = df.copy()
    valid_cols = [c for c in columns if c in df_result.columns]
    invalid_cols = [c for c in columns if c not in df_result.columns]

    if not valid_cols:
        return df_result, "未选择有效的列"

    if method == 'drop':
        before_rows = len(df_result)
        df_result = df_result.dropna(subset=valid_cols)
        after_rows = len(df_result)
        removed = before_rows - after_rows
        desc = f"删除含缺失值的行（基于 {len(valid_cols)} 列），共移除 {removed} 行"
        if invalid_cols:
            desc += f"，{len(invalid_cols)} 列不存在已跳过"

    elif method == 'mean':
        filled_count = 0
        for col in valid_cols:
            if pd.api.types.is_numeric_dtype(df_result[col]):
                fill = df_result[col].mean()
                missing_before = int(df_result[col].isnull().sum())
                df_result[col] = df_result[col].fillna(fill)
                filled_count += missing_before
        desc = f"均值填充完成，共填充 {filled_count} 个缺失值（仅数值列）"
        if invalid_cols:
            desc += f"，{len(invalid_cols)} 列不存在已跳过"

    elif method == 'median':
        filled_count = 0
        for col in valid_cols:
            if pd.api.types.is_numeric_dtype(df_result[col]):
                fill = df_result[col].median()
                missing_before = int(df_result[col].isnull().sum())
                df_result[col] = df_result[col].fillna(fill)
                filled_count += missing_before
        desc = f"中位数填充完成，共填充 {filled_count} 个缺失值（仅数值列）"
        if invalid_cols:
            desc += f"，{len(invalid_cols)} 列不存在已跳过"

    elif method == 'mode':
        filled_count = 0
        for col in valid_cols:
            mode_series = df_result[col].mode()
            if len(mode_series) > 0:
                fill = mode_series[0]
                missing_before = int(df_result[col].isnull().sum())
                df_result[col] = df_result[col].fillna(fill)
                filled_count += missing_before
        desc = f"众数填充完成，共填充 {filled_count} 个缺失值"
        if invalid_cols:
            desc += f"，{len(invalid_cols)} 列不存在已跳过"

    elif method == 'custom':
        filled_count = 0
        for col in valid_cols:
            missing_before = int(df_result[col].isnull().sum())
            if pd.api.types.is_numeric_dtype(df_result[col]):
                try:
                    val = float(fill_value)
                except ValueError:
                    val = fill_value
            else:
                val = fill_value
            df_result[col] = df_result[col].fillna(val)
            filled_count += missing_before
        desc = f'自定义值 "{fill_value}" 填充完成，共填充 {filled_count} 个缺失值'
        if invalid_cols:
            desc += f"，{len(invalid_cols)} 列不存在已跳过"

    return df_result, desc


# ==================== 异常值检测 ====================

def detect_outliers_iqr(df: pd.DataFrame, columns: list[str],
                         multiplier: float = 1.5) -> dict:
    """
    使用 IQR（四分位距）方法检测异常值
    参数:
        df: DataFrame
        columns: 要检测的数值列
        multiplier: IQR 乘数（默认 1.5）
    返回: 检测结果字典
    """
    results = {
        'method': 'iqr',
        'multiplier': multiplier,
        'columns': {},
        'total_outliers': 0,
        'total_outlier_rows': 0
    }

    outlier_mask = pd.Series(False, index=df.index)

    for col in columns:
        if col not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        col_data = df[col].dropna()
        if len(col_data) < 4:
            continue

        Q1 = col_data.quantile(0.25)
        Q3 = col_data.quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - multiplier * IQR
        upper = Q3 + multiplier * IQR

        outliers_low = df[col] < lower
        outliers_high = df[col] > upper
        col_outliers = outliers_low | outliers_high

        outlier_mask = outlier_mask | col_outliers

        results['columns'][col] = {
            'Q1': round(float(Q1), 4),
            'Q3': round(float(Q3), 4),
            'IQR': round(float(IQR), 4),
            'lower_bound': round(float(lower), 4),
            'upper_bound': round(float(upper), 4),
            'outlier_count': int(col_outliers.sum()),
            'outlier_percent': round(float(col_outliers.sum() / len(df) * 100), 2),
            'outlier_indices': df.index[col_outliers].tolist()
        }
        results['total_outliers'] += int(col_outliers.sum())

    results['total_outlier_rows'] = int(outlier_mask.sum())
    return results


def detect_outliers_zscore(df: pd.DataFrame, columns: list[str],
                            threshold: float = 3.0) -> dict:
    """
    使用 Z-Score 方法检测异常值
    参数:
        df: DataFrame
        columns: 要检测的数值列
        threshold: Z-Score 阈值（默认 3.0）
    返回: 检测结果字典
    """
    results = {
        'method': 'zscore',
        'threshold': threshold,
        'columns': {},
        'total_outliers': 0,
        'total_outlier_rows': 0
    }

    outlier_mask = pd.Series(False, index=df.index)

    for col in columns:
        if col not in df.columns:
            continue
        if not pd.api.types.is_numeric_dtype(df[col]):
            continue

        col_data = df[col].dropna()
        if len(col_data) < 4:
            continue

        mean = col_data.mean()
        std = col_data.std()
        if std == 0:
            continue

        z_scores = np.abs((df[col] - mean) / std)
        col_outliers = z_scores > threshold
        outlier_mask = outlier_mask | col_outliers

        results['columns'][col] = {
            'mean': round(float(mean), 4),
            'std': round(float(std), 4),
            'threshold': threshold,
            'outlier_count': int(col_outliers.sum()),
            'outlier_percent': round(float(col_outliers.sum() / len(df) * 100), 2),
            'outlier_indices': df.index[col_outliers].tolist()
        }
        results['total_outliers'] += int(col_outliers.sum())

    results['total_outlier_rows'] = int(outlier_mask.sum())
    return results


def handle_outliers(df: pd.DataFrame, outlier_indices: list[int]) -> tuple[pd.DataFrame, str]:
    """删除包含异常值的行"""
    df_result = df.copy()
    valid_indices = [i for i in outlier_indices if i in df_result.index]
    if not valid_indices:
        return df_result, "未找到可删除的异常值行"

    before = len(df_result)
    df_result = df_result.drop(index=valid_indices)
    after = len(df_result)
    return df_result, f"已删除 {before - after} 行异常数据"


# ==================== 自动化清洗规则配置（加分项） ====================

@dataclass
class CleaningRule:
    """单条清洗规则"""
    rule_type: str  # 'missing' | 'outlier' | 'remove_duplicates'
    columns: list[str] = field(default_factory=list)
    method: str = ''          # missing: drop/mean/median/mode/custom
    fill_value: str = ''      # custom 填充值
    outlier_method: str = ''  # iqr / zscore
    threshold: float = 0      # IQR multiplier 或 Z-Score threshold
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            rule_type=data.get('rule_type', ''),
            columns=data.get('columns', []),
            method=data.get('method', ''),
            fill_value=data.get('fill_value', ''),
            outlier_method=data.get('outlier_method', ''),
            threshold=data.get('threshold', 0),
            enabled=data.get('enabled', True)
        )


class AutoCleanConfig:
    """自动化清洗规则配置管理器"""

    def __init__(self):
        self.rules: list[CleaningRule] = []
        self.config_name: str = '默认配置'

    def add_rule(self, rule: CleaningRule):
        self.rules.append(rule)

    def remove_rule(self, index: int):
        if 0 <= index < len(self.rules):
            self.rules.pop(index)

    def enable_rule(self, index: int, enabled: bool):
        if 0 <= index < len(self.rules):
            self.rules[index].enabled = enabled

    def get_enabled_rules(self) -> list[CleaningRule]:
        return [r for r in self.rules if r.enabled]

    def execute(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        """按顺序执行所有启用的清洗规则"""
        df_result = df.copy()
        logs = []

        for i, rule in enumerate(self.rules):
            if not rule.enabled:
                continue

            if rule.rule_type == 'missing':
                df_result, desc = handle_missing(
                    df_result,
                    columns=rule.columns if rule.columns else df_result.columns.tolist(),
                    method=rule.method,
                    fill_value=rule.fill_value
                )
                logs.append(f"[规则{i+1}] 缺失值处理: {desc}")

            elif rule.rule_type == 'outlier':
                numeric_cols = (rule.columns if rule.columns
                                else df_result.select_dtypes(include=['number']).columns.tolist())
                if rule.outlier_method == 'iqr':
                    result = detect_outliers_iqr(
                        df_result, numeric_cols,
                        multiplier=rule.threshold if rule.threshold else 1.5
                    )
                else:
                    result = detect_outliers_zscore(
                        df_result, numeric_cols,
                        threshold=rule.threshold if rule.threshold else 3.0
                    )
                all_indices = []
                for col_info in result['columns'].values():
                    all_indices.extend(col_info['outlier_indices'])
                all_indices = list(set(all_indices))
                if all_indices:
                    df_result, desc = handle_outliers(df_result, all_indices)
                    logs.append(f"[规则{i+1}] 异常值处理: {desc}")
                else:
                    logs.append(f"[规则{i+1}] 异常值处理: 未检测到异常值")

            elif rule.rule_type == 'remove_duplicates':
                before = len(df_result)
                df_result = df_result.drop_duplicates()
                after = len(df_result)
                logs.append(f"[规则{i+1}] 去重: 移除 {before - after} 条重复行")

        return df_result, logs

    def to_dict(self) -> dict:
        return {
            'config_name': self.config_name,
            'rules': [r.to_dict() for r in self.rules]
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict):
        config = cls()
        config.config_name = data.get('config_name', '默认配置')
        config.rules = [CleaningRule.from_dict(r) for r in data.get('rules', [])]
        return config

    @classmethod
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def create_preset(cls, preset_name: str = 'standard') -> 'AutoCleanConfig':
        """创建预设清洗配置"""
        config = cls()
        if preset_name == 'standard':
            config.config_name = '标准清洗配置'
            config.rules = [
                CleaningRule(
                    rule_type='missing',
                    columns=[],
                    method='median',
                    enabled=True
                ),
                CleaningRule(
                    rule_type='outlier',
                    columns=[],
                    outlier_method='iqr',
                    threshold=1.5,
                    enabled=True
                ),
                CleaningRule(
                    rule_type='remove_duplicates',
                    enabled=True
                ),
            ]
        elif preset_name == 'strict':
            config.config_name = '严格清洗配置'
            config.rules = [
                CleaningRule(
                    rule_type='missing',
                    columns=[],
                    method='drop',
                    enabled=True
                ),
                CleaningRule(
                    rule_type='outlier',
                    columns=[],
                    outlier_method='zscore',
                    threshold=3.0,
                    enabled=True
                ),
                CleaningRule(
                    rule_type='remove_duplicates',
                    enabled=True
                ),
            ]
        elif preset_name == 'light':
            config.config_name = '轻度清洗配置'
            config.rules = [
                CleaningRule(
                    rule_type='missing',
                    columns=[],
                    method='mode',
                    enabled=True
                ),
                CleaningRule(
                    rule_type='outlier',
                    columns=[],
                    outlier_method='iqr',
                    threshold=3.0,
                    enabled=True
                ),
            ]
        return config
