"""
数据管理模块
负责：文件上传验证、数据加载、预览、导出
"""
import os
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime


class DataManager:
    """数据管理器 —— 处理文件的完整生命周期，同时作为模块间数据共享的中心"""

    ALLOWED_EXTENSIONS = {'csv', 'xls', 'xlsx'}

    def __init__(self, upload_folder='uploads'):
        self.upload_folder = upload_folder
        os.makedirs(upload_folder, exist_ok=True)
        # ---- 内部状态：当前数据 ----
        self.df = None          # 当前 DataFrame
        self.filepath = None    # 当前文件路径
        self.filename = None    # 当前文件名

    # ==================== 文件上传 ====================

    def allowed_file(self, filename):
        """验证文件扩展名是否在允许列表中"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS

    def save_uploaded_file(self, file):
        """
        安全保存上传文件
        返回: (保存路径, 错误信息) — 成功时错误信息为 None
        """
        if not file or file.filename == '':
            return None, "未选择文件，请先选择一个数据文件"

        if not self.allowed_file(file.filename):
            return None, f"不支持的文件格式。仅支持: {', '.join(self.ALLOWED_EXTENSIONS)}"

        # secure_filename 防止路径穿越攻击
        original_name = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{original_name}"
        filepath = os.path.join(self.upload_folder, filename)

        try:
            file.save(filepath)
            return filepath, None
        except Exception as e:
            return None, f"文件保存失败: {str(e)}"

    # ==================== 数据加载 ====================

    def load_data(self, filepath):
        """
        根据文件扩展名自动选择加载方式
        返回: (DataFrame, 错误信息)
        """
        try:
            ext = filepath.rsplit('.', 1)[1].lower()
            if ext == 'csv':
                df = pd.read_csv(filepath)
            elif ext in ('xls', 'xlsx'):
                df = pd.read_excel(filepath)
            else:
                return None, f"不支持的文件类型: {ext}"
            return df, None
        except Exception as e:
            return None, f"数据加载失败: {str(e)}"

    # ==================== 数据信息 ====================

    def get_data_info(self, df, filepath):
        """获取数据集的基本信息摘要"""
        return {
            'rows': len(df),
            'columns': len(df.columns),
            'column_names': df.columns.tolist(),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'numeric_columns': df.select_dtypes(include=['number']).columns.tolist(),
            'categorical_columns': df.select_dtypes(include=['object']).columns.tolist(),
            'missing_total': int(df.isnull().sum().sum()),
            'missing_percent': round(df.isnull().sum().sum() / (df.shape[0] * df.shape[1]) * 100, 2),
            'duplicates': int(df.duplicated().sum()),
            'memory_usage': f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB",
            'file_size': f"{os.path.getsize(filepath) / 1024:.2f} KB" if os.path.exists(filepath) else "未知",
        }

    # ==================== 数据导出 ====================

    def export_data(self, df, format_type, output_folder='exports', base_name='data'):
        """
        导出数据为指定格式
        返回: (文件路径, 错误信息)
        """
        os.makedirs(output_folder, exist_ok=True)

        try:
            if format_type == 'csv':
                filepath = os.path.join(output_folder, f"{base_name}.csv")
                df.to_csv(filepath, index=False, encoding='utf-8-sig')
                return filepath, None

            elif format_type == 'excel':
                filepath = os.path.join(output_folder, f"{base_name}.xlsx")
                df.to_excel(filepath, index=False, engine='openpyxl')
                return filepath, None

            elif format_type == 'json':
                filepath = os.path.join(output_folder, f"{base_name}.json")
                df.to_json(filepath, orient='records', force_ascii=False, indent=2)
                return filepath, None

            else:
                return None, f"不支持的导出格式: {format_type}"

        except Exception as e:
            return None, f"导出失败: {str(e)}"

    # ==================== 队友调用接口 ====================

    def get_current_data(self):
        """
        【供清洗/可视化/分析模块调用】
        获取当前数据及元信息
        返回: dict，包含 DataFrame、列名、数值列、分类列等
        """
        if self.df is None:
            return {'df': None, 'message': '暂无数据，请先上传文件'}

        return {
            'df': self.df,                              # Pandas DataFrame，供任何模块使用
            'filename': self.filename,                  # 原始文件名
            'columns': self.df.columns.tolist(),        # 全部列名
            'numeric_columns': self.df.select_dtypes(   # 数值列（用于绘图、聚类）
                include=['number']).columns.tolist(),
            'categorical_columns': self.df.select_dtypes(  # 分类列
                include=['object']).columns.tolist(),
            'shape': self.df.shape,                     # (行数, 列数)
            'dtypes': {col: str(dtype) for col, dtype   # 每列数据类型
                       in self.df.dtypes.items()},
        }

    def update_data(self, df, message='数据已更新'):
        """
        【供清洗模块调用】
        接收清洗/处理后的新 DataFrame，替换当前数据
        参数:
            df: 新的 DataFrame
            message: 更新说明
        返回: {'success': True/False, 'message': str}
        """
        if not isinstance(df, pd.DataFrame):
            return {'success': False, 'message': '数据类型错误，需要 pandas DataFrame'}
        self.df = df
        return {'success': True, 'message': message}

    def has_data(self):
        """【供所有模块调用】检查是否有数据"""
        return self.df is not None
