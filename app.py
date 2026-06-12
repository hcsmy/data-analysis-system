"""
数据管理与分析系统 - 主入口
小组项目：交互式数据分析系统
"""
from modules.ml_analysis import kmeans_cluster, calculate_elbow_value
from modules.data_cleaning import (
    get_missing_info, handle_missing,
    detect_outliers_iqr, detect_outliers_zscore, handle_outliers,
    AutoCleanConfig
)
import os
from flask import Flask, render_template, request, jsonify, send_file
from modules.data_manager import DataManager
from modules.visualization import visualization_bp, init_visualization
from modules.database import database_bp

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-production'
dm = DataManager()
init_visualization(dm)
app.register_blueprint(visualization_bp)
app.register_blueprint(database_bp)

# 数据状态由 DataManager 实例统一管理


@app.route('/')
def index():
    """首页 - 文件上传"""
    return render_template('upload.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传请求"""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未找到上传文件'}), 400

    file = request.files['file']

    # 步骤1：安全保存文件
    filepath, error = dm.save_uploaded_file(file)
    if error:
        return jsonify({'success': False, 'message': error}), 400

    # 步骤2：加载为 DataFrame
    df, error = dm.load_data(filepath)
    if error:
        return jsonify({'success': False, 'message': error}), 400

    # 步骤3：存入 DataManager（供所有模块共享）
    dm.df = df
    dm.filepath = filepath
    dm.filename = file.filename

    # 步骤4：返回摘要信息
    info = dm.get_data_info(df, filepath)
    return jsonify({
        'success': True,
        'message': f'文件 {file.filename} 上传成功',
        'info': info
    })


@app.route('/preview')
def preview():
    """数据预览页"""
    df = dm.df
    if df is None:
        return render_template('preview.html', error='请先上传文件')

    # 分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    total_rows = len(df)
    total_pages = max((total_rows + per_page - 1) // per_page, 1)
    start = (page - 1) * per_page
    end = min(start + per_page, total_rows)

    # 数据表格 HTML
    preview_html = df.iloc[start:end].to_html(
        classes='table table-striped table-hover table-sm',
        index=True,
        na_rep='<span class="text-muted">-</span>',
        escape=False
    )

    # 统计信息
    stats = dm.get_data_info(df, dm.filepath)

    return render_template('preview.html',
                           table=preview_html,
                           stats=stats,
                           page=page,
                           total_pages=total_pages,
                           filename=dm.filename or '未知')


@app.route('/export')
def export_page():
    """导出选择页面"""
    df = dm.df
    if df is None:
        return render_template('export.html', error='请先上传文件')
    return render_template('export.html',
                           filename=dm.filename,
                           columns=df.columns.tolist())


@app.route('/export/download', methods=['POST'])
def export_download():
    """执行数据导出并下载"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '无数据可导出'}), 400

    format_type = request.form.get('format', 'csv')
    base_name = dm.filename.rsplit('.', 1)[0] if dm.filename else 'data'

    filepath, error = dm.export_data(df, format_type, base_name=base_name)
    if error:
        return jsonify({'success': False, 'message': error}), 400

    download_name = f"{base_name}.{format_type}"
    if format_type == 'excel':
        download_name = f"{base_name}.xlsx"

    return send_file(filepath, as_attachment=True, download_name=download_name)
@app.route('/analysis',methods=["GET","POST"])
def analysis():
    # 直接取用项目全局DataManager中已上传的数据，无需path参数
    df = dm.df
    res_data,score,group_cnt,sse_data = None,None,None,None
    # 无数据时页面提示
    if df is None:
        return render_template("analysis.html",error="请先上传数据文件！",table_data=None)
    
    if request.method == "POST":
        # 前端提交K值，默认3
        k = int(request.form.get("k_value", default=3))
        res_df,score,group_cnt = kmeans_cluster(df,k)
        res_data = res_df.to_dict("records")
        sse_data = calculate_elbow_value(df)

    return render_template("analysis.html",
                           table_data=res_data,
                           sil_score=score,
                           group_info=group_cnt,
                           elbow_sse=sse_data)


# ==================== 数据清洗路由 ====================

# 自动化清洗配置（模块级存储，开发模式下跨请求保留）
_auto_clean_config = AutoCleanConfig()


@app.route('/cleaning')
def clean_page():
    """数据清洗页面"""
    df = dm.df
    if df is None:
        return render_template('cleaning.html', error='请先上传文件')

    stats = dm.get_data_info(df, dm.filepath)
    missing = get_missing_info(df)
    columns = df.columns.tolist()
    numeric_columns = df.select_dtypes(include=['number']).columns.tolist()

    return render_template('cleaning.html',
                           stats=stats,
                           missing=missing,
                           columns=columns,
                           numeric_columns=numeric_columns,
                           filename=dm.filename or '未知')


@app.route('/cleaning/missing', methods=['POST'])
def handle_missing_route():
    """处理缺失值"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传文件'}), 400

    data = request.get_json()
    columns = data.get('columns', [])
    method = data.get('method', 'mean')
    fill_value = str(data.get('fill_value', ''))

    # 未选列则默认全部列
    if not columns:
        columns = df.columns.tolist()

    result_df, desc = handle_missing(df, columns, method, fill_value)
    dm.update_data(result_df, desc)

    return jsonify({
        'success': True,
        'message': desc,
        'missing': get_missing_info(result_df)
    })


@app.route('/cleaning/outlier-detect', methods=['POST'])
def detect_outliers_route():
    """检测异常值"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传文件'}), 400

    data = request.get_json()
    columns = data.get('columns', [])
    method = data.get('method', 'iqr')
    threshold = float(data.get('threshold', 1.5))

    if not columns:
        columns = df.select_dtypes(include=['number']).columns.tolist()

    if method == 'zscore':
        result = detect_outliers_zscore(df, columns, threshold)
    else:
        result = detect_outliers_iqr(df, columns, threshold)

    return jsonify({'success': True, 'result': result})


@app.route('/cleaning/outlier-remove', methods=['POST'])
def remove_outliers_route():
    """删除异常值行"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传文件'}), 400

    data = request.get_json()
    indices = data.get('indices', [])

    result_df, desc = handle_outliers(df, indices)
    dm.update_data(result_df, desc)

    return jsonify({'success': True, 'message': desc})


@app.route('/cleaning/duplicates', methods=['POST'])
def remove_duplicates_route():
    """删除重复行"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传文件'}), 400

    before = len(df)
    result_df = df.drop_duplicates()
    after = len(result_df)
    desc = f"已删除 {before - after} 条重复行"

    dm.update_data(result_df, desc)

    return jsonify({'success': True, 'message': desc})


# ==================== 自动化清洗规则配置 ====================

@app.route('/cleaning/auto-config')
def get_auto_config():
    """获取自动化清洗配置"""
    return jsonify({'success': True, 'config': _auto_clean_config.to_dict()})


@app.route('/cleaning/auto-config/save', methods=['POST'])
def save_auto_config():
    """保存自动化清洗配置"""
    global _auto_clean_config
    data = request.get_json()
    if data:
        _auto_clean_config = AutoCleanConfig.from_dict(data)
    return jsonify({'success': True, 'message': '配置已保存'})


@app.route('/cleaning/auto-config/preset', methods=['POST'])
def load_preset_route():
    """加载预设清洗配置"""
    global _auto_clean_config
    data = request.get_json()
    preset = data.get('preset', 'standard')
    _auto_clean_config = AutoCleanConfig.create_preset(preset)
    return jsonify({
        'success': True,
        'message': f'已加载「{_auto_clean_config.config_name}」',
        'config': _auto_clean_config.to_dict()
    })


@app.route('/cleaning/auto-config/execute', methods=['POST'])
def execute_auto_config():
    """执行自动化清洗"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传文件'}), 400

    result_df, logs = _auto_clean_config.execute(df)
    dm.update_data(result_df, '自动化清洗完成')

    return jsonify({
        'success': True,
        'message': '自动化清洗执行完成',
        'logs': logs,
        'missing': get_missing_info(result_df)
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
