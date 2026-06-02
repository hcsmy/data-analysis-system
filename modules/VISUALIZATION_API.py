"""
================================================================================
  可视化模块 - 接口文档 v1.0
================================================================================

一、文件结构
  modules/visualization.py       -- 核心模块 (Flask Blueprint + VisualizationManager)
  templates/visualization.html   -- 可视化操作页面

二、集成方式（app.py 添加 3 行）
  from modules.visualization import visualization_bp, init_visualization
  init_visualization(dm)
  app.register_blueprint(visualization_bp)

  templates/base.html 导航栏添加:
  <a class="nav-link" href="/visualize">可视化</a>

三、依赖
  requirements.txt 需含:  matplotlib>=3.7, numpy>=1.24

四、VisualizationManager 对外接口

  4.1 get_available_charts(df)
      根据 DataFrame 返回可用图表类型和列信息
      返回: {chart_types: [...], all_columns: [...], numeric_columns: [...], ...}

  4.2 generate_chart(df, chart_type, params)
      生成图表，返回 base64 PNG
      chart_type: bar / line / scatter / histogram / pie / correlation_heatmap
      返回: {success: True/False, image_base64: '...', message: '...'}

五、图表类型及参数

  柱状图 (bar)
    x_column / y_column / title / color / horizontal / data_start / data_count / data_end

  折线图 (line)
    x_column / y_column / title / color / show_markers / data_start / data_count / data_end

  散点图 (scatter)
    x_column / y_column / title / color / point_size

  直方图 (histogram)
    column / bins / title / color / show_kde

  饼图 (pie)
    labels_column / values_column / title / show_percent / data_start / data_count / data_end

  相关性热力图 (correlation_heatmap)
    columns / title

  * data_start/data_count/data_end: 三参数自动互算，任意填两个即可，留空=全部

六、Flask API 路由

  GET  /visualize              页面
  GET  /visualize/options      JSON: 可用图表类型+列信息
  POST /visualize/generate     JSON: 接收 chart_type+params, 返回 image_base64

七、DataManager 已有接口
  dm.df / dm.get_current_data() / dm.has_data() / dm.update_data(df, msg) / dm.filename
"""
print("接口文档已就绪。")
