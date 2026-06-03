"""
数据管理与分析系统 - 主入口
小组项目：交互式数据分析系统
"""
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)
