const positions = ["Attack", "Midfield", "SSDM", "Defensemen", "Faceoff", "Goalie"];

async function loadPredictions(year, week) {
    const container = document.getElementById('plots-container');
    const subtitle = document.getElementById('subtitle-text');
    
    if (subtitle) {
        subtitle.textContent = `${year} SEASON | WEEK ${week} ANALYSIS`;
    }
    
    container.innerHTML = '<div class="loading">Analyzing Matchups...</div>';

    try {
        const response = await fetch(`predictions/${year}/${week}`);
        if (!response.ok) throw new Error(`Predictions not found for Year ${year} Week ${week}.`);
        const data = await response.json();
        container.innerHTML = ''; // Clear loading and old plots

        const renderQueue = [];

        positions.forEach(pos => {
            // subPosition preserves the SSDM vs Defensemen split for display
            // while positionGroup ("Defense") is used for shared boom thresholds
            const posData = data.filter(d => d.subPosition === pos);
            if (posData.length === 0) return;

            console.log(`Creating card for ${pos}`);
            const div = document.createElement('div');
            div.className = 'plot-card';
            div.id = `plot-${pos}`;
            container.appendChild(div);

            renderQueue.push({ id: div.id, pos, data: posData });
        });

        // Render all plots after the grid layout has settled with all cards in the DOM
        renderQueue.forEach(item => {
            console.log(`Rendering ${item.pos} with ${item.data.length} players`);
            let displayTitle = item.pos;
            if (displayTitle === "SSDM") displayTitle = "SSDM/LSM";
            renderPlot(item.id, displayTitle, item.data);
        });

    } catch (err) {
        container.innerHTML = `<div class="loading" style="color: #ff4444">${err.message}</div>`;
        const statusEl = document.getElementById('cacheStatus');
        if (statusEl) {
            statusEl.textContent = '⚡ OFFLINE — data not loaded';
            statusEl.style.background = 'rgba(245, 101, 101, 0.12)';
            statusEl.style.color = '#f56565';
            statusEl.style.border = '1px solid rgba(245, 101, 101, 0.25)';
        }
    }
}

function renderPlot(targetId, title, data) {
    const x = data.map(d => d.salary);
    const y = data.map(d => d.BoomProbability);
    
    const xMin = Math.min(...x);
    const xMax = Math.max(...x);
    const xPadding = (xMax - xMin) * 0.15 || 50;
    const medianSalary = x.length > 0 ? x.slice().sort((a,b) => a-b)[Math.floor(x.length/2)] : 500;

    // Sort data by star power so top players get priority for labels
    const sortedData = [...data].sort((a, b) => b.fp_season_avg - a.fp_season_avg);

    const placed = [];
    const textLabels = sortedData.map(d => {
        const xNorm = (d.salary - xMin) / (xMax - xMin || 1);
        const yNorm = d.BoomProbability / 100;
        
        // Simple distance check to prevent label overlap
        let overlap = false;
        for (let p of placed) {
            const dist = Math.sqrt(Math.pow(p.x - xNorm, 2) + Math.pow(p.y - yNorm, 2));
            if (dist < 0.07) { // 7% of chart area threshold
                overlap = true;
                break;
            }
        }
        
        if (!overlap) {
            placed.push({ x: xNorm, y: yNorm });
            return d.lastName;
        }
        return "";
    });

    const trace = {
        x: sortedData.map(d => d.salary),
        y: sortedData.map(d => d.BoomProbability),
        mode: 'markers+text',
        text: textLabels,
        textfont: { family: 'Inter', size: 10, color: 'rgba(255,255,255,0.7)' },
        textposition: 'top center',
        hoverinfo: 'none',
        customdata: sortedData,
        marker: {
            size: sortedData.map(d => Math.sqrt(d.fp_season_avg) * 5 + 5),
            color: sortedData.map(d => d.team_def_rating),
            colorscale: [
                [0, 'rgb(215,48,39)'],
                [0.5, 'rgb(255,255,191)'],
                [1, 'rgb(26,152,80)']
            ],
            reversescale: false, 
            cmin: 0.6,
            cmax: 1.4,
            showscale: true,
            colorbar: {
                title: 'Hist. Perf vs Opp',
                thickness: 15,
                x: 1.1,
                tickfont: { color: '#8b949e' }
            },
            line: { color: '#161b22', width: 1 },
            opacity: 0.9
        },
        type: 'scatter'
    };

    const layout = {
        title: { 
            text: title.toUpperCase(), 
            font: { color: '#9f7aea', family: 'Inter', size: 22, weight: 700 },
            x: 0.05,
            xanchor: 'left'
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#f0f6fc', family: 'Inter' },
        xaxis: { 
            title: 'Fantasy Salary (Coins)', 
            gridcolor: '#30363d', 
            zeroline: false,
            range: [xMin - xPadding, xMax + xPadding]
        },
        yaxis: { 
            title: 'Boom Probability (%)', 
            range: [-5, 115], 
            gridcolor: '#30363d', 
            zeroline: false 
        },
        margin: { t: 80, b: 80, l: 80, r: 100 },
        shapes: [
            { type: 'line', x0: medianSalary, x1: medianSalary, yref: 'paper', y0: 0, y1: 1, line: { color: 'rgba(255,255,255,0.1)', width: 1, dash: 'dash' } },
            { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: 50, y1: 50, line: { color: 'rgba(255,255,255,0.1)', width: 1, dash: 'dash' } }
        ]
    };

    Plotly.purge(targetId);
    Plotly.newPlot(targetId, [trace], layout, { responsive: true, displayModeBar: false });

    // Custom Tooltip Logic
    const plotEl = document.getElementById(targetId);
    const tooltip = document.getElementById('custom-tooltip');

    plotEl.on('plotly_click', function(data){
        window.isPlotlyClick = true;
        const point = data.points[0];
        const p = point.customdata;
        
        tooltip.style.display = 'block';
        tooltip.style.left = (data.event.clientX + 20) + 'px';
        tooltip.style.top = (data.event.clientY - 20) + 'px';
        
        tooltip.innerHTML = `
            <div class="tooltip-header">${p.firstName} ${p.lastName}</div>
            <div class="tooltip-row"><span class="tooltip-label">Opponent</span><span class="tooltip-value">${p.opponent}</span></div>
            <div class="tooltip-row"><span class="tooltip-label">Salary</span><span class="tooltip-value">${p.salary} Coins</span></div>
            <div class="tooltip-row"><span class="tooltip-label">Season Avg</span><span class="tooltip-value">${p.fp_season_avg.toFixed(1)}</span></div>
            <div class="tooltip-row"><span class="tooltip-label">Opp. Rating</span><span class="tooltip-value" style="color: ${p.team_def_rating > 1.1 ? '#00ff88' : p.team_def_rating < 0.9 ? '#ff4444' : '#ffffff'}">${p.team_def_rating.toFixed(2)}</span></div>
            <div class="tooltip-row" style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.1)">
                <span class="tooltip-label">Boom Prob</span>
                <span class="tooltip-value" style="color: #00ccff">${p.BoomProbability.toFixed(0)}%</span>
            </div>
        `;
    });
}

async function initDashboard() {
    const yearSelect = document.getElementById('year-select');
    const weekSelect = document.getElementById('week-select');
    try {
        const response = await fetch('predictions/available');
        if (!response.ok) throw new Error("Failed to load available prediction periods.");
        const available = await response.json();
        
        if (available.length === 0) {
            yearSelect.innerHTML = '<option disabled>No periods</option>';
            weekSelect.innerHTML = '<option disabled>No periods</option>';
            throw new Error("No prediction periods found.");
        }
        
        // Group by year
        const periodsByYear = {};
        available.forEach(item => {
            if (!periodsByYear[item.year]) periodsByYear[item.year] = [];
            periodsByYear[item.year].push(item.week);
        });

        const years = Object.keys(periodsByYear).sort((a, b) => b - a); // descending
        
        yearSelect.innerHTML = '';
        years.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            yearSelect.appendChild(option);
        });

        function populateWeeks(year) {
            weekSelect.innerHTML = '';
            const weeks = periodsByYear[year].sort((a, b) => b - a); // descending
            weeks.forEach(week => {
                const option = document.createElement('option');
                option.value = week;
                option.textContent = `Week ${week}`;
                weekSelect.appendChild(option);
            });
        }

        // Initialize weeks for the first year
        const defaultYear = years[0];
        populateWeeks(defaultYear);
        yearSelect.value = defaultYear;
        const defaultWeek = periodsByYear[defaultYear].sort((a, b) => b - a)[0];
        weekSelect.value = defaultWeek;

        // Set up change listeners
        yearSelect.addEventListener('change', (e) => {
            const selectedYear = e.target.value;
            populateWeeks(selectedYear);
            const newWeek = periodsByYear[selectedYear].sort((a, b) => b - a)[0];
            weekSelect.value = newWeek;
            loadPredictions(selectedYear, newWeek);
        });

        weekSelect.addEventListener('change', (e) => {
            loadPredictions(yearSelect.value, e.target.value);
        });
        
        // Load initial data
        loadPredictions(defaultYear, defaultWeek);
        
    } catch (err) {
        console.error(err);
        const container = document.getElementById('plots-container');
        container.innerHTML = `<div class="loading" style="color: #ff4444">${err.message}</div>`;
        const statusEl = document.getElementById('cacheStatus');
        if (statusEl) {
            statusEl.textContent = '⚡ OFFLINE — data not loaded';
            statusEl.style.background = 'rgba(245, 101, 101, 0.12)';
            statusEl.style.color = '#f56565';
            statusEl.style.border = '1px solid rgba(245, 101, 101, 0.25)';
        }
    }
}

document.addEventListener('click', function(e) {
    if (window.isPlotlyClick) {
        window.isPlotlyClick = false;
        return;
    }
    const tooltip = document.getElementById('custom-tooltip');
    if (tooltip && tooltip.style.display === 'block' && !e.target.closest('#custom-tooltip')) {
        tooltip.style.display = 'none';
    }
});

initDashboard();
