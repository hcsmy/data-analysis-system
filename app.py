"""
数据管理与分析系统 - 主入口
小组项目：交互式数据分析系统
"""
import os
from flask import Flask, render_template, request, jsonify, send_file
from modules.data_manager import DataManager
from modules.data_cleaning import (
    get_missing_info, handle_missing,
    detect_outliers_iqr, detect_outliers_zscore, handle_outliers,
    CleaningRule, AutoCleanConfig
)

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-in-production'
dm = DataManager()
# 自动化清洗配置（存储在 DataManager 上）
dm.auto_config = AutoCleanConfig()

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


# ==================== 数据清洗模块 ====================

@app.route('/cleaning')
def cleaning_page():
    """数据清洗页面入口"""
    df = dm.df
    if df is None:
        return render_template('cleaning.html', error='请先上传文件')

    missing = get_missing_info(df)
    return render_template('cleaning.html',
                           filename=dm.filename,
                           columns=df.columns.tolist(),
                           numeric_columns=df.select_dtypes(include=['number']).columns.tolist(),
                           missing=missing,
                           auto_config=dm.auto_config)


@app.route('/cleaning/missing', methods=['POST'])
def cleaning_missing():
    """执行缺失值处理"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传数据文件'})

    data = request.get_json()
    columns = data.get('columns', [])
    method = data.get('method', 'mean')
    fill_value = data.get('fill_value', '')

    if not columns:
        return jsonify({'success': False, 'message': '请选择需要处理的列'})

    df_new, desc = handle_missing(df, columns, method, fill_value)
    dm.update_data(df_new, desc)

    missing = get_missing_info(df_new)
    return jsonify({'success': True, 'message': desc, 'missing': missing})


@app.route('/cleaning/outlier-detect', methods=['POST'])
def cleaning_outlier_detect():
    """执行异常值检测（仅检测，不删除）"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传数据文件'})

    data = request.get_json()
    columns = data.get('columns', [])
    method = data.get('method', 'iqr')
    threshold = data.get('threshold', 1.5)

    if not columns:
        return jsonify({'success': False, 'message': '请选择需要检测的列'})

    if method == 'iqr':
        result = detect_outliers_iqr(df, columns, multiplier=float(threshold))
    else:
        result = detect_outliers_zscore(df, columns, threshold=float(threshold))

    return jsonify({'success': True, 'result': result})


@app.route('/cleaning/outlier-remove', methods=['POST'])
def cleaning_outlier_remove():
    """删除检测到的异常值行"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传数据文件'})

    data = request.get_json()
    indices = data.get('indices', [])

    df_new, desc = handle_outliers(df, indices)
    dm.update_data(df_new, desc)

    return jsonify({'success': True, 'message': desc})


@app.route('/cleaning/duplicates', methods=['POST'])
def cleaning_duplicates():
    """删除重复行"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传数据文件'})

    before = len(df)
    df_new = df.drop_duplicates()
    after = len(df_new)

    if before == after:
        return jsonify({'success': True, 'message': '未发现重复行'})

    dm.update_data(df_new, f'移除 {before - after} 条重复行')
    return jsonify({'success': True, 'message': f'已移除 {before - after} 条重复行'})


# ==================== 自动化清洗规则配置 ====================

@app.route('/cleaning/auto-config', methods=['GET'])
def cleaning_get_config():
    """获取当前自动化清洗配置"""
    return jsonify({'success': True, 'config': dm.auto_config.to_dict()})


@app.route('/cleaning/auto-config/save', methods=['POST'])
def cleaning_save_config():
    """保存自动化清洗配置"""
    data = request.get_json()
    dm.auto_config = AutoCleanConfig.from_dict(data)
    return jsonify({'success': True, 'message': '配置已保存'})


@app.route('/cleaning/auto-config/preset', methods=['POST'])
def cleaning_load_preset():
    """加载预设配置"""
    data = request.get_json()
    preset = data.get('preset', 'standard')
    dm.auto_config = AutoCleanConfig.create_preset(preset)
    return jsonify({'success': True, 'config': dm.auto_config.to_dict(),
                     'message': f'已加载预设: {preset}'})


@app.route('/cleaning/auto-config/execute', methods=['POST'])
def cleaning_execute_auto():
    """执行自动化清洗配置"""
    df = dm.df
    if df is None:
        return jsonify({'success': False, 'message': '请先上传数据文件'})

    df_new, logs = dm.auto_config.execute(df)
    dm.update_data(df_new, '自动化清洗完成')

    missing = get_missing_info(df_new)
    return jsonify({'success': True, 'message': '自动化清洗完成',
                     'logs': logs, 'missing': missing})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
