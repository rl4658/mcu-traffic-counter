import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

traffic_history = []

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Traffic Counter Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #0d0d1a;
            --bg-card: rgba(30, 30, 50, 0.6);
            --bg-glass: rgba(255, 255, 255, 0.05);
            --border-glass: rgba(255, 255, 255, 0.1);
            --accent: #4e9af1;
            --accent-glow: rgba(78, 154, 241, 0.5);
            --text-main: #e8e8f0;
            --text-dim: #8a8a9e;
            
            --sev-low: #2ecc71;
            --sev-medium: #f1c40f;
            --sev-high: #e74c3c;
        }

        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-main);
            background-image: 
                radial-gradient(circle at 15% 50%, rgba(78, 154, 241, 0.1), transparent 25%),
                radial-gradient(circle at 85% 30%, rgba(123, 104, 238, 0.1), transparent 25%);
            color: var(--text-main);
            min-height: 100vh;
        }

        .container {
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        header {
            margin-bottom: 40px;
            text-align: center;
        }

        h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #4e9af1, #7b68ee);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 30px var(--accent-glow);
        }

        .subtitle {
            color: var(--text-dim);
            font-size: 1.1rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .stat-card {
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-glass);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
            transition: transform 0.3s ease, border-color 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            border-color: rgba(255, 255, 255, 0.2);
        }

        .stat-title {
            font-size: 0.9rem;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }

        .stat-value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--accent);
        }

        .history-section {
            background: var(--bg-card);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--border-glass);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        }

        .history-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border-glass);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .history-header h2 {
            margin: 0;
            font-size: 1.2rem;
            font-weight: 600;
        }

        .live-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.9rem;
            color: var(--sev-low);
        }

        .dot {
            width: 8px;
            height: 8px;
            background-color: var(--sev-low);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--sev-low);
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; box-shadow: 0 0 0 0 rgba(46, 204, 113, 0.7); }
            70% { opacity: 0.5; box-shadow: 0 0 0 6px rgba(46, 204, 113, 0); }
            100% { opacity: 1; box-shadow: 0 0 0 0 rgba(46, 204, 113, 0); }
        }

        .row {
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }
        
        .row:last-child {
            border-bottom: none;
        }

        .row-header {
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            transition: background 0.2s ease;
        }

        .row-header:hover {
            background: var(--bg-glass);
        }

        .row-time {
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .row-summary {
            color: var(--text-dim);
            font-size: 0.95rem;
        }
        
        .sev-badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .sev-Low { background: rgba(46, 204, 113, 0.2); border: 1px solid rgba(46, 204, 113, 0.5); color: var(--sev-low); }
        .sev-Medium { background: rgba(241, 196, 15, 0.2); border: 1px solid rgba(241, 196, 15, 0.5); color: var(--sev-medium); }
        .sev-High { background: rgba(231, 76, 60, 0.2); border: 1px solid rgba(231, 76, 60, 0.5); color: var(--sev-high); }

        .row-content {
            padding: 0 24px;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.4s ease, padding 0.4s ease;
            background: rgba(0, 0, 0, 0.2);
        }

        .row.active .row-content {
            padding: 20px 24px;
            max-height: 200px;
        }

        .details-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }

        .detail-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 16px;
            background: var(--bg-glass);
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.03);
        }

        .detail-label { color: var(--text-dim); font-size: 0.9rem; }
        .detail-value { font-weight: 600; font-size: 1.1rem; }

        .dir-n { color: #2ecc71; }
        .dir-s { color: #f39c12; }
        .dir-w { color: #4e9af1; }
        .dir-e { color: #7b68ee; }

        .empty-state {
            padding: 40px;
            text-align: center;
            color: var(--text-dim);
        }
    </style>
</head>
<body>

<div class="container">
    <header>
        <h1>Traffic Network Monitor</h1>
        <div class="subtitle">Real-time IoT Intersections Data</div>
    </header>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-title">Total Vehicles Today</div>
            <div class="stat-value" id="globalTotal">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Current Congestion</div>
            <div class="stat-value" id="globalCongestion">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-title">Sensors Active</div>
            <div class="stat-value" id="globalSensors">0</div>
        </div>
    </div>

    <div class="history-section">
        <div class="history-header">
            <h2>Status Logs (1-Min Intervals)</h2>
            <div class="live-indicator">
                <div class="dot"></div> Live Updates
            </div>
        </div>
        <div id="historyList">
            <div class="empty-state">Waiting for IoT device data...</div>
        </div>
    </div>
</div>

<script>
    let activeRows = new Set();
    let currentDataLength = 0;

    function toggleRow(element, index) {
        const row = element.parentElement;
        row.classList.toggle('active');
        if (row.classList.contains('active')) {
            activeRows.add(index);
        } else {
            activeRows.delete(index);
        }
    }

    function formatTime(unixSecs) {
        const d = new Date(unixSecs * 1000);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    async function fetchData() {
        try {
            const response = await fetch('/api/history');
            const data = await response.json();
            
            if (data.length === 0) return;
            
            // Update Top Stats
            const latest = data[data.length - 1];
            document.getElementById('globalTotal').innerText = latest.total_count;
            document.getElementById('globalCongestion').innerText = latest.severity;
            
            // Re-render list if data size changed
            if (data.length !== currentDataLength) {
                currentDataLength = data.length;
                
                // Get unique active devices
                const devices = new Set(data.map(d => d.device_id));
                document.getElementById('globalSensors').innerText = devices.size;

                const listEl = document.getElementById('historyList');
                listEl.innerHTML = ''; // Rebuild
                
                // Reverse iterate to show newest first
                [...data].reverse().forEach((item, revIndex) => {
                    const idx = data.length - 1 - revIndex; // original idx
                    const isActive = activeRows.has(idx) ? 'active' : '';
                    
                    const rowHtml = `
                        <div class="row ${isActive}">
                            <div class="row-header" onclick="toggleRow(this, ${idx})">
                                <div class="row-time">
                                    <span>${formatTime(item.timestamp)}</span>
                                    <span class="sev-badge sev-${item.severity}">${item.severity}</span>
                                </div>
                                <div class="row-summary">
                                    ${item.device_id} &bull; ${item.total_count} vehicles
                                </div>
                            </div>
                            <div class="row-content">
                                <div class="details-grid">
                                    <div class="detail-item">
                                        <span class="detail-label">Northbound (↑)</span>
                                        <span class="detail-value dir-n">${item.north}</span>
                                    </div>
                                    <div class="detail-item">
                                        <span class="detail-label">Southbound (↓)</span>
                                        <span class="detail-value dir-s">${item.south}</span>
                                    </div>
                                    <div class="detail-item">
                                        <span class="detail-label">Westbound (←)</span>
                                        <span class="detail-value dir-w">${item.west}</span>
                                    </div>
                                    <div class="detail-item">
                                        <span class="detail-label">Eastbound (→)</span>
                                        <span class="detail-value dir-e">${item.east}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                    listEl.innerHTML += rowHtml;
                });
            }
        } catch (e) {
            console.error("Failed to fetch data", e);
        }
    }

    // Initial fetch, then poll every 3 seconds
    fetchData();
    setInterval(fetchData, 3000);
</script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(DASHBOARD_HTML)


@app.route("/traffic", methods=["POST"])
def traffic():
    data = request.json
    print(f"[{datetime.datetime.now()}] Received 1-min IoT report: {data}")
    traffic_history.append(data)
    return jsonify({"ok": True, "received": data})


@app.route("/api/history", methods=["GET"])
def history():
    return jsonify(traffic_history)


@app.route("/latest", methods=["GET"])
def latest():
    if traffic_history:
        return jsonify(traffic_history[-1])
    return jsonify({})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)