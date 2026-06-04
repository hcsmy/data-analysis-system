"""
可视化模块
负责：图表生成、可视化页面路由、图表参数配置
==============================================
【集成说明】在 app.py 中添加以下代码即可：
    from modules. Visualization import visualization_bp, init_visualization
    init_visualization(dm)
    app.register_blueprint(visualization_bp)

【供分析/清洗模块调用接口】
    from modules. Visualization import VisualizationManager
    vm = VisualizationManager()
    chart_base64 = vm.generate_chart(df, chart_type, params)
    chart_options = vm.get_available_charts(df)
"""
import io
import base64
import warnings
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from flask import Blueprint, render_template, request, jsonify, current_app

warnings.filterwarnings('ignore', category=UserWarning)

# ==================== 中文字体配置 ====================

def _setup_chinese_font():
    """配置 matplotlib 中文字体，返回字体名称"""
    import os
    from matplotlib import font_manager

    font_dir = os.path.join(os.environ.get('WINDIR', os.path.join('C:', 'Windows', 'Fonts')))
    candidates = [
        os.path.join(font_dir, 'msyh.ttc'),
        os.path.join(font_dir, 'msyhbd.ttc'),
        os.path.join(font_dir, 'simhei.ttf'),
        os.path.join(font_dir, 'simsun.ttc'),
        os.path.join(font_dir, 'simkai.ttf'),
    ]

    font_path = None
    for fp in candidates:
        if os.path.exists(fp):
            font_path = fp
            break

    if font_path:
        font_manager.fontManager.addfont(font_path)
        prop = font_manager.FontProperties(fname=font_path)
        return prop.get_name()

    return 'SimHei'


_CHINESE_FONT = _setup_chinese_font()


def _apply_chinese_font():
    """每次画图前调用，确保 rcParams 中方字体生效（因为 plt.style.use 会重置）"""
    plt.rcParams['font.sans-serif'] = [_CHINESE_FONT, 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

# ==================== 图表配色方案 ====================

COLOR_PALETTES = {
    'default':  ['#4C72B0', '#DD8452', '#55A868', '#C44E52', '#8172B3',
                 '#937860', '#DA8BC3', '#8C8C8C', '#CCB974', '#64B5CD'],
    'pastel':   ['#A1C9F4', '#FFB482', '#8DE5A1', '#FF9F9B', '#D0BBFF',
                 '#DEBB9B', '#FAB0E4', '#CFCFCF', '#FFEA6D', '#B9E6F8'],
    'vivid':    ['#023EFF', '#FF7C00', '#1AC938', '#E8000B', '#8B2BE2',
                 '#9F4800', '#F14CC1', '#A3A3A3', '#FFC400', '#00D7FF'],
}

# ==================== 图表类型定义 ====================

CHART_TYPES = {
    'bar': {
        'name': '柱状图',
        'icon': '📊',
        'description': '展示分类数据的数值对比',
        'requires': {'x': 'any', 'y': 'numeric'},
        'params': ['x_column', 'y_column', 'title', 'color', 'horizontal', 'data_start', 'data_count', 'data_end'],
    },
    'line': {
        'name': '折线图',
        'icon': '📈',
        'description': '展示数据随时间或顺序的变化趋势',
        'requires': {'x': 'any', 'y': 'numeric'},
        'params': ['x_column', 'y_column', 'title', 'color', 'show_markers', 'data_start', 'data_count', 'data_end'],
    },
    'scatter': {
        'name': '散点图',
        'icon': '🔵',
        'description': '展示两个数值变量之间的关系',
        'requires': {'x': 'numeric', 'y': 'numeric'},
        'params': ['x_column', 'y_column', 'title', 'color', 'point_size'],
    },
    'histogram': {
        'name': '直方图',
        'icon': '📶',
        'description': '展示单个数值变量的分布情况',
        'requires': {'column': 'numeric'},
        'params': ['column', 'bins', 'title', 'color', 'show_kde'],
    },
    'pie': {
        'name': '饼图',
        'icon': '🥧',
        'description': '展示各部分在整体中的占比',
        'requires': {'labels': 'categorical', 'values': 'numeric'},
        'params': ['labels_column', 'values_column', 'title', 'show_percent', 'data_start', 'data_count', 'data_end'],
    },
    'correlation_heatmap': {
        'name': '相关性热力图',
        'icon': '🔥',
        'description': '展示数值列之间的相关性矩阵',
        'requires': {'columns': 'numeric'},
        'params': ['columns', 'title'],
    },
}


class VisualizationManager:
    """图表生成管理器 —— 独立于 Flask，可被任何模块直接调用"""

    def __init__(self):
        self.dpi = 120
        self.figsize = (10, 6)
        self.color_palette = COLOR_PALETTES['default']

    def get_available_charts(self, df):
        """
        【供所有模块调用】根据 DataFrame 结构返回可用的图表类型及可选列
        """
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(
            include=['object', 'category']).columns.tolist()
        datetime_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        all_cols = df.columns.tolist()

        available = []
        for ctype, info in CHART_TYPES.items():
            req = info['requires']
            ok, _ = self._check_requirements(df, req)
            if ok:
                entry = {
                    'type': ctype,
                    'name': info['name'],
                    'icon': info['icon'],
                    'description': info['description'],
                    'params': info['params'],
                }
                if ctype == 'correlation_heatmap':
                    entry['column_options'] = numeric_cols if len(numeric_cols) >= 2 else []
                available.append(entry)

        return {
            'chart_types': available,
            'all_columns': all_cols,
            'numeric_columns': numeric_cols,
            'categorical_columns': categorical_cols,
            'datetime_columns': datetime_cols,
        }

    def generate_chart(self, df, chart_type, params=None):
        """
        【供所有模块调用】核心图表生成入口
        """
        if df is None or df.empty:
            return {'success': False, 'message': '数据为空，无法生成图表'}

        if chart_type not in CHART_TYPES:
            return {'success': False, 'message': f'不支持的图表类型: {chart_type}'}

        params = params or {}
        req = CHART_TYPES[chart_type]['requires']
        ok, missing = self._check_requirements(df, req)
        if not ok:
            return {'success': False, 'message': f'数据不满足图表要求: {missing}'}

        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except Exception:
            try:
                plt.style.use('ggplot')
            except Exception:
                pass

        _apply_chinese_font()

        try:
            fig = None
            if chart_type == 'bar':
                fig = self._draw_bar(df, params)
            elif chart_type == 'line':
                fig = self._draw_line(df, params)
            elif chart_type == 'scatter':
                fig = self._draw_scatter(df, params)
            elif chart_type == 'histogram':
                fig = self._draw_histogram(df, params)
            elif chart_type == 'pie':
                fig = self._draw_pie(df, params)
            elif chart_type == 'correlation_heatmap':
                fig = self._draw_heatmap(df, params)

            image_b64 = self._fig_to_base64(fig)
            plt.close(fig)
            return {'success': True, 'image_base64': image_b64}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'message': f'图表生成失败: {str(e)}'}

    def _draw_bar(self, df, params):
        x_col = params.get('x_column', df.columns[0])
        y_col = params.get('y_column', self._find_numeric(df)[0])
        horizontal = params.get('horizontal', 'false') == 'true'

        data = df[[x_col, y_col]].dropna().copy()
        data = data.groupby(x_col)[y_col].sum().reset_index()
        data.sort_values(y_col, ascending=False, inplace=True)
        data = self._slice_data(data, params)

        fig, ax = plt.subplots(figsize=self.figsize)
        palette = self._get_palette(params)
        bars = ax.barh(data[x_col].astype(str), data[y_col], color=palette[0], alpha=0.85) \
            if horizontal else \
            ax.bar(data[x_col].astype(str), data[y_col], color=palette[0], alpha=0.85)

        if horizontal:
            ax.invert_yaxis()

        self._add_labels_to_bars(ax, bars, horizontal)
        ax.set_title(params.get('title', f'{y_col} 柱状图'), fontsize=14, fontweight='bold')
        ax.set_ylabel(x_col if horizontal else y_col)
        ax.set_xlabel(y_col if horizontal else x_col)
        self._finalize_axes(ax, data, horizontal)
        plt.tight_layout()
        return fig

    def _draw_line(self, df, params):
        x_col = params.get('x_column', df.columns[0])
        y_col = params.get('y_column', self._find_numeric(df)[0])
        show_markers = params.get('show_markers', 'true') == 'true'

        data = df[[x_col, y_col]].dropna().copy()
        data = self._slice_data(data, params)
        color = self._get_color(params, 0)

        fig, ax = plt.subplots(figsize=self.figsize)
        marker = 'o' if show_markers else None
        ax.plot(data[x_col].astype(str) if data[x_col].dtype == 'object'
                else data[x_col], data[y_col],
                color=color, marker=marker, linewidth=2, markersize=5)

        ax.fill_between(range(len(data)), data[y_col], alpha=0.1, color=color)

        ax.set_title(params.get('title', f'{y_col} 趋势图'), fontsize=14, fontweight='bold')
        self._finalize_axes(ax, data)
        plt.tight_layout()
        return fig

    def _draw_scatter(self, df, params):
        x_col = params.get('x_column', self._find_numeric(df)[0])
        y_col = params.get('y_column', self._find_numeric(df)[-1])
        point_size = int(params.get('point_size', 40))

        data = df[[x_col, y_col]].dropna()
        color = self._get_color(params, 0)

        fig, ax = plt.subplots(figsize=self.figsize)
        ax.scatter(data[x_col], data[y_col], s=point_size, c=color,
                   alpha=0.6, edgecolors='white', linewidth=0.5)

        if len(data) > 2:
            try:
                z = np.polyfit(data[x_col], data[y_col], 1)
                p = np.poly1d(z)
                x_range = np.linspace(data[x_col].min(), data[x_col].max(), 100)
                ax.plot(x_range, p(x_range), '--', color='red',
                        alpha=0.6, linewidth=1.5, label='趋势线')
                ax.legend()
            except Exception:
                pass

        ax.set_title(params.get('title', f'{x_col} vs {y_col} 散点图'),
                     fontsize=14, fontweight='bold')
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        self._finalize_axes(ax, data)
        plt.tight_layout()
        return fig

    def _draw_histogram(self, df, params):
        column = params.get('column', self._find_numeric(df)[0])
        bins = int(params.get('bins', 20))
        show_kde = params.get('show_kde', 'false') == 'true'

        data = df[column].dropna()
        color = self._get_color(params, 0)

        fig, ax = plt.subplots(figsize=self.figsize)
        ax.hist(data, bins=bins, color=color,
                alpha=0.75, edgecolor='white', linewidth=0.5)

        if show_kde and len(data) > 1:
            try:
                from scipy.stats import gaussian_kde
            except ImportError:
                pass
            else:
                kde = gaussian_kde(data)
                x_kde = np.linspace(data.min(), data.max(), 200)
                ax2 = ax.twinx()
                ax2.plot(x_kde, kde(x_kde), color='red', linewidth=2, label='KDE')
                ax2.set_ylabel('密度', color='red')
                ax2.legend(loc='upper right')

        ax.set_title(params.get('title', f'{column} 分布直方图'),
                     fontsize=14, fontweight='bold')
        ax.set_xlabel(column)
        ax.set_ylabel('频数')
        self._finalize_axes(ax, data)
        plt.tight_layout()
        return fig

    def _draw_pie(self, df, params):
        labels_col = params.get('labels_column', df.select_dtypes(
            include=['object']).columns[0] if len(df.select_dtypes(
            include=['object']).columns) > 0 else df.columns[0])
        values_col = params.get('values_column', self._find_numeric(df)[0])
        show_percent = params.get('show_percent', 'true') == 'true'

        data = df[[labels_col, values_col]].dropna().copy()
        data = data.groupby(labels_col)[values_col].sum().reset_index()
        data.sort_values(values_col, ascending=False, inplace=True)

        data = self._slice_data(data, params)

        total_sliced = data[values_col].sum()
        total_all = df[values_col].dropna().sum()
        other_value = total_all - total_sliced
        if other_value > 0.001 * total_all and other_value > 0:
            data = pd.concat([data, pd.DataFrame(
                {labels_col: ['其他'], values_col: [other_value]}
            )], ignore_index=True)

        palette = self._get_palette(params)
        colors = palette[:len(data)] * (len(data) // len(palette) + 1)

        fig, ax = plt.subplots(figsize=(9, 7))
        autopct = '%1.1f%%' if show_percent else None
        ax.pie(data[values_col], labels=data[labels_col], autopct=autopct,
               colors=colors, startangle=90, pctdistance=0.75,
               wedgeprops={'edgecolor': 'white', 'linewidth': 1})

        ax.set_title(params.get('title', f'{values_col} 占比饼图'),
                     fontsize=14, fontweight='bold')
        plt.tight_layout()
        return fig

    def _draw_heatmap(self, df, params):
        cols_str = params.get('columns', '')
        if cols_str:
            columns = [c.strip() for c in cols_str.split(',')]
        else:
            columns = self._find_numeric(df)

        data = df[columns].select_dtypes(include=['number'])
        if data.shape[1] < 2:
            raise ValueError('至少需要两个数值列才能生成热力图')

        corr = data.corr()

        fig, ax = plt.subplots(figsize=(10, 8))
        im = ax.imshow(corr, cmap='RdYlBu_r', aspect='auto', vmin=-1, vmax=1)

        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha='right', fontsize=10)
        ax.set_yticklabels(corr.columns, fontsize=10)

        for i in range(len(corr.columns)):
            for j in range(len(corr.columns)):
                ax.text(j, i, f'{corr.iloc[i, j]:.2f}',
                        ha='center', va='center',
                        fontsize=10, fontweight='bold',
                        color='white' if abs(corr.iloc[i, j]) > 0.6 else 'black')

        cbar = plt.colorbar(im, ax=ax, shrink=0.8)
        cbar.set_label('相关系数', fontsize=11)

        ax.set_title(params.get('title', '相关性矩阵热力图'),
                     fontsize=14, fontweight='bold')
        plt.tight_layout()
        return fig

    def _check_requirements(self, df, req):
        numeric = df.select_dtypes(include=['number']).columns.tolist()
        categorical = df.select_dtypes(include=['object', 'category']).columns.tolist()

        for axis, requirement in req.items():
            cols = self._resolve_axis(axis, numeric, categorical)
            if requirement == 'numeric' and not cols:
                return False, f'缺少数值类型列'
            if requirement == 'categorical' and not categorical:
                return False, f'缺少分类类型列'
            if not cols:
                return False, f'没有可用列'
        return True, None

    def _resolve_axis(self, axis, numeric, categorical):
        m = {
            'x': ['any'],
            'y': numeric,
            'column': numeric,
            'columns': numeric,
            'labels': categorical,
            'values': numeric,
        }
        return m.get(axis, numeric)

    def _find_numeric(self, df):
        return df.select_dtypes(include=['number']).columns.tolist()

    def _get_color(self, params, idx=0):
        color_name = params.get('color', '')
        if color_name:
            return color_name
        return self.color_palette[idx % len(self.color_palette)]

    def _get_palette(self, params):
        palette_name = params.get('palette', 'default')
        return COLOR_PALETTES.get(palette_name, COLOR_PALETTES['default'])

    def _fig_to_base64(self, fig):
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight',
                     facecolor='white', edgecolor='none')
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode('utf-8')
        buf.close()
        return f'data:image/png;base64,{img_b64}'

    def _add_labels_to_bars(self, ax, bars, horizontal=False):
        for bar in bars:
            if horizontal:
                width = bar.get_width()
                ax.text(width + (width * 0.01), bar.get_y() + bar.get_height() / 2,
                        f'{width:.0f}', va='center', fontsize=8)
            else:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width() / 2, height + (height * 0.01),
                        f'{height:.0f}', ha='center', fontsize=8)

    def _slice_data(self, data, params):
        """根据 data_start / data_end / data_count 对数据切片，任意填两个即可"""
        raw_start = params.get('data_start', '')
        raw_count = params.get('data_count', '')
        raw_end = params.get('data_end', '')
        has_start = raw_start != ''
        has_count = raw_count != ''
        has_end = raw_end != ''

        if not has_start and not has_count and not has_end:
            return data

        total = len(data)
        start = int(raw_start) if has_start else 1
        end = int(raw_end) if has_end else total
        count = int(raw_count) if has_count else total

        if not has_start:
            start = end - count + 1
        elif not has_end:
            end = start + count - 1

        start = max(1, min(start, total))
        end = max(start, min(end, total))
        return data.iloc[start - 1:end]

    def _finalize_axes(self, ax, data, horizontal=False):
        if horizontal and data is not None:
            return
        if data is not None and len(data) > 15:
            ax.tick_params(axis='x', rotation=45, labelsize=8)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)


# ==================== Flask Blueprint ====================

visualization_bp = Blueprint('visualization', __name__, template_folder='../templates')

_data_manager = None


def init_visualization(data_manager):
    global _data_manager
    _data_manager = data_manager


def _get_df():
    if _data_manager is None:
        return None
    if not _data_manager.has_data():
        return None
    return _data_manager.df


@visualization_bp.route('/visualize')
def visualize_page():
    df = _get_df()
    if df is None:
        return render_template('visualization.html', error='请先上传数据文件')
    return render_template('visualization.html', filename=_data_manager.filename)


@visualization_bp.route('/visualize/options')
def chart_options():
    df = _get_df()
    if df is None:
        return jsonify({'success': False, 'message': '请先上传数据文件'}), 400

    vm = VisualizationManager()
    options = vm.get_available_charts(df)
    options['success'] = True
    return jsonify(options)


@visualization_bp.route('/visualize/generate', methods=['POST'])
def generate_chart():
    df = _get_df()
    if df is None:
        return jsonify({'success': False, 'message': '请先上传数据文件'}), 400

    data = request.get_json() or {}
    chart_type = data.get('chart_type', 'bar')
    params = data.get('params', {})

    vm = VisualizationManager()
    result = vm.generate_chart(df, chart_type, params)
    return jsonify(result)
