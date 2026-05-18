"""
KnowFlow Dashboard Generator
Generate a beautiful, mobile-friendly HTML dashboard from knowledge data.
"""
import json
import re
import os
from pathlib import Path
from datetime import datetime
from html import escape


def _read_md(filepath):
    """Read a markdown file and return its content."""
    try:
        return Path(filepath).read_text(encoding='utf-8')
    except (FileNotFoundError, IOError):
        return None


def _parse_table(md_text):
    """Parse a markdown table into list of dicts."""
    lines = md_text.strip().split('\n')
    if len(lines) < 3:
        return []
    headers = [h.strip() for h in lines[0].split('|')[1:-1]]
    rows = []
    for line in lines[2:]:  # skip header and separator
        cols = [c.strip() for c in line.split('|')[1:-1]]
        if len(cols) == len(headers):
            rows.append(dict(zip(headers, cols)))
    return rows


def _parse_key_value(md_text):
    """Parse key-value pairs from markdown (lines like '- **Key**: Value')."""
    result = {}
    for m in re.finditer(r'-\s+\*\*(.+?)\*\*:\s*(.+)', md_text):
        result[m.group(1).strip()] = m.group(2).strip()
    return result


class DashboardGenerator:
    """Generate a static HTML dashboard from knowledge data."""

    def __init__(self, knowledge_dir, output_dir=None, password=None):
        self.knowledge_dir = Path(knowledge_dir)
        self.output_dir = Path(output_dir or knowledge_dir / 'dashboard')
        self.password = password
        self.data = {}

    def collect(self):
        """Collect all data from the knowledge directory."""
        obsidian_dir = self.knowledge_dir / 'obsidian'
        output_dir = self.knowledge_dir / 'output'

        # Football predictions
        football_dir = output_dir / 'football' / 'predictions'
        football_files = sorted(football_dir.glob('*.md')) if football_dir.exists() else []
        football_data = []
        for f in football_files[-5:]:  # last 5
            content = _read_md(f)
            if content:
                kv = _parse_key_value(content)
                tables = re.findall(r'## Matches\n\n(.*?)(?=\n\n|$)', content, re.DOTALL)
                matches = _parse_table(tables[0]) if tables else []
                football_data.append({
                    'date': kv.get('Date', f.stem),
                    'file': f.name,
                    'matches': matches,
                })

        # Football learnings
        learnings_md = _read_md(output_dir / 'football' / 'learnings.md') or \
                       _read_md(obsidian_dir / 'football' / 'learnings.md')

        # Stock analysis
        stock_base = output_dir / 'stock' / 'daily'
        stock_dates = sorted([d for d in stock_base.iterdir() if d.is_dir()]) if stock_base.exists() else []
        stock_data = {}
        if stock_dates:
            latest = stock_dates[-1]
            for f in latest.glob('*.md'):
                content = _read_md(f)
                if content:
                    kv = _parse_key_value(content)
                    tables = re.findall(r'## (.*?)\n\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
                    stock_data[f.stem] = {'meta': kv, 'sections': tables}

        # Stock portfolio
        portfolio_md = _read_md(output_dir / 'stock' / 'portfolio' / 'portfolio_million.md') or \
                       _read_md(output_dir / 'stock' / 'portfolio' / 'simulated_portfolio.md')

        # Worldcup
        worldcup_md = _read_md(output_dir / 'worldcup' / 'squads.md') or \
                      _read_md(obsidian_dir / 'worldcup' / 'squads.md')
        worldcup_teams = []
        if worldcup_md:
            tables = re.findall(r'## Teams\n\n(.*?)(?=\n\n|$)', worldcup_md, re.DOTALL)
            worldcup_teams = _parse_table(tables[0]) if tables else []

        # Count all files
        total_files = sum(1 for _ in self.knowledge_dir.rglob('*') if _.is_file() and '.git' not in str(_))

        self.data = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'football': {
                'predictions': football_data,
                'learnings': learnings_md,
            },
            'stock': {
                'latest_date': stock_dates[-1].name if stock_dates else None,
                'files': stock_data,
            },
            'worldcup': {
                'teams': worldcup_teams,
            },
            'stats': {
                'total_files': total_files,
                'football_matches': sum(len(p['matches']) for p in football_data),
                'worldcup_teams': len(worldcup_teams),
                'stock_strategies': len(stock_data),
            }
        }
        return self.data

    def generate_html(self):
        """Generate the HTML dashboard."""
        d = self.data

        # Build football matches table
        football_html = ''
        for pred in d['football']['predictions']:
            if pred['matches']:
                football_html += f'<h4>📅 {escape(pred["date"])}</h4>\n'
                football_html += '<table><thead><tr><th>对阵</th><th>预测</th><th>置信度</th><th>比分</th></tr></thead><tbody>\n'
                for m in pred['matches']:
                    teams = escape(m.get('Match', ''))
                    prediction = escape(m.get('Prediction', ''))
                    confidence = escape(m.get('Confidence', ''))
                    score = escape(m.get('Predicted Score', ''))
                    football_html += f'<tr><td>{teams}</td><td>{prediction}</td><td>{confidence}%</td><td>{score}</td></tr>\n'
                football_html += '</tbody></table>\n'

        # Build worldcup table
        wc_html = ''
        if d['worldcup']['teams']:
            wc_html = '<table><thead><tr><th>球队</th><th>分组</th><th>人数</th><th>公布时间</th></tr></thead><tbody>\n'
            for t in d['worldcup']['teams']:
                name = escape(t.get('Name Cn', t.get('Name En', '')))
                group = escape(t.get('Group', ''))
                size = escape(t.get('Squad Size', ''))
                announced = escape(t.get('Announced At', ''))
                wc_html += f'<tr><td>{name}</td><td>{group}</td><td>{size}</td><td>{announced}</td></tr>\n'
            wc_html += '</tbody></table>\n'

        # Build stock summary
        stock_html = ''
        for fname, fdata in d['stock']['files'].items():
            meta = fdata.get('meta', {})
            idx_px = meta.get('Price', '')
            idx_chg = meta.get('Change Pct', '')
            is_pos = idx_chg and float(idx_chg) >= 0
            stock_html += f'<div class="stock-card">\n'
            stock_html += f'  <h4>{escape(fname.replace("_", " ").title())}</h4>\n'
            if idx_px:
                cls = 'pos' if is_pos else 'neg'
                stock_html += f'  <p>点位: <strong>{escape(idx_px)}</strong> <span class="{cls}">{escape(idx_chg)}%</span></p>\n'
            stock_html += '</div>\n'

        # Build the full HTML
        now = d['generated_at']
        total_matches = d['stats']['football_matches']
        total_teams = d['stats']['worldcup_teams']
        total_strats = d['stats']['stock_strategies']
        total_files = d['stats']['total_files']

        # Password protection
        password_guard = ''
        if self.password:
            password_guard = f'''
<div id="password-overlay" style="position:fixed;top:0;left:0;right:0;bottom:0;background:#0f1117;z-index:9999;display:flex;align-items:center;justify-content:center;">
<div style="background:#161b22;border:1px solid #30363d;border-radius:16px;padding:40px;width:90%;max-width:380px;text-align:center;">
<div style="font-size:3em;margin-bottom:16px;">🔐</div>
<h2 style="color:#f0f6fc;margin-bottom:8px;">KnowFlow</h2>
<p style="color:#8b949e;font-size:0.9em;margin-bottom:24px;">请输入密码查看仪表盘</p>
<input id="pwd-input" type="password" placeholder="密码" style="width:100%;padding:12px 16px;background:#0f1117;border:1px solid #30363d;border-radius:8px;color:#e1e4e8;font-size:1em;outline:none;margin-bottom:12px;box-sizing:border-box;" onkeydown="if(event.key==='Enter')checkPwd()">
<button onclick="checkPwd()" style="width:100%;padding:12px;background:#238636;border:none;border-radius:8px;color:#fff;font-size:1em;cursor:pointer;font-weight:600;">进入</button>
<p id="pwd-error" style="color:#f85149;font-size:0.85em;margin-top:12px;display:none;">密码错误，请重试</p>
</div>
</div>
<script>
var _pwd = {json.dumps(self.password)};
function checkPwd() {{
    var v = document.getElementById('pwd-input').value;
    if (v === _pwd) {{
        document.getElementById('password-overlay').style.display = 'none';
        document.getElementById('dashboard-content').style.display = 'block';
    }} else {{
        document.getElementById('pwd-error').style.display = 'block';
    }}
}}
document.addEventListener('DOMContentLoaded', function() {{
    document.getElementById('password-overlay').style.display = 'flex';
    document.getElementById('dashboard-content').style.display = 'none';
    document.getElementById('pwd-input').focus();
}});
</script>'''

        html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>KnowFlow Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f1117;
    color: #e1e4e8;
    min-height: 100vh;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
.header {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 20px 0; border-bottom: 1px solid #21262d; margin-bottom: 24px;
    flex-wrap: wrap; gap: 12px;
}}
.header h1 {{ font-size: 1.6em; background: linear-gradient(135deg, #58a6ff, #bc8cff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
.header .sub {{ color: #8b949e; font-size: 0.85em; }}
.stats-row {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px; margin-bottom: 24px;
}}
.stat-card {{
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 20px; text-align: center;
}}
.stat-card .num {{ font-size: 2em; font-weight: 700; color: #58a6ff; }}
.stat-card .label {{ color: #8b949e; font-size: 0.85em; margin-top: 4px; }}
.section {{
    background: #161b22; border: 1px solid #30363d; border-radius: 12px;
    padding: 24px; margin-bottom: 20px;
}}
.section h2 {{ font-size: 1.2em; margin-bottom: 16px; color: #f0f6fc; }}
.section h2 .icon {{ margin-right: 8px; }}
.section h3 {{ font-size: 1em; color: #58a6ff; margin: 16px 0 8px; }}
.section h4 {{ font-size: 0.9em; color: #c9d1d9; margin: 12px 0 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
th {{ text-align: left; padding: 8px; border-bottom: 2px solid #30363d; color: #8b949e; font-weight: 600; }}
td {{ padding: 8px; border-bottom: 1px solid #21262d; }}
tr:hover td {{ background: #1c2128; }}
.pos {{ color: #3fb950; }}
.neg {{ color: #f85149; }}
.stock-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
.stock-card {{
    background: #1c2128; border: 1px solid #30363d; border-radius: 8px;
    padding: 14px; font-size: 0.85em;
}}
.stock-card h4 {{ margin-bottom: 8px; }}
.empty {{ color: #8b949e; font-style: italic; text-align: center; padding: 20px; }}
.footer {{
    text-align: center; padding: 20px; color: #484f58;
    font-size: 0.8em; border-top: 1px solid #21262d; margin-top: 20px;
}}
@media (max-width: 600px) {{
    .container {{ padding: 12px; }}
    .header h1 {{ font-size: 1.2em; }}
    .stat-card .num {{ font-size: 1.4em; }}
    .section {{ padding: 16px; }}
    table {{ font-size: 0.78em; }}
    th, td {{ padding: 5px; }}
}}
</style>
</head>
{password_guard}
<div id="dashboard-content">
<div class="container">
    <div class="header">
        <div>
            <h1>🧠 KnowFlow</h1>
            <div class="sub">Agent Knowledge Dashboard</div>
        </div>
        <div class="sub">🔄 {escape(now)}</div>
    </div>

    <div class="stats-row">
        <div class="stat-card"><div class="num">{total_matches}</div><div class="label">⚽ 足球预测</div></div>
        <div class="stat-card"><div class="num">{total_teams}</div><div class="label">🏆 世界杯球队</div></div>
        <div class="stat-card"><div class="num">{total_strats}</div><div class="label">📈 股票策略</div></div>
        <div class="stat-card"><div class="num">{total_files}</div><div class="label">📁 知识库文件</div></div>
    </div>
'''

        # Football section
        html += '<div class="section">\n<h2><span class="icon">⚽</span>足球预测</h2>\n'
        if football_html:
            html += football_html
        else:
            html += '<div class="empty">暂无足球预测数据</div>\n'
        html += '</div>\n'

        # Worldcup section
        html += '<div class="section">\n<h2><span class="icon">🏆</span>世界杯名单</h2>\n'
        if wc_html:
            html += wc_html
        else:
            html += '<div class="empty">暂无球队数据</div>\n'
        html += '</div>\n'

        # Stock section
        html += '<div class="section">\n<h2><span class="icon">📈</span>股票分析</h2>\n'
        if stock_html:
            stock_date = escape(d['stock']['latest_date'] or '')
            html += f'<h3>📅 {stock_date}</h3>\n<div class="stock-grid">\n{stock_html}</div>\n'
        else:
            html += '<div class="empty">暂无股票分析数据</div>\n'
        html += '</div>\n'

        # System status
        html += f'''<div class="section">
<h2><span class="icon">🔧</span>系统状态</h2>
<table>
<tr><td>知识库位置</td><td>{escape(str(self.knowledge_dir))}</td></tr>
<tr><td>文件总数</td><td>{total_files}</td></tr>
<tr><td>仪表盘生成</td><td>{escape(now)}</td></tr>
</table>
</div>

<div class="footer">
KnowFlow &copy; {datetime.now().year} &mdash; Agent Knowledge Pipeline &mdash; 数据自动流动
</div>
</div>
</div>
</body>
</html>'''
        return html

    def generate(self):
        """Collect data and generate the dashboard HTML file."""
        self.collect()
        html = self.generate_html()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.output_dir / 'index.html'
        out_path.write_text(html, encoding='utf-8')
        return out_path


def generate(knowledge_dir, output_dir=None, password=None):
    """Convenience function to generate a dashboard."""
    gen = DashboardGenerator(knowledge_dir, output_dir, password=password)
    path = gen.generate()
    print(f"✅ Dashboard generated: {path}")
    return path
