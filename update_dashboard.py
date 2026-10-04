import re

with open("dashboard_ui.html", "r", encoding="utf-8") as f:
    html = f.read()

# 1. Update CSS to be more modern and add chart/table styles
new_css = """
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --card-hover: #334155;
      --border: #334155;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #0ea5e9;
      --emerald: #10b981;
      --amber: #f59e0b;
      --rose: #f43f5e;
      --violet: #8b5cf6;
      --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', system-ui, sans-serif; }
    body { background: var(--bg); color: var(--text); line-height: 1.5; padding-bottom: 60px; font-size: 14px; }
    header {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      border-bottom: 1px solid var(--border);
      padding: 20px 30px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 14px;
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: var(--shadow);
    }
    .brand h1 { font-size: 1.4rem; font-weight: 700; color: #fff; letter-spacing: -0.02em; }
    .brand p { font-size: 0.85rem; color: var(--muted); margin-top: 4px; }
    .top-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    .badge-pill {
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.2);
      color: #34d399;
      font-size: 0.8rem;
      padding: 6px 14px;
      border-radius: 9999px;
      font-weight: 600;
    }
    button {
      cursor: pointer;
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--text);
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 0.85rem;
      font-weight: 500;
      transition: all 0.2s;
    }
    button:hover { background: var(--card-hover); border-color: var(--accent); }
    .btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
    .btn-primary:hover { background: #0284c7; }
    .btn-success { background: var(--emerald); border-color: var(--emerald); color: #fff; }
    .btn-success:hover { background: #059669; }
    .btn-warn { background: var(--amber); border-color: var(--amber); color: #fff; }
    .btn-danger { background: var(--rose); border-color: var(--rose); color: #fff; }

    nav.tabs {
      display: flex;
      gap: 8px;
      padding: 16px 30px;
      background: #0f172a;
      border-bottom: 1px solid var(--border);
      overflow-x: auto;
    }
    nav.tabs button {
      background: transparent;
      border: 1px solid transparent;
      color: var(--muted);
      padding: 10px 18px;
      border-radius: 6px;
      white-space: nowrap;
      font-weight: 500;
    }
    nav.tabs button.active {
      background: rgba(14, 165, 233, 0.1);
      border-color: rgba(14, 165, 233, 0.3);
      color: var(--accent);
    }
    nav.tabs button:hover:not(.active) {
      color: #e2e8f0;
      background: rgba(255,255,255,0.05);
    }

    .container { max-width: 1400px; margin: 30px auto; padding: 0 30px; }
    .tab-pane { display: none; animation: fadeIn 0.3s; }
    .tab-pane.active { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin-bottom: 30px; }
    .kpi-card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      box-shadow: var(--shadow);
      transition: transform 0.2s;
    }
    .kpi-card:hover { transform: translateY(-2px); }
    .kpi-label { font-size: 0.8rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
    .kpi-val { font-size: 2rem; font-weight: 700; margin-top: 8px; color: #fff; letter-spacing: -0.02em; }
    .kpi-sub { font-size: 0.8rem; color: var(--emerald); margin-top: 6px; font-weight: 500; }

    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
    @media (max-width: 960px) { .grid-2 { grid-template-columns: 1fr; } }

    .panel {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: var(--shadow);
    }
    .panel h2 { font-size: 1.15rem; margin-bottom: 16px; color: #f8fafc; font-weight: 600; }
    
    .data-table-container {
        overflow-x: auto;
        margin-top: 15px;
        border-radius: 8px;
        border: 1px solid var(--border);
    }
    table.data-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
    }
    table.data-table th, table.data-table td {
        padding: 10px 15px;
        border-bottom: 1px solid var(--border);
        text-align: left;
    }
    table.data-table th {
        background: #0f172a;
        color: var(--muted);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }
    table.data-table tr:last-child td { border-bottom: none; }
    table.data-table tr:hover { background: rgba(255,255,255,0.02); }

    .chart-container {
        background: #0f172a;
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 15px;
        margin-top: 20px;
        height: 350px;
        position: relative;
    }

    .funnel-row { margin-bottom: 16px; }
    .funnel-header { display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 6px; font-weight: 500; }
    .bar-bg { background: #0f172a; height: 10px; border-radius: 999px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 999px; transition: width 0.5s ease-out; }

    .job-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: var(--shadow); }
    .job-card:hover { border-color: var(--accent); }
    .job-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
    .job-title { font-size: 1.15rem; font-weight: 600; color: #fff; letter-spacing: -0.01em; }
    .job-comp { font-size: 0.95rem; color: var(--accent); font-weight: 500; margin-top: 4px; }
    .chips { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
    .chip { font-size: 0.75rem; padding: 4px 12px; border-radius: 999px; background: #0f172a; border: 1px solid var(--border); color: #cbd5e1; font-weight: 500; }
    
    .why-box { background: rgba(14, 165, 233, 0.05); border-left: 3px solid var(--accent); padding: 12px 16px; border-radius: 4px; font-size: 0.85rem; color: #e2e8f0; margin: 12px 0; }
    textarea.pitch-box { width: 100%; min-height: 120px; background: #0f172a; color: #e2e8f0; border: 1px solid var(--border); border-radius: 6px; padding: 12px; font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 0.85rem; margin-top: 10px; }
    .action-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; align-items: center; }
    input, select { background: #0f172a; border: 1px solid var(--border); color: #fff; padding: 10px 14px; border-radius: 6px; font-size: 0.9rem; }
    input:focus, select:focus { outline: none; border-color: var(--accent); }
"""

# Replace CSS
html = re.sub(r':root \{.*?\}', new_css, html, flags=re.DOTALL)

# Add Chart.js to head
head_end = html.find("</head>")
chart_js = '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n'
html = html[:head_end] + chart_js + html[head_end:]

# 2. Add Tab Button
nav_end = html.find("</nav>")
new_tab_btn = '<button onclick="switchTab(\'tab-data\', this)">6. Database Visualizer</button>\n  '
html = html[:nav_end] + new_tab_btn + html[nav_end:]

# 3. Add Tab Content
tab_content = """
    <!-- TAB 6: DATA VISUALIZER -->
    <div id="tab-data" class="tab-pane">
      <div class="panel">
        <h2>Database Visualizer & Analytics</h2>
        <p style="font-size:0.85rem; color:var(--muted); margin-bottom:16px;">
          Select a table from the data layer to visualize its raw records and generate dynamic charts.
        </p>
        <div class="calc-inputs" style="margin-bottom:20px;">
          <select id="dbTableSelect" onchange="loadTableData()">
            <option value="">Loading tables...</option>
          </select>
          <button class="btn-primary" onclick="loadTableData()">Refresh Data</button>
        </div>
        
        <div class="grid-2">
            <div class="chart-container">
                <canvas id="dataChart1"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="dataChart2"></canvas>
            </div>
        </div>

        <h3 style="margin-top:24px; margin-bottom:12px; font-size:1rem; font-weight:600;">Raw Table Data</h3>
        <div class="data-table-container" id="dataTableContainer">
            <p style="color:var(--muted); padding:10px;">Select a table to view records.</p>
        </div>
      </div>
    </div>
"""
tabs_end = html.rfind("</div>\n\n  <script>")
html = html[:tabs_end] + tab_content + html[tabs_end:]

# 4. Add JavaScript for the new tab
js_code = """
    let myChart1 = null;
    let myChart2 = null;

    async function loadTableList() {
        try {
            const resp = await fetch('/api/tables');
            if (resp.ok) {
                const data = await resp.json();
                const sel = document.getElementById('dbTableSelect');
                sel.innerHTML = '<option value="">-- Select a Table --</option>' + 
                    data.tables.map(t => `<option value="${t}">${t}</option>`).join('');
                if (data.tables.includes('agent_episodic_memories')) {
                    sel.value = 'agent_episodic_memories';
                    loadTableData();
                }
            }
        } catch (e) {
            console.error("Failed to load tables", e);
        }
    }

    async function loadTableData() {
        const table = document.getElementById('dbTableSelect').value;
        if (!table) return;
        try {
            const resp = await fetch(`/api/table_data/${table}`);
            if (resp.ok) {
                const data = await resp.json();
                renderDataTable(data.columns, data.data);
                renderDataCharts(table, data.columns, data.data);
            }
        } catch(e) {
            console.error("Failed to load table data", e);
            document.getElementById('dataTableContainer').innerHTML = '<p style="color:var(--rose);">Error loading data</p>';
        }
    }

    function renderDataTable(columns, rows) {
        if (!rows.length) {
            document.getElementById('dataTableContainer').innerHTML = '<p style="padding:10px; color:var(--muted);">Table is empty.</p>';
            return;
        }
        let html = '<table class="data-table"><thead><tr>';
        columns.forEach(c => html += `<th>${escapeHtml(c)}</th>`);
        html += '</tr></thead><tbody>';
        rows.slice(0, 100).forEach(r => {
            html += '<tr>';
            columns.forEach(c => {
                let val = r[c];
                if (typeof val === 'object' && val !== null) val = JSON.stringify(val);
                if (String(val).length > 50) val = String(val).substring(0, 50) + '...';
                html += `<td>${escapeHtml(val)}</td>`;
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        if (rows.length > 100) html += `<p style="padding:10px; font-size:0.8rem; color:var(--muted);">Showing top 100 of ${rows.length} rows.</p>`;
        document.getElementById('dataTableContainer').innerHTML = html;
    }

    function renderDataCharts(tableName, columns, rows) {
        if (myChart1) myChart1.destroy();
        if (myChart2) myChart2.destroy();
        
        const ctx1 = document.getElementById('dataChart1').getContext('2d');
        const ctx2 = document.getElementById('dataChart2').getContext('2d');
        
        Chart.defaults.color = '#94a3b8';
        Chart.defaults.font.family = 'Inter';

        if (tableName === 'agent_episodic_memories') {
            // Chart 1: Lifecycle Stage Distribution
            const stages = {};
            rows.forEach(r => { stages[r.lifecycle_stage] = (stages[r.lifecycle_stage] || 0) + 1; });
            myChart1 = new Chart(ctx1, {
                type: 'doughnut',
                data: {
                    labels: Object.keys(stages),
                    datasets: [{
                        data: Object.values(stages),
                        backgroundColor: ['#0ea5e9', '#10b981', '#f59e0b', '#f43f5e', '#8b5cf6', '#34d399']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Jobs by Lifecycle Stage', color: '#fff' } } }
            });

            // Chart 2: Match Score Distribution
            const scores = rows.map(r => r.match_score).filter(s => s != null);
            const bins = {'90-100':0, '80-89':0, '70-79':0, '<70':0};
            scores.forEach(s => {
                if(s >= 90) bins['90-100']++;
                else if (s >= 80) bins['80-89']++;
                else if (s >= 70) bins['70-79']++;
                else bins['<70']++;
            });
            myChart2 = new Chart(ctx2, {
                type: 'bar',
                data: {
                    labels: Object.keys(bins),
                    datasets: [{
                        label: 'Number of Roles',
                        data: Object.values(bins),
                        backgroundColor: '#0ea5e9'
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Match Score Distribution', color: '#fff' } } }
            });
        } else if (tableName === 'application_timeline_events') {
            const stages = {};
            rows.forEach(r => { stages[r.to_stage] = (stages[r.to_stage] || 0) + 1; });
            myChart1 = new Chart(ctx1, {
                type: 'pie',
                data: {
                    labels: Object.keys(stages),
                    datasets: [{ data: Object.values(stages), backgroundColor: ['#0ea5e9', '#10b981', '#f59e0b', '#f43f5e'] }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Timeline Events by Target Stage', color: '#fff' } } }
            });
            
            const dates = {};
            rows.forEach(r => { 
                const d = String(r.event_at).substring(0, 10);
                if (d && d !== 'null') dates[d] = (dates[d] || 0) + 1; 
            });
            myChart2 = new Chart(ctx2, {
                type: 'line',
                data: {
                    labels: Object.keys(dates).sort(),
                    datasets: [{ label: 'Events', data: Object.keys(dates).sort().map(k=>dates[k]), borderColor: '#10b981', tension: 0.1 }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { title: { display: true, text: 'Events Over Time', color: '#fff' } } }
            });
        } else {
            // Generic visual
            document.getElementById('dataChart1').parentElement.innerHTML = '<p style="color:var(--muted); text-align:center; padding-top:40%;">Auto-charting not configured for this table.</p>';
            document.getElementById('dataChart2').parentElement.innerHTML = '<p style="color:var(--muted); text-align:center; padding-top:40%;">Auto-charting not configured for this table.</p>';
        }
    }
"""
load_state_call = "loadState().then(() => {"
js_hook = js_code + "\n    loadTableList();\n    " + load_state_call
html = html.replace(load_state_call, js_hook)

with open("dashboard_ui.html", "w", encoding="utf-8") as f:
    f.write(html)
