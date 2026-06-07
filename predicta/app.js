const positions = ["Attack", "Midfield", "SSDM", "Defensemen", "Faceoff", "Goalie"];
let activeRosterTab = "MC_EV";

const rosterDescriptions = {
    "MC_EV": "Optimizes the roster to get the highest average points. Best for consistent, safe performance.",
    "MC_Win_160": "Optimizes the roster to maximize the chance of scoring 160 or more points. Balances safety with some high-scoring potential.",
    "MC_Win_180": "Optimizes the roster to maximize the chance of scoring 180 or more points. Focuses heavily on high-scoring teammate combinations.",
    "MC_Ceil_90": "Optimizes the roster to maximize the highest possible potential score, ignoring the risk of a low score.",
    "Coulda": "<strong>COULDA</strong>: Retroactively solves the absolute best possible roster for this week based on actual fantasy points scored. Use this to compare how close predictions were to the ultimate ceiling."
};

function getCouldaSet() {
    const couldaSet = new Set();
    if (window.currentAdvisory && window.currentAdvisory.Coulda) {
        window.currentAdvisory.Coulda.forEach(p => {
            couldaSet.add(`${p.firstName.trim()} ${p.lastName.trim()}|${p.game_id}`);
        });
    }
    return couldaSet;
}

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
        const cacheBuster = `?t=${Date.now()}`;
        const [predRes, advRes] = await Promise.all([
            fetch(`predictions/${year}/${week}${cacheBuster}`),
            fetch(`advisory/${year}/${week}${cacheBuster}`).catch(err => {
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
        
        // Store predictions and advisory data globally first so renderPlot can access it for Coulda highlighting
        window.currentPredictions = data;
        window.currentAdvisory = advisoryData;

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

        // Pre-compute shared Y-axis range for SSDM and Defensemen so they're comparable
        const defPositions = ['SSDM', 'Defensemen'];
        const getMcEvVal = d => (d.mc_ev != null && d.mc_ev > 0) ? d.mc_ev : (d.fp_season_avg || 0);
        const defData = data.filter(d => defPositions.includes(d.subPosition));
        let defYRange = null;
        if (defData.length > 0) {
            const defEvs = defData.map(getMcEvVal);
            const defMin = Math.min(...defEvs);
            const defMax = Math.max(...defEvs);
            const defPad = (defMax - defMin) * 0.15 || 2;
            defYRange = [Math.max(0, defMin - defPad), defMax + defPad * 2];
        }

        // Render all plots
        renderQueue.forEach(item => {
            console.log(`Rendering ${item.pos} with ${item.data.length} players`);
            let displayTitle = item.pos;
            if (displayTitle === "SSDM") displayTitle = "SSDM/LSM";
            const lockedYRange = defPositions.includes(item.pos) ? defYRange : null;
            renderPlot(item.id, displayTitle, item.data, lockedYRange);
        });

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
            statusEl.textContent = '⚡ ERROR — data not loaded';
            statusEl.style.background = 'rgba(245, 101, 101, 0.12)';
            statusEl.style.color = '#f56565';
            statusEl.style.border = '1px solid rgba(245, 101, 101, 0.25)';
            statusEl.style.display = 'inline-block';
        }
    }
}

function renderPlot(targetId, title, data, yRange = null) {
    const x = data.map(d => d.salary);
    // Use mc_ev (Monte Carlo Expected Value) on Y-axis; fallback to season avg
    const getMcEv = d => (d.mc_ev != null && d.mc_ev > 0) ? d.mc_ev : (d.fp_season_avg || 0);

    const xMin = Math.min(...x);
    const xMax = Math.max(...x);
    const xPadding = (xMax - xMin) * 0.15 || 5;
    const medianSalary = x.length > 0 ? x.slice().sort((a,b) => a-b)[Math.floor(x.length/2)] : 10;

    const couldaSet = getCouldaSet();

    // Sort data by Coulda first (so they are processed first in overlap logic and are always labeled), then by star power
    const sortedData = [...data].sort((a, b) => {
        const aCoulda = couldaSet.has(`${a.firstName} ${a.lastName}|${a.game_id}`) ? 1 : 0;
        const bCoulda = couldaSet.has(`${b.firstName} ${b.lastName}|${b.game_id}`) ? 1 : 0;
        if (aCoulda !== bCoulda) {
            return bCoulda - aCoulda;
        }
        return b.fp_season_avg - a.fp_season_avg;
    });

    const sortedY = sortedData.map(getMcEv);
    const yMax = Math.max(...sortedY);
    const yMin = Math.min(...sortedY);
    const yPad = (yMax - yMin) * 0.15 || 2;
    const medianEV = sortedY.length > 0 ? [...sortedY].sort((a,b) => a-b)[Math.floor(sortedY.length/2)] : 15;

    // Use locked range if provided (for shared-axis position groups), else auto-scale to data
    const yAxisRange = yRange !== null ? yRange : [Math.max(0, yMin - yPad), yMax + yPad * 2];

    // For overlap detection use the actual axis range
    const yAxisMin = yAxisRange[0];
    const yAxisSpan = yAxisRange[1] - yAxisRange[0];
    const placed = [];
    const textLabels = sortedData.map((d, i) => {
        const xNorm = (d.salary - xMin) / (xMax - xMin || 1);
        const yNorm = (sortedY[i] - yAxisMin) / (yAxisSpan || 1);
        
        let overlap = false;
        for (let p of placed) {
            const dist = Math.sqrt(Math.pow(p.x - xNorm, 2) + Math.pow(p.y - yNorm, 2));
            if (dist < 0.07) {
                overlap = true;
                break;
            }
        }
        
        if (!overlap || couldaSet.has(`${d.firstName} ${d.lastName}|${d.game_id}`)) {
            placed.push({ x: xNorm, y: yNorm });
            return d.lastName;
        }
        return "";
    });

    // Custom marker line colors, widths, and text colors to highlight Coulda players in cyan (#00f0ff)
    const markerLineColors = sortedData.map(d => couldaSet.has(`${d.firstName} ${d.lastName}|${d.game_id}`) ? '#00f0ff' : '#161b22');
    const markerLineWidths = sortedData.map(d => couldaSet.has(`${d.firstName} ${d.lastName}|${d.game_id}`) ? 3 : 1);
    const textColors = sortedData.map(d => couldaSet.has(`${d.firstName} ${d.lastName}|${d.game_id}`) ? '#00f0ff' : 'rgba(255,255,255,0.7)');

    // Dot size: MC p90 (90th percentile ceiling from simulation), fallback to mc_ev * 1.5 or season avg
    const dotSizes = sortedData.map(d => {
        const p90 = d.mc_p90 || (d.mc_ev ? d.mc_ev * 1.5 : null) || d.fp_season_avg || 8;
        return Math.max(6, p90 * 0.55 + 4);
    });

    // Color by MC Std Dev (risk/volatility): green = safe floor, red = boom-or-bust
    const stdValues = sortedData.map(d => d.mc_std != null ? d.mc_std : 0);
    const stdMin = Math.max(0, Math.min(...stdValues));
    const stdMax = Math.max(...stdValues);


    const trace = {
        x: sortedData.map(d => d.salary),
        y: sortedY,
        mode: 'markers+text',
        text: textLabels,
        textfont: { family: 'Inter', size: 10, color: textColors },
        textposition: 'top center',
        hoverinfo: 'none',
        customdata: sortedData,
        marker: {
            size: dotSizes,
            color: stdValues,
            colorscale: [
                [0,   'rgb(26,152,80)'],
                [0.4, 'rgb(166,217,106)'],
                [0.6, 'rgb(255,255,191)'],
                [0.8, 'rgb(253,174,97)'],
                [1,   'rgb(215,48,39)']
            ],
            reversescale: false,
            cmin: stdMin,
            cmax: stdMax,
            showscale: true,
            colorbar: {
                title: { text: 'Risk (σ)', font: { color: '#8b949e', size: 11 } },
                thickness: 15,
                x: 1.1,
                tickfont: { color: '#8b949e' }
            },
            line: { color: markerLineColors, width: markerLineWidths },
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
            title: 'MC Expected Value (Pts)', 
            range: yAxisRange, 
            gridcolor: '#30363d', 
            zeroline: false 
        },
        margin: { t: 80, b: 80, l: 80, r: 100 },
        shapes: [
            { type: 'line', x0: medianSalary, x1: medianSalary, yref: 'paper', y0: 0, y1: 1, line: { color: 'rgba(255,255,255,0.1)', width: 1, dash: 'dash' } },
            { type: 'line', xref: 'paper', x0: 0, x1: 1, y0: medianEV, y1: medianEV, line: { color: 'rgba(255,255,255,0.1)', width: 1, dash: 'dash' } }
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
                <span class="tooltip-label">MC EV</span>
                <span class="tooltip-value" style="color: #00ccff">${(p.mc_ev != null ? p.mc_ev : 0).toFixed(1)} pts</span>
            </div>
            <div class="tooltip-row">
                <span class="tooltip-label">Risk (σ)</span>
                <span class="tooltip-value" style="color: ${p.mc_std > 20 ? '#ff4444' : p.mc_std > 12 ? '#fdae61' : '#6dbe6d'}">${(p.mc_std != null ? p.mc_std : 0).toFixed(1)}</span>
            </div>
            <div class="tooltip-row">
                <span class="tooltip-label">Boom Prob</span>
                <span class="tooltip-value" style="color: rgba(255,255,255,0.55)">${(p.BoomProbability || 0).toFixed(0)}%</span>
            </div>
            <div class="tooltip-row">
                <span class="tooltip-label">MC p90 (Ceil)</span>
                <span class="tooltip-value" style="color: #9f7aea">${(p.mc_p90 || 0).toFixed(1)} pts</span>
            </div>
            ${p.actualPoints !== undefined && p.actualPoints !== null ? `
            <div class="tooltip-row" style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.1)">
                <span class="tooltip-label" style="color: #00f0ff; font-weight: 700;">Actual Score</span>
                <span class="tooltip-value" style="color: #00f0ff; font-weight: 700;">${p.actualPoints.toFixed(1)} pts</span>
            </div>` : ''}
        `;
    });
}

function renderAdvisor(advisoryData) {
    window.currentAdvisory = advisoryData;
    
    // Manage display & layout columns of Coulda tab
    const couldaTab = document.getElementById('coulda-tab');
    const rosterTabsContainer = document.querySelector('.roster-tabs');
    if (couldaTab && rosterTabsContainer) {
        if (advisoryData.Coulda && advisoryData.Coulda.length > 0) {
            couldaTab.style.display = 'inline-block';
            rosterTabsContainer.style.gridTemplateColumns = 'repeat(5, 1fr)';
        } else {
            couldaTab.style.display = 'none';
            rosterTabsContainer.style.gridTemplateColumns = 'repeat(4, 1fr)';
            if (activeRosterTab === "Coulda") {
                activeRosterTab = "MC_EV";
            }
        }
    }

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

    const posMap = {
        "A": "Attack",
        "M": "Midfield",
        "D": "Defense",
        "FO": "Faceoff",
        "G": "Goalie",
        "Attack": "Attack",
        "Midfield": "Midfield",
        "Defense": "Defense",
        "Defensemen": "Defense",
        "SSDM": "Defense",
        "LSM": "Defense",
        "Faceoff": "Faceoff",
        "Goalie": "Goalie"
    };

    const posOrder = {
        "Attack": 0,
        "Midfield": 1,
        "Defense": 2,
        "Defensemen": 2,
        "SSDM": 2,
        "LSM": 2,
        "Faceoff": 3,
        "Goalie": 4
    };
    const sortedRoster = [...roster].sort((a, b) => {
        const aPos = posMap[a.position] || a.position;
        const bPos = posMap[b.position] || b.position;
        return (posOrder[aPos] ?? 99) - (posOrder[bPos] ?? 99);
    });

    const totalCost = roster.reduce((sum, p) => sum + p.salary, 0);
    const totalEV = roster.reduce((sum, p) => sum + p.EV, 0);
    const totalCeiling = roster.reduce((sum, p) => sum + (p.ceiling || 0), 0);
    const totalBoom = roster.reduce((sum, p) => sum + (p.boom || 0), 0);
    const totalActual = roster.reduce((sum, p) => sum + (p.actualPoints || 0), 0);

    const showBoom = (rosterName === "MC_Win_160" || rosterName === "MC_Win_180");
    
    let lastColHeader = "Ceil";
    if (rosterName === "Coulda") {
        lastColHeader = "Actual";
    } else if (showBoom) {
        lastColHeader = "Boom";
    }
    
    const avgBoom = totalBoom / roster.length;
    const couldaSet = getCouldaSet();
    const isCouldaTable = rosterName === "Coulda";

    const hasPlayed = window.currentAdvisory.Coulda && window.currentAdvisory.Coulda.length > 0;
    const showActualCol = hasPlayed && rosterName !== "Coulda";

    let html = `
        <div class="roster-desc">
            ${rosterDescriptions[rosterName] || ""}
        </div>
        <table class="roster-table ${isCouldaTable ? 'roster-table-coulda' : ''}">
            <thead>
                <tr>
                    <th>Slot</th>
                    <th>Player</th>
                    <th>Team</th>
                    <th>Cost</th>
                    <th>EV</th>
                    <th>${lastColHeader}</th>
                    ${showActualCol ? '<th style="color:#00f0ff;">Actual</th>' : ''}
                </tr>
            </thead>
            <tbody>
    `;

    sortedRoster.forEach(p => {
        const lookup = window.currentPredictions ? window.currentPredictions.find(item => item.firstName === p.firstName && item.lastName === p.lastName && item.game_id === p.game_id) : null;
        let badgePos = p.position;
        if (lookup) {
            badgePos = lookup.subPosition;
        } else {
            // fallback mapping for display
            const displayPosMap = {
                "A": "Attack",
                "M": "Midfield",
                "D": "Defensemen",
                "FO": "Faceoff",
                "G": "Goalie"
            };
            badgePos = displayPosMap[badgePos] || badgePos;
        }
        if (badgePos === "SSDM") badgePos = "SSDM/LSM";

        let lastColVal = "";
        if (rosterName === "Coulda") {
            lastColVal = p.actualPoints ? p.actualPoints.toFixed(1) : "-";
        } else if (showBoom) {
            lastColVal = p.boom ? p.boom.toFixed(0) + "%" : "-";
        } else {
            lastColVal = p.ceiling ? p.ceiling.toFixed(1) : "-";
        }

        const isCouldaPlayer = couldaSet.has(`${p.firstName} ${p.lastName}|${p.game_id}`);
        const highlightClass = (isCouldaPlayer && rosterName !== "Coulda") ? "coulda-highlight" : "";

        let actualColHtml = "";
        if (showActualCol) {
            actualColHtml = `<td style="color:#00f0ff; font-weight:700;">${p.actualPoints !== undefined ? p.actualPoints.toFixed(1) : "-"}</td>`;
        }

        html += `
            <tr class="roster-row ${highlightClass}" onclick="highlightPlayerInPlot('${lookup ? lookup.subPosition : p.position}', '${p.firstName}', '${p.lastName}', '${p.game_id}')" title="Click to highlight on chart">
                <td><span class="roster-pos-badge">${badgePos}</span></td>
                <td><strong>${p.lastName}</strong>, ${p.firstName[0]}.</td>
                <td><span style="font-weight:700;">${p.team}</span> <span style="font-size:0.6rem; color:#8b949e">@ ${p.opponent}</span></td>
                <td>${p.salary}</td>
                <td>${p.EV.toFixed(1)}</td>
                <td>${lastColVal}</td>
                ${actualColHtml}
            </tr>
        `;
    });

    let lastColTotal = "";
    if (rosterName === "Coulda") {
        lastColTotal = totalActual.toFixed(1);
    } else if (showBoom) {
        lastColTotal = avgBoom.toFixed(0) + "% (avg)";
    } else {
        lastColTotal = totalCeiling.toFixed(1);
    }

    let actualTotalHtml = "";
    if (showActualCol) {
        const totalActualRoster = roster.reduce((sum, item) => sum + (item.actualPoints || 0), 0);
        actualTotalHtml = `<td style="color:#00f0ff; font-weight:700;">${totalActualRoster.toFixed(1)}</td>`;
    }

    html += `
                <tr class="roster-total-row">
                    <td colspan="3">Total</td>
                    <td>${totalCost}</td>
                    <td>${totalEV.toFixed(1)}</td>
                    <td>${lastColTotal}</td>
                    ${actualTotalHtml}
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

function highlightPlayerInPlot(position, firstName, lastName, gameId) {
    let displayPos = position;
    if (position === "SSDM" || position === "LSM") {
        displayPos = "SSDM";
    } else if (position === "Defense" || position === "Defensemen" || position === "D") {
        displayPos = "Defensemen";
    } else if (position === "A" || position === "Attack") {
        displayPos = "Attack";
    } else if (position === "M" || position === "Midfield") {
        displayPos = "Midfield";
    } else if (position === "FO" || position === "Faceoff") {
        displayPos = "Faceoff";
    } else if (position === "G" || position === "Goalie") {
        displayPos = "Goalie";
    }
    
    const plotId = `plot-${displayPos}`;
    const plotEl = document.getElementById(plotId);
    if (!plotEl) return;
    
    const gd = plotEl;
    if (!gd.data || gd.data.length === 0) return;
    
    const customdata = gd.data[0].customdata;
    const ptIdx = customdata.findIndex(p => p.firstName === firstName && p.lastName === lastName && (!gameId || p.game_id === gameId));
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
            <span class="tooltip-label">MC EV</span>
            <span class="tooltip-value" style="color: #00ccff">${(p.mc_ev != null ? p.mc_ev : 0).toFixed(1)} pts</span>
        </div>
        <div class="tooltip-row">
            <span class="tooltip-label">Risk (σ)</span>
            <span class="tooltip-value" style="color: ${p.mc_std > 20 ? '#ff4444' : p.mc_std > 12 ? '#fdae61' : '#6dbe6d'}">${(p.mc_std != null ? p.mc_std : 0).toFixed(1)}</span>
        </div>
        <div class="tooltip-row">
            <span class="tooltip-label">Boom Prob</span>
            <span class="tooltip-value" style="color: rgba(255,255,255,0.55)">${(p.BoomProbability || 0).toFixed(0)}%</span>
        </div>
        <div class="tooltip-row">
            <span class="tooltip-label">MC p90 (Ceil)</span>
            <span class="tooltip-value" style="color: #9f7aea">${(p.mc_p90 || 0).toFixed(1)} pts</span>
        </div>
        ${p.actualPoints !== undefined && p.actualPoints !== null ? `
        <div class="tooltip-row" style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(255,255,255,0.1)">
            <span class="tooltip-label" style="color: #00f0ff; font-weight: 700;">Actual Score</span>
            <span class="tooltip-value" style="color: #00f0ff; font-weight: 700;">${p.actualPoints.toFixed(1)} pts</span>
        </div>` : ''}
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
        const response = await fetch(`predictions/available?t=${Date.now()}`);
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
            statusEl.textContent = '⚡ ERROR — data not loaded';
            statusEl.style.background = 'rgba(245, 101, 101, 0.12)';
            statusEl.style.color = '#f56565';
            statusEl.style.border = '1px solid rgba(245, 101, 101, 0.25)';
            statusEl.style.display = 'inline-block';
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
