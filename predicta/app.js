const positions = ["Attack", "Midfield", "SSDM", "Defensemen", "Faceoff", "Goalie"];
let activeRosterTab = "Cash";

const rosterDescriptions = {
    "Cash": "<strong>BOOM</strong>: Optimizes the roster to maximize expected value (EV) points based on classification probabilities. This focuses on high-floor consistency, making it best for head-to-head matches and double-ups.",
    "Ceiling": "<strong>CEILING</strong>: Optimizes the roster to maximize predicted 90th percentile ceiling points directly from the regression model. Ideal for finding high-upside sleeper combinations.",
    "StackedBoom": "<strong>STACK BOOM</strong>: Teammate-stacking tournament optimizer using Boom Probability. Pairs high-boom players on the same franchise to capture positive offensive correlation.",
    "StackedReg": "<strong>STACK CEILING</strong>: Teammate-stacking tournament optimizer using 90th percentile ceilings. Pairs high-ceiling offensive players to maximize tournament-winning scoring explosions."
};

async function loadPredictions(year, week) {
    const container = document.getElementById('plots-container');
    const subtitle = document.getElementById('subtitle-text');
    
    if (subtitle) {
        subtitle.textContent = `${year} SEASON ANALYSIS`;
    }
    
    container.innerHTML = '<div class="loading">Analyzing Matchups...</div>';

    // Show loading in advisor panel
    const coreContainer = document.getElementById('core-container');
    const sleeperContainer = document.getElementById('sleeper-container');
    const rosterContainer = document.getElementById('roster-container');
    if (coreContainer) coreContainer.innerHTML = '<span class="muted-text">Analyzing...</span>';
    if (sleeperContainer) sleeperContainer.innerHTML = '<span class="muted-text">Analyzing...</span>';
    if (rosterContainer) rosterContainer.innerHTML = '<div class="muted-text" style="padding: 1rem 0;">Solving optimal rosters...</div>';

    try {
        // Parallel fetch for predictions and optimizer data
        const [predRes, advRes] = await Promise.all([
            fetch(`predictions/${year}/${week}`),
            fetch(`advisory/${year}/${week}`).catch(err => {
                console.warn('Advisory fetch failed:', err);
                return null;
            })
        ]);

        if (!predRes.ok) throw new Error(`Predictions not found for Year ${year} Week ${week}.`);
        const data = await predRes.json();
        
        let advisoryData = null;
        if (advRes && advRes.ok) {
            advisoryData = await advRes.json();
        }

        container.innerHTML = ''; // Clear loading and old plots
        const renderQueue = [];

        positions.forEach(pos => {
            const posData = data.filter(d => d.subPosition === pos);
            if (posData.length === 0) return;

            console.log(`Creating card for ${pos}`);
            const div = document.createElement('div');
            div.className = 'plot-card';
            div.id = `plot-${pos}`;
            container.appendChild(div);

            renderQueue.push({ id: div.id, pos, data: posData });
        });

        // Render all plots
        renderQueue.forEach(item => {
            console.log(`Rendering ${item.pos} with ${item.data.length} players`);
            let displayTitle = item.pos;
            if (displayTitle === "SSDM") displayTitle = "SSDM/LSM";
            renderPlot(item.id, displayTitle, item.data);
        });

        // Store predictions data globally for lookup
        window.currentPredictions = data;

        if (advisoryData) {
            renderAdvisor(advisoryData);
        } else {
            if (coreContainer) coreContainer.innerHTML = '<span class="muted-text">Advisory unavailable.</span>';
            if (sleeperContainer) sleeperContainer.innerHTML = '<span class="muted-text">Advisory unavailable.</span>';
            if (rosterContainer) rosterContainer.innerHTML = '<div class="muted-text" style="padding: 1rem 0;">Optimizer unavailable.</div>';
        }

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
    const xPadding = (xMax - xMin) * 0.15 || 5;
    const medianSalary = x.length > 0 ? x.slice().sort((a,b) => a-b)[Math.floor(x.length/2)] : 10;

    // Sort data by star power so top players get priority for labels
    const sortedData = [...data].sort((a, b) => b.fp_season_avg - a.fp_season_avg);

    const placed = [];
    const textLabels = sortedData.map(d => {
        const xNorm = (d.salary - xMin) / (xMax - xMin || 1);
        const yNorm = d.BoomProbability / 100;
        
        let overlap = false;
        for (let p of placed) {
            const dist = Math.sqrt(Math.pow(p.x - xNorm, 2) + Math.pow(p.y - yNorm, 2));
            if (dist < 0.07) {
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
            size: sortedData.map(d => Math.max(2, d.PredictedPoints || 0) * 0.9 + 5),
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
            <div class="tooltip-row">
                <span class="tooltip-label">Ceiling (Pts)</span>
                <span class="tooltip-value" style="color: #9f7aea">${(p.PredictedPoints || 0).toFixed(1)}</span>
            </div>
        `;
    });
}

function renderAdvisor(advisoryData) {
    window.currentAdvisory = advisoryData;
    
    // 1. Render Consensus Core Plays
    const coreContainer = document.getElementById('core-container');
    if (coreContainer) {
        coreContainer.innerHTML = '';
        if (advisoryData.Core && advisoryData.Core.length > 0) {
            advisoryData.Core.forEach(fullName => {
                const nameParts = fullName.split(' ');
                const lookup = window.currentPredictions ? window.currentPredictions.find(p => p.firstName === nameParts[0] && p.lastName === nameParts[1]) : null;
                const pos = lookup ? lookup.subPosition : 'Attack';
                
                const pill = document.createElement('span');
                pill.className = 'pill core';
                pill.textContent = fullName;
                pill.title = "Click to highlight on chart";
                pill.onclick = () => highlightPlayerInPlot(pos, nameParts[0], nameParts[1]);
                coreContainer.appendChild(pill);
            });
        } else {
            coreContainer.innerHTML = '<span class="muted-text">No consensus core plays this week.</span>';
        }
    }
    
    // 2. Render Ceiling Sleepers
    const sleeperContainer = document.getElementById('sleeper-container');
    if (sleeperContainer) {
        sleeperContainer.innerHTML = '';
        if (advisoryData.Sleepers && advisoryData.Sleepers.length > 0) {
            advisoryData.Sleepers.forEach(fullName => {
                const nameParts = fullName.split(' ');
                const lookup = window.currentPredictions ? window.currentPredictions.find(p => p.firstName === nameParts[0] && p.lastName === nameParts[1]) : null;
                const pos = lookup ? lookup.subPosition : 'Attack';
                const salary = lookup ? lookup.salary : '';
                
                const pill = document.createElement('span');
                pill.className = 'pill sleeper';
                pill.textContent = `${fullName} (${salary}c)`;
                pill.title = "Click to highlight on chart";
                pill.onclick = () => highlightPlayerInPlot(pos, nameParts[0], nameParts[1]);
                sleeperContainer.appendChild(pill);
            });
        } else {
            sleeperContainer.innerHTML = '<span class="muted-text">No sleepers found.</span>';
        }
    }
    
    // 3. Render Roster
    renderRoster(activeRosterTab);
}

function renderRoster(rosterName) {
    activeRosterTab = rosterName;
    const container = document.getElementById('roster-container');
    if (!container || !window.currentAdvisory) return;

    // Update active tab styling
    document.querySelectorAll('.tab-btn').forEach(btn => {
        if (btn.getAttribute('data-roster') === rosterName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    const roster = window.currentAdvisory[rosterName];
    if (!roster || roster.length === 0) {
        container.innerHTML = '<div class="muted-text" style="padding: 1rem 0;">No lineup found for this strategy.</div>';
        return;
    }

    const posOrder = { "Attack": 0, "Midfield": 1, "Defense": 2, "Faceoff": 3, "Goalie": 4 };
    const sortedRoster = [...roster].sort((a, b) => posOrder[a.position] - posOrder[b.position]);

    const totalCost = roster.reduce((sum, p) => sum + p.salary, 0);
    const totalEV = roster.reduce((sum, p) => sum + p.EV, 0);
    const totalCeiling = roster.reduce((sum, p) => sum + (p.ceiling || 0), 0);
    const totalBoom = roster.reduce((sum, p) => sum + (p.boom || 0), 0);

    const showBoom = (rosterName === "StackedBoom" || rosterName === "Cash");
    const lastColHeader = showBoom ? "Boom" : "Ceil";
    const avgBoom = totalBoom / roster.length;

    let html = `
        <div class="roster-desc">
            ${rosterDescriptions[rosterName] || ""}
        </div>
        <table class="roster-table">
            <thead>
                <tr>
                    <th>Slot</th>
                    <th>Player</th>
                    <th>Team</th>
                    <th>Cost</th>
                    <th>EV</th>
                    <th>${lastColHeader}</th>
                </tr>
            </thead>
            <tbody>
    `;

    sortedRoster.forEach(p => {
        const lookup = window.currentPredictions ? window.currentPredictions.find(item => item.firstName === p.firstName && item.lastName === p.lastName) : null;
        let badgePos = p.position;
        if (lookup) {
            badgePos = lookup.subPosition;
            if (badgePos === "SSDM") badgePos = "SSDM/LSM";
        }

        html += `
            <tr class="roster-row" onclick="highlightPlayerInPlot('${lookup ? lookup.subPosition : p.position}', '${p.firstName}', '${p.lastName}')" title="Click to highlight on chart">
                <td><span class="roster-pos-badge">${badgePos}</span></td>
                <td><strong>${p.lastName}</strong>, ${p.firstName[0]}.</td>
                <td><span style="font-weight:700;">${p.team}</span> <span style="font-size:0.6rem; color:#8b949e">@ ${p.opponent}</span></td>
                <td>${p.salary}</td>
                <td>${p.EV.toFixed(1)}</td>
                <td>${showBoom ? (p.boom ? p.boom.toFixed(0) + "%" : "-") : p.ceiling.toFixed(1)}</td>
            </tr>
        `;
    });

    html += `
                <tr class="roster-total-row">
                    <td colspan="3">Total</td>
                    <td>${totalCost}</td>
                    <td>${totalEV.toFixed(1)}</td>
                    <td>${showBoom ? avgBoom.toFixed(0) + "% (avg)" : totalCeiling.toFixed(1)}</td>
                </tr>
            </tbody>
        </table>
    `;

    const teams = roster.map(p => p.team);
    const stackCounts = {};
    teams.forEach(t => stackCounts[t] = (stackCounts[t] || 0) + 1);
    const stacks = Object.entries(stackCounts).filter(([t, count]) => count >= 2);
    if (stacks.length > 0) {
        const stackList = stacks.map(([t, count]) => `${t} (${count}x)`).join(', ');
        html += `<div class="stack-indicator">⚡ <strong>Stacks</strong>: ${stackList}</div>`;
    }

    container.innerHTML = html;
}

function highlightPlayerInPlot(position, firstName, lastName) {
    let displayPos = position;
    if (position === "SSDM" || position === "LSM") {
        displayPos = "SSDM";
    } else if (position === "Defense" || position === "Defensemen") {
        displayPos = "Defensemen";
    }
    
    const plotId = `plot-${displayPos}`;
    const plotEl = document.getElementById(plotId);
    if (!plotEl) return;
    
    const gd = plotEl;
    if (!gd.data || gd.data.length === 0) return;
    
    const customdata = gd.data[0].customdata;
    const ptIdx = customdata.findIndex(p => p.firstName === firstName && p.lastName === lastName);
    if (ptIdx === -1) return;
    
    plotEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    const originalLineColors = gd.data[0].marker.line.color 
        ? (Array.isArray(gd.data[0].marker.line.color) ? [...gd.data[0].marker.line.color] : Array(customdata.length).fill(gd.data[0].marker.line.color))
        : Array(customdata.length).fill('#161b22');
        
    const originalLineWidths = gd.data[0].marker.line.width
        ? (Array.isArray(gd.data[0].marker.line.width) ? [...gd.data[0].marker.line.width] : Array(customdata.length).fill(gd.data[0].marker.line.width))
        : Array(customdata.length).fill(1);
        
    const originalSizes = gd.data[0].marker.size
        ? (Array.isArray(gd.data[0].marker.size) ? [...gd.data[0].marker.size] : Array(customdata.length).fill(10))
        : Array(customdata.length).fill(10);
        
    const newColors = [...originalLineColors];
    const newWidths = [...originalLineWidths];
    const newSizes = [...originalSizes];
    
    newColors[ptIdx] = '#ff00ff';
    newWidths[ptIdx] = 5;
    newSizes[ptIdx] = originalSizes[ptIdx] * 1.8;
    
    Plotly.restyle(gd, {
        'marker.line.color': [newColors],
        'marker.line.width': [newWidths],
        'marker.size': [newSizes]
    }, [0]);
    
    const tooltip = document.getElementById('custom-tooltip');
    const p = customdata[ptIdx];
    const rect = plotEl.getBoundingClientRect();
    
    tooltip.style.display = 'block';
    tooltip.style.left = (rect.left + 50) + 'px';
    tooltip.style.top = (rect.top + 80) + 'px';
    
    tooltip.innerHTML = `
        <div class="tooltip-header">${p.firstName} ${p.lastName} <span style="font-size:0.6rem; color: #ff00ff; border: 1px solid #ff00ff; padding: 2px 4px; border-radius:3px; margin-left:5px; font-weight:700;">ADVISOR SELECT</span></div>
        <div class="tooltip-row"><span class="tooltip-label">Opponent</span><span class="tooltip-value">${p.opponent}</span></div>
        <div class="tooltip-row"><span class="tooltip-label">Salary</span><span class="tooltip-value">${p.salary} Coins</span></div>
        <div class="tooltip-row"><span class="tooltip-label">Season Avg</span><span class="tooltip-value">${p.fp_season_avg.toFixed(1)}</span></div>
        <div class="tooltip-row"><span class="tooltip-label">Opp. Rating</span><span class="tooltip-value" style="color: ${p.team_def_rating > 1.1 ? '#00ff88' : p.team_def_rating < 0.9 ? '#ff4444' : '#ffffff'}">${p.team_def_rating.toFixed(2)}</span></div>
        <div class="tooltip-row" style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.1)">
            <span class="tooltip-label">Boom Prob</span>
            <span class="tooltip-value" style="color: #00ccff">${p.BoomProbability.toFixed(0)}%</span>
        </div>
        <div class="tooltip-row">
            <span class="tooltip-label">Ceiling (Pts)</span>
            <span class="tooltip-value" style="color: #9f7aea">${(p.PredictedPoints || 0).toFixed(1)}</span>
        </div>
    `;
    
    setTimeout(() => {
        Plotly.restyle(gd, {
            'marker.line.color': [originalLineColors],
            'marker.line.width': [originalLineWidths],
            'marker.size': [originalSizes]
        }, [0]);
    }, 2000);
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
        
        const periodsByYear = {};
        available.forEach(item => {
            if (!periodsByYear[item.year]) periodsByYear[item.year] = [];
            periodsByYear[item.year].push(item.week);
        });

        const years = Object.keys(periodsByYear).sort((a, b) => b - a);
        
        yearSelect.innerHTML = '';
        years.forEach(year => {
            const option = document.createElement('option');
            option.value = year;
            option.textContent = year;
            yearSelect.appendChild(option);
        });

        function populateWeeks(year) {
            weekSelect.innerHTML = '';
            const weeks = periodsByYear[year].sort((a, b) => b - a);
            weeks.forEach(week => {
                const option = document.createElement('option');
                option.value = week;
                option.textContent = `Week ${week}`;
                weekSelect.appendChild(option);
            });
        }

        const defaultYear = years[0];
        populateWeeks(defaultYear);
        yearSelect.value = defaultYear;
        const defaultWeek = periodsByYear[defaultYear].sort((a, b) => b - a)[0];
        weekSelect.value = defaultWeek;

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

// Roster Tab Switch Listeners
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
        const rosterName = e.target.getAttribute('data-roster');
        renderRoster(rosterName);
    });
});

initDashboard();
