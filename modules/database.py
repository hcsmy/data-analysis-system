"""
数据库管理模块 (SQLite)
提供数据持久化存储、历史记录、SQL查询功能
"""
import os
import sqlite3
import pandas as pd
from flask import Blueprint, render_template, jsonify, request

# ---- Blueprint ----
database_bp = Blueprint('database', __name__, url_prefix='/database')

# 数据库文件路径
DB_PATH = 'database/data.db'


class DatabaseManager:
    """SQLite 数据库管理器 —— 数据持久化存储"""

    def __init__(self, db_path=DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._ensure_meta_table()

    def _ensure_meta_table(self):
        """创建元数据表，记录每次存储的信息"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS _meta (
                table_name TEXT PRIMARY KEY,
                rows INTEGER,
                columns INTEGER,
                saved_at TEXT DEFAULT (datetime('now', 'localtime')),
                description TEXT
            )
        ''')
        conn.commit()
        conn.close()

    # ==================== 核心操作 ====================

    def save_dataframe(self, df, table_name, description=''):
        """
        将 DataFrame 保存到 SQLite 表
        返回: {'success': True/False, 'message': str}
        """
        if df is None or df.empty:
            return {'success': False, 'message': 'DataFrame 为空，无法保存'}

        try:
            conn = sqlite3.connect(self.db_path)
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            # 更新元数据
            conn.execute('''
                INSERT OR REPLACE INTO _meta (table_name, rows, columns, description)
                VALUES (?, ?, ?, ?)
            ''', (table_name, len(df), len(df.columns), description))
            conn.commit()
            conn.close()
            return {
                'success': True,
                'message': f'已保存到表 [{table_name}]，{len(df)} 行 × {len(df.columns)} 列'
            }
        except Exception as e:
            return {'success': False, 'message': f'保存失败: {str(e)}'}

    def load_dataframe(self, table_name):
        """
        从 SQLite 表加载 DataFrame
        返回: (DataFrame, 错误信息)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql(f"SELECT * FROM [{table_name}]", conn)
            conn.close()
            return df, None
        except Exception as e:
            return None, f'加载失败: {str(e)}'

    def list_tables(self):
        """列出所有已存储的表及元数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            tables = pd.read_sql(
                "SELECT * FROM _meta ORDER BY saved_at DESC", conn
            ).to_dict(orient='records')
            conn.close()
            return tables
        except Exception:
            return []

    def delete_table(self, table_name):
        """删除指定表"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
            conn.execute("DELETE FROM _meta WHERE table_name = ?", (table_name,))
            conn.commit()
            conn.close()
            return {'success': True, 'message': f'表 [{table_name}] 已删除'}
        except Exception as e:
            return {'success': False, 'message': f'删除失败: {str(e)}'}

    def execute_query(self, sql):
        """执行自定义 SQL 查询（仅限 SELECT）"""
        sql_stripped = sql.strip().upper()
        if not sql_stripped.startswith('SELECT'):
            return None, '仅支持 SELECT 查询'

        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql(sql, conn)
            conn.close()
            return df, None
        except Exception as e:
            return None, f'查询失败: {str(e)}'


# 初始化数据库管理器
dbm = DatabaseManager()


# ==================== Flask 路由 ====================

@database_bp.route('/')
def database_page():
    """数据库管理页面"""
    tables = dbm.list_tables()
    return render_template('database.html', tables=tables)


@database_bp.route('/tables')
def get_tables():
    """获取所有表信息 (JSON)"""
    return jsonify({'success': True, 'tables': dbm.list_tables()})


@database_bp.route('/save', methods=['POST'])
def save_current_data():
    """保存当前 DataFrame 到数据库"""
    # 从 DataManager 获取当前数据
    from app import dm
    if not dm.has_data():
        return jsonify({'success': False, 'message': '暂无数据，请先上传文件'}), 400

    table_name = request.form.get('table_name', '')
    description = request.form.get('description', '')

    if not table_name:
        return jsonify({'success': False, 'message': '请输入表名'}), 400

    # 清理表名（只保留字母数字下划线）
    import re
    table_name = re.sub(r'[^\w]', '_', table_name)

    result = dbm.save_dataframe(dm.df, table_name, description)
    return jsonify(result)


@database_bp.route('/load/<table_name>', methods=['POST'])
def load_table(table_name):
    """从数据库加载表，设为当前数据"""
    from app import dm

    df, error = dbm.load_dataframe(table_name)
    if error:
        return jsonify({'success': False, 'message': error}), 400

    dm.df = df
    dm.filename = f'{table_name} (from database)'
    return jsonify({
        'success': True,
        'message': f'已加载表 [{table_name}]，{len(df)} 行 × {len(df.columns)} 列'
    })


@database_bp.route('/table/<table_name>', methods=['DELETE'])
def delete_table(table_name):
    """删除数据库中的表"""
    result = dbm.delete_table(table_name)
    return jsonify(result)


@database_bp.route('/query', methods=['POST'])
def run_query():
    """执行自定义 SQL 查询"""
    sql = request.form.get('sql', '')
    if not sql:
        return jsonify({'success': False, 'message': '请输入 SQL 语句'}), 400

    df, error = dbm.execute_query(sql)
    if error:
        return jsonify({'success': False, 'message': error}), 400

    html = df.to_html(
        classes='table table-striped table-sm',
        index=False,
        na_rep='<span class="text-muted">-</span>',
        escape=False
    )
    return jsonify({
        'success': True,
        'html': html,
        'rows': len(df),
        'columns': len(df.columns)
    })
