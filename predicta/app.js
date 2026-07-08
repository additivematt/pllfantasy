const positions = ["Attack", "Midfield", "SSDM", "Defensemen", "Faceoff", "Goalie"];
let activeRosterTab = "MC_EV";

const rosterDescriptions = {
    "MC_EV": "Optimizes the roster to get the highest average points. Best for consistent, safe performance.",
    "MC_Win_160": "Optimizes the roster to maximize the chance of scoring 160 or more points. Balances safety with some high-scoring potential.",
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
    const rosterContainer = document.getElementById('roster-container');
    if (rosterContainer) rosterContainer.innerHTML = '<div class="muted-text" style="padding: 1rem 0;">Solving optimal rosters...</div>';

    try {
        const cacheBuster = `?t=${Date.now()}`;
        const [predRes, advRes, conRes] = await Promise.all([
            fetch(`predictions/${year}/${week}${cacheBuster}`),
            fetch(`advisory/${year}/${week}${cacheBuster}`).catch(err => {
                console.warn('Advisory fetch failed:', err);
                return null;
            }),
            fetch(`advisory/week${week}_${year}_consensus_ownership.json${cacheBuster}`).catch(err => {
                console.warn('Consensus fetch failed:', err);
                return null;
            })
        ]);

        if (!predRes.ok) throw new Error(`Predictions not found for Year ${year} Week ${week}.`);
        const data = await predRes.json();
        
        let advisoryData = null;
        if (advRes && advRes.ok) {
            advisoryData = await advRes.json();
        }
        
        let consensusData = null;
        if (conRes && conRes.ok) {
            consensusData = await conRes.json();
        }
        window.currentConsensus = consensusData;

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
            if (advisoryData.RecommendedStrategy) {
                activeRosterTab = advisoryData.RecommendedStrategy;
            }
            renderAdvisor(advisoryData);
        } else {
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
        
        const maxCeiling = Math.max(...sortedData.map(d => d.mc_p90 || 0), 1);
        const floor = p.mc_p10 != null ? p.mc_p10 : 0.0;
        const ceiling = p.mc_p90 != null ? p.mc_p90 : 0.0;
        const ev = p.mc_ev != null ? p.mc_ev : 0.0;
        const p10Pct = (floor / maxCeiling) * 100;
        const fillWidthPct = ((ceiling - floor) / maxCeiling) * 100;
        const evPct = (ev / maxCeiling) * 100;

        tooltip.innerHTML = `
            <div class="tooltip-header">${p.firstName} ${p.lastName} <span style="font-size:0.75rem; color:#8b949e; font-weight:normal; float:right; margin-top:4px;">${p.team} - ${p.position || p.positionGroup}</span></div>
            <div class="tooltip-grid">
                <div class="tooltip-row"><span class="tooltip-label">Opponent</span><span class="tooltip-value">${p.opponent}</span></div>
                <div class="tooltip-row"><span class="tooltip-label">Opp. Rating</span><span class="tooltip-value" style="color: ${p.team_def_rating > 1.1 ? '#00ff88' : p.team_def_rating < 0.9 ? '#ff4444' : '#ffffff'}">${(p.team_def_rating || 1.0).toFixed(2)}</span></div>
                <div class="tooltip-row"><span class="tooltip-label">Salary</span><span class="tooltip-value">${p.salary} Coins</span></div>
                <div class="tooltip-row"><span class="tooltip-label">Risk (σ)</span><span class="tooltip-value" style="color: ${p.mc_std > 20 ? '#ff4444' : p.mc_std > 12 ? '#fdae61' : '#6dbe6d'}">${(p.mc_std != null ? p.mc_std : 0).toFixed(1)}</span></div>
                <div class="tooltip-row"><span class="tooltip-label">Season Avg</span><span class="tooltip-value">${(p.fp_season_avg || 0).toFixed(1)}</span></div>
                <div class="tooltip-row"><span class="tooltip-label">Boom Prob</span><span class="tooltip-value" style="color: rgba(255,255,255,0.55)">${(p.BoomProbability || 0).toFixed(0)}%</span></div>
            </div>
            <div class="range-bar-section">
                <div class="range-bar-title">MC Projections Range (EV: <span style="color:#00ffff">${ev.toFixed(1)}</span> pts)</div>
                <div class="range-bar-container">
                    <div class="range-bar-track"></div>
                    <div class="range-bar-fill" style="left: ${p10Pct}%; width: ${fillWidthPct}%;"></div>
                    <div class="range-bar-dot" style="left: ${evPct}%;"></div>
                </div>
                <div class="range-bar-labels">
                    <span>Floor (p10): <span class="range-bar-val">${floor.toFixed(1)}</span></span>
                    <span>Ceiling (p90): <span class="range-bar-val">${ceiling.toFixed(1)}</span></span>
                </div>
            </div>
            ${p.actualPoints !== undefined && p.actualPoints !== null ? `
            <div class="tooltip-row" style="margin-top: 0.6rem; padding-top: 0.6rem; border-top: 1px solid rgba(255, 255, 255, 0.08)">
                <span class="tooltip-label" style="color: #00f0ff; font-weight: 700;">Actual Score</span>
                <span class="tooltip-value" style="color: #00f0ff; font-weight: 700;">${p.actualPoints.toFixed(1)} pts</span>
            </div>` : ''}
        `;
    });
}

function renderAdvisor(advisoryData) {
    window.currentAdvisory = advisoryData;
    
    // Rebuild roster tabs dynamically
    const rosterTabsContainer = document.querySelector('.roster-tabs');
    if (rosterTabsContainer) {
        rosterTabsContainer.innerHTML = '';
        
        // Define display names
        const labelMap = {
            "MC_EV": "MC EV",
            "MC_Win_160": "MC WIN 160",
            "MC_Ceil_90": "MC CEIL 90",
            "MC_Consensus": "MC CONSENSUS",
            "MC_Differential": "MC DIFFERENTIAL"
        };
        
        // Find all available roster keys in advisoryData
        const availableRosters = [];
        const order = ["MC_EV", "MC_Win_160", "MC_Ceil_90", "MC_Consensus", "MC_Differential"];
        for (const k of order) {
            if (advisoryData[k] && advisoryData[k].length > 0) {
                availableRosters.push({ key: k, label: labelMap[k] || k });
            }
        }
        
        // Add Coulda if present
        if (advisoryData.Coulda && advisoryData.Coulda.length > 0) {
            availableRosters.push({ key: "Coulda", label: "COULDA" });
        }
        
        availableRosters.forEach(r => {
            const btn = document.createElement('button');
            btn.className = 'tab-btn';
            if (r.key === activeRosterTab) {
                btn.classList.add('active');
            }
            btn.setAttribute('data-roster', r.key);
            
            if (r.key === advisoryData.RecommendedStrategy) {
                btn.innerHTML = `${r.label} <span class="rec-star" style="color: #ecc94b; margin-left: 2px;">⭐</span>`;
                btn.setAttribute('title', `Recommended: ${advisoryData.RecommendedReason}`);
            } else {
                btn.textContent = r.label;
            }
            
            btn.addEventListener('click', (e) => {
                let target = e.target;
                if (target.tagName === 'SPAN') {
                    target = target.parentElement;
                }
                const rName = target.getAttribute('data-roster');
                renderRoster(rName);
            });
            rosterTabsContainer.appendChild(btn);
        });
        
        // If our activeRosterTab is no longer in the list, fall back to first
        if (!availableRosters.some(r => r.key === activeRosterTab) && availableRosters.length > 0) {
            activeRosterTab = availableRosters[0].key;
        }
    }



    // 2.5 Render Roster Insights Narrative
    const insightsSection = document.getElementById('roster-insights-section');
    const insightsContainer = document.getElementById('roster-insights-container');
    if (insightsSection && insightsContainer) {
        insightsContainer.innerHTML = '';
        if (advisoryData) {
            insightsSection.style.display = 'block';
            
            const rostersToInspect = ["MC_EV", "MC_Win_160", "MC_Ceil_90"];
            const uniquePlayers = new Map();

            rostersToInspect.forEach(rKey => {
                const roster = advisoryData[rKey];
                if (roster) {
                    roster.forEach(p => {
                        const fullName = `${p.firstName} ${p.lastName}`;
                        if (!uniquePlayers.has(fullName)) {
                            uniquePlayers.set(fullName, {
                                firstName: p.firstName,
                                lastName: p.lastName,
                                position: p.position,
                                salary: p.salary,
                                team: p.team,
                                opponent: p.opponent,
                                game_id: p.game_id,
                                rosters: [rKey]
                            });
                        } else {
                            uniquePlayers.get(fullName).rosters.push(rKey);
                        }
                    });
                }
            });

            // Convert map to sorted array
            const sortedPlayers = Array.from(uniquePlayers.values()).sort((a, b) => {
                if (b.rosters.length !== a.rosters.length) {
                    return b.rosters.length - a.rosters.length;
                }
                return b.salary - a.salary;
            });

            if (sortedPlayers.length > 0) {
                let tableHtml = `
                    <table class="insights-table">
                        <thead>
                            <tr>
                                <th>Player</th>
                                <th>Rosters</th>
                                <th>Rationale</th>
                            </tr>
                        </thead>
                        <tbody>
                `;

                sortedPlayers.forEach(p => {
                    const fullName = `${p.firstName} ${p.lastName}`;
                    
                    // Build badges
                    let badgesHtml = '';
                    if (p.rosters.includes("MC_EV")) {
                        badgesHtml += `<span class="insight-badge ev" title="MC Expected Value">EV</span>`;
                    }
                    if (p.rosters.includes("MC_Win_160")) {
                        badgesHtml += `<span class="insight-badge win160" title="MC Win 160">160</span>`;
                    }
                    if (p.rosters.includes("MC_Ceil_90")) {
                        badgesHtml += `<span class="insight-badge ceil" title="MC Ceiling 90">Ceil</span>`;
                    }

                    // Resolve whyIncluded
                    let rationale = '';
                    const recPlayer = advisoryData.Narrative && advisoryData.Narrative.RecommendedRoster ? advisoryData.Narrative.RecommendedRoster.find(rp => rp.firstName === p.firstName && rp.lastName === p.lastName) : null;
                    if (recPlayer && recPlayer.bullets && recPlayer.bullets.length > 0) {
                        rationale = recPlayer.bullets.map(b => {
                            if (b.includes(":")) {
                                const index = b.indexOf(":");
                                const tag = b.substring(0, index);
                                const rest = b.substring(index);
                                return `<strong>${tag}</strong>${rest}`;
                            }
                            return b;
                        }).join(" ");
                    } else {
                        // Look up in variants
                        const matchingVariants = (advisoryData.Narrative && advisoryData.Narrative.Variants || []).filter(v => v.in && v.in.includes(fullName));
                        if (matchingVariants.length > 0) {
                            rationale = matchingVariants.map(v => {
                                if (v.strategy === "MC_Win_160") {
                                    return "<strong>Roster Swap:</strong> Swapped in for higher floor stability.";
                                } else if (v.strategy === "MC_Ceil_90") {
                                    return "<strong>Roster Swap:</strong> Swapped in for higher ceiling upside.";
                                }
                                return `<strong>Roster Swap:</strong> ${v.rationale}`;
                            }).join(" ");
                        } else {
                            rationale = "Included to satisfy lineup budget and position optimization constraints.";
                        }
                    }

                    tableHtml += `
                        <tr class="insight-table-row" onclick="highlightPlayerInPlot('${p.position}', '${p.firstName}', '${p.lastName}')" title="Click to highlight on chart">
                            <td class="insight-player-cell">
                                <span class="insight-player-name"><strong>${p.lastName}</strong>, ${p.firstName[0]}.</span><br/>
                                <span class="insight-player-meta">${p.position} | ${p.salary}c</span>
                            </td>
                            <td class="insight-badges-cell">${badgesHtml}</td>
                            <td class="insight-rationale-cell">${rationale}</td>
                        </tr>
                    `;
                });

                tableHtml += `
                        </tbody>
                    </table>
                `;
                
                insightsContainer.innerHTML = tableHtml;
            } else {
                insightsContainer.innerHTML = '<span class="muted-text">No roster insights available.</span>';
            }
        } else {
            insightsSection.style.display = 'none';
        }
    }
    
    // 2.7 Render Tactical Advisory
    const tacticalSection = document.getElementById('tactical-advice-section');
    const tacticalContainer = document.getElementById('tactical-advice-container');
    if (tacticalSection && tacticalContainer) {
        tacticalContainer.innerHTML = '';
        if (advisoryData.TacticalAdvice && 
            ((advisoryData.TacticalAdvice.FloorLocks && advisoryData.TacticalAdvice.FloorLocks.length > 0) ||
             (advisoryData.TacticalAdvice.DifferentialLeverage && advisoryData.TacticalAdvice.DifferentialLeverage.length > 0) ||
             (advisoryData.TacticalAdvice.Rivals && advisoryData.TacticalAdvice.Rivals.length > 0))) {
            
            tacticalSection.style.display = 'block';
            renderTacticalAdvice(advisoryData.TacticalAdvice);
        } else {
            tacticalSection.style.display = 'none';
        }
    }
    
    // 3. Render Roster
    renderRoster(activeRosterTab);
}

function renderTacticalAdvice(tacticalData) {
    const container = document.getElementById('tactical-advice-container');
    if (!container) return;

    let totalRivals = 3;
    if (window.currentConsensus && window.currentConsensus.local_league_rosters) {
        const rosters = window.currentConsensus.local_league_rosters;
        const keys = Object.keys(rosters);
        let activeCount = 0;
        keys.forEach(k => {
            if (rosters[k].players && rosters[k].players.length > 0) {
                activeCount++;
            }
        });
        totalRivals = activeCount > 0 ? activeCount : keys.length;
    }

    const players = [];
    if (tacticalData.FloorLocks) {
        tacticalData.FloorLocks.forEach(p => {
            players.push({
                ...p,
                type: 'lock',
                label: 'LOCK',
                badgeClass: 'insight-badge ev' // green
            });
        });
    }
    if (tacticalData.DifferentialLeverage) {
        tacticalData.DifferentialLeverage.forEach(p => {
            players.push({
                ...p,
                type: 'diff',
                label: 'LEVERAGE',
                badgeClass: 'insight-badge ceil' // purple
            });
        });
    }

    let html = '<div class="tactical-container">';

    if (players.length > 0) {
        html += `
            <table class="insights-table">
                <thead>
                    <tr>
                        <th>Player</th>
                        <th>Type</th>
                        <th>Stats</th>
                        <th>Advisory</th>
                    </tr>
                </thead>
                <tbody>
        `;

        players.forEach(p => {
            // Lookup player in currentPredictions to get team and salary info
            const lookup = window.currentPredictions ? window.currentPredictions.find(item => item.firstName === p.firstName && item.lastName === p.lastName) : null;
            const salary = lookup ? lookup.salary : '';
            const displayPosMap = {
                "Attack": "Attack",
                "Midfield": "Midfield",
                "Defense": "Defense",
                "FO": "Faceoff",
                "Faceoff": "Faceoff",
                "G": "Goalie",
                "Goalie": "Goalie"
            };
            const posLabel = displayPosMap[p.position] || p.position;

            let statsBadges = `
                <span class="insight-badge ev" style="margin-bottom: 2px;">G: ${p.globalRate}%</span><br/>
                <span class="insight-badge ${p.rivalCount > 0 ? 'win160' : 'ceil'}">R: ${p.rivalCount}/${totalRivals}</span>
            `;

            html += `
                <tr class="insight-table-row" onclick="highlightPlayerInPlot('${lookup ? lookup.subPosition : p.position}', '${p.firstName}', '${p.lastName}')" title="Click to highlight on chart">
                    <td class="insight-player-cell">
                        <span class="insight-player-name"><strong>${p.lastName}</strong>, ${p.firstName[0]}.</span><br/>
                        <span class="insight-player-meta">${posLabel} ${salary ? `| ${salary}c` : ''}</span>
                    </td>
                    <td class="insight-badges-cell">
                        <span class="${p.badgeClass}">${p.label}</span>
                    </td>
                    <td class="insight-badges-cell" style="min-width: 65px;">
                        ${statsBadges}
                    </td>
                    <td class="insight-rationale-cell" style="line-height: 1.35;">
                        ${p.description}
                    </td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;
    } else {
        html += '<span class="muted-text">No floor locks or differential leverage plays identified.</span>';
    }

    html += '</div>';
    container.innerHTML = html;

    // Render Rival Radar under rosters table
    renderRivalRadar(tacticalData.Rivals);
}

function renderRivalRadar(rivals) {
    const container = document.getElementById('rival-radar-container');
    if (!container) return;

    if (!rivals || rivals.length === 0) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'block';
    let html = `
        <div style="margin-bottom: 0.5rem; font-size: 0.75rem; font-weight: 700; color: #8b949e; letter-spacing: 0.5px; text-transform: uppercase;">📡 Rival Radar</div>
        <div class="rival-radar-card">
            <table class="rival-table">
                <thead>
                    <tr>
                        <th width="30%">Rival</th>
                        <th width="70%">Roster selections</th>
                    </tr>
                </thead>
                <tbody>
    `;

    rivals.forEach(rival => {
        html += `
            <tr>
                <td class="rival-name-cell">
                    ${rival.teamName}<br/>
                    <span style="font-size: 0.6rem; color: #8b949e;">#${rival.rank} (${rival.points.toFixed(1)} pts)</span>
                </td>
                <td class="rival-roster-cell">${rival.roster}</td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        </div>
    `;
    container.innerHTML = html;
}

function getPlayerOwnership(firstName, lastName) {
    const res = { globalRate: 0, rivalCount: 0, totalRivals: 0 };
    if (!window.currentConsensus) return res;

    const cleanName = (firstName + lastName).replace(/['\-\. ]/g, '').toLowerCase();

    // 1. Get global ownership
    if (window.currentConsensus.global_top_25) {
        const item = window.currentConsensus.global_top_25.find(c => c.clean_name === cleanName);
        if (item) {
            res.globalRate = Math.round(item.rate * 100);
        }
    }

    // 2. Get local rival ownership count
    if (window.currentConsensus.local_league_rosters) {
        const rivalRosters = window.currentConsensus.local_league_rosters;
        const keys = Object.keys(rivalRosters);
        
        let totalActiveRivals = 0;
        let count = 0;
        keys.forEach(k => {
            const players = rivalRosters[k].players || [];
            if (players.length > 0) {
                totalActiveRivals++;
                const hasPlayer = players.some(pName => {
                    const pClean = pName.replace(/['\-\. ]/g, '').toLowerCase();
                    return pClean === cleanName;
                });
                if (hasPlayer) {
                    count++;
                }
            }
        });
        res.totalRivals = totalActiveRivals;
        res.rivalCount = count;
    }

    return res;
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
    const totalEV = roster.reduce((sum, p) => sum + (p.mc_ev || 0), 0);
    const totalCeiling = roster.reduce((sum, p) => sum + (p.mc_p90 || 0), 0);
    const totalActual = roster.reduce((sum, p) => sum + (p.actualPoints || 0), 0);

    const couldaSet = getCouldaSet();
    const isCouldaTable = rosterName === "Coulda";
    const hasPlayed = window.currentAdvisory.Coulda && window.currentAdvisory.Coulda.length > 0;

    // Determine conditional columns: Omit MC p90 for MC_Consensus and MC_Differential
    const showCeiling = (rosterName !== "MC_Consensus" && rosterName !== "MC_Differential");
    
    let extraHeaderHtml = "";
    if (rosterName === "MC_Consensus") {
        extraHeaderHtml = '<th style="text-align: right;">Global %</th>';
    } else if (rosterName === "MC_Differential") {
        extraHeaderHtml = '<th style="text-align: right;">Rivals</th>';
    }

    let html = `
        <div class="roster-desc">
            ${rosterDescriptions[rosterName] || ""}
        </div>
    `;

    if (rosterName === window.currentAdvisory.RecommendedStrategy) {
        html += `
            <div class="roster-rec-badge">
                <span class="rec-icon">⭐</span>
                <span class="rec-reason"><strong>Recommended Strategy:</strong> ${window.currentAdvisory.RecommendedReason}</span>
            </div>
        `;
    }

    html += `
        <table class="roster-table ${isCouldaTable ? 'roster-table-coulda' : ''}">
            <thead>
                <tr>
                    <th>Slot</th>
                    <th>Player</th>
                    <th>Team</th>
                    <th>Cost</th>
                    <th>MC EV</th>
                    ${showCeiling ? '<th>MC p90</th>' : ''}
                    ${extraHeaderHtml}
                    ${hasPlayed ? '<th style="color:#00f0ff;">Actual</th>' : ''}
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

        const isCouldaPlayer = couldaSet.has(`${p.firstName} ${p.lastName}|${p.game_id}`);
        const highlightClass = (isCouldaPlayer && rosterName !== "Coulda") ? "coulda-highlight" : "";

        let actualColHtml = "";
        if (hasPlayed) {
            actualColHtml = `<td style="color:#00f0ff; font-weight:700;">${p.actualPoints !== undefined ? p.actualPoints.toFixed(1) : "-"}</td>`;
        }

        let p90ColHtml = "";
        if (showCeiling) {
            p90ColHtml = `<td>${(p.mc_p90 || 0).toFixed(1)}</td>`;
        }

        let extraColHtml = "";
        if (rosterName === "MC_Consensus") {
            const own = getPlayerOwnership(p.firstName, p.lastName);
            extraColHtml = `<td style="text-align: right; font-weight:700; color: #b794f4;">${own.globalRate}%</td>`;
        } else if (rosterName === "MC_Differential") {
            const own = getPlayerOwnership(p.firstName, p.lastName);
            extraColHtml = `<td style="text-align: right; font-weight:700; color: #9f7aea;">${own.rivalCount}/${own.totalRivals || 3}</td>`;
        }

        html += `
            <tr class="roster-row ${highlightClass}" onclick="highlightPlayerInPlot('${lookup ? lookup.subPosition : p.position}', '${p.firstName}', '${p.lastName}', '${p.game_id}')" title="Click to highlight on chart">
                <td><span class="roster-pos-badge">${badgePos}</span></td>
                <td><strong>${p.lastName}</strong>, ${p.firstName[0]}.</td>
                <td><span style="font-weight:700;">${p.team}</span> <span style="font-size:0.6rem; color:#8b949e">@ ${p.opponent}</span></td>
                <td>${p.salary}</td>
                <td>${(p.mc_ev || 0).toFixed(1)}</td>
                ${p90ColHtml}
                ${extraColHtml}
                ${actualColHtml}
            </tr>
        `;
    });

    let actualTotalHtml = "";
    if (hasPlayed) {
        actualTotalHtml = `<td style="color:#00f0ff; font-weight:700;">${totalActual.toFixed(1)}</td>`;
    }

    let p90TotalHtml = "";
    if (showCeiling) {
        p90TotalHtml = `<td>${totalCeiling.toFixed(1)}</td>`;
    }

    let extraTotalHtml = "";
    if (rosterName === "MC_Consensus" || rosterName === "MC_Differential") {
        extraTotalHtml = `<td></td>`;
    }

    html += `
                <tr class="roster-total-row">
                    <td colspan="3">Total</td>
                    <td>${totalCost}</td>
                    <td>${totalEV.toFixed(1)}</td>
                    ${p90TotalHtml}
                    ${extraTotalHtml}
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
    
    const maxCeiling = Math.max(...customdata.map(d => d.mc_p90 || 0), 1);
    const floor = p.mc_p10 != null ? p.mc_p10 : 0.0;
    const ceiling = p.mc_p90 != null ? p.mc_p90 : 0.0;
    const ev = p.mc_ev != null ? p.mc_ev : 0.0;
    const p10Pct = (floor / maxCeiling) * 100;
    const fillWidthPct = ((ceiling - floor) / maxCeiling) * 100;
    const evPct = (ev / maxCeiling) * 100;

    tooltip.innerHTML = `
        <div class="tooltip-header">${p.firstName} ${p.lastName} <span style="font-size:0.65rem; color: #ff00ff; border: 1px solid #ff00ff; padding: 2px 4px; border-radius:3px; float:right; margin-top:3px; font-weight:700;">ADVISOR SELECT</span></div>
        <div class="tooltip-grid">
            <div class="tooltip-row"><span class="tooltip-label">Opponent</span><span class="tooltip-value">${p.opponent}</span></div>
            <div class="tooltip-row"><span class="tooltip-label">Opp. Rating</span><span class="tooltip-value" style="color: ${p.team_def_rating > 1.1 ? '#00ff88' : p.team_def_rating < 0.9 ? '#ff4444' : '#ffffff'}">${(p.team_def_rating || 1.0).toFixed(2)}</span></div>
            <div class="tooltip-row"><span class="tooltip-label">Salary</span><span class="tooltip-value">${p.salary} Coins</span></div>
            <div class="tooltip-row"><span class="tooltip-label">Risk (σ)</span><span class="tooltip-value" style="color: ${p.mc_std > 20 ? '#ff4444' : p.mc_std > 12 ? '#fdae61' : '#6dbe6d'}">${(p.mc_std != null ? p.mc_std : 0).toFixed(1)}</span></div>
            <div class="tooltip-row"><span class="tooltip-label">Season Avg</span><span class="tooltip-value">${(p.fp_season_avg || 0).toFixed(1)}</span></div>
            <div class="tooltip-row"><span class="tooltip-label">Boom Prob</span><span class="tooltip-value" style="color: rgba(255,255,255,0.55)">${(p.BoomProbability || 0).toFixed(0)}%</span></div>
        </div>
        <div class="range-bar-section">
            <div class="range-bar-title">MC Projections Range (EV: <span style="color:#00ffff">${ev.toFixed(1)}</span> pts)</div>
            <div class="range-bar-container">
                <div class="range-bar-track"></div>
                <div class="range-bar-fill" style="left: ${p10Pct}%; width: ${fillWidthPct}%;"></div>
                <div class="range-bar-dot" style="left: ${evPct}%;"></div>
            </div>
            <div class="range-bar-labels">
                <span>Floor (p10): <span class="range-bar-val">${floor.toFixed(1)}</span></span>
                <span>Ceiling (p90): <span class="range-bar-val">${ceiling.toFixed(1)}</span></span>
            </div>
        </div>
        ${p.actualPoints !== undefined && p.actualPoints !== null ? `
        <div class="tooltip-row" style="margin-top: 0.6rem; padding-top: 0.6rem; border-top: 1px solid rgba(255, 255, 255, 0.08)">
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

        const PLAYOFF_WEEKS = {
            2024: { 12: 'QF', 13: 'SF', 14: 'Final' },
            2025: { 12: 'QF', 13: 'SF', 14: 'Final' },
            2026: { 13: 'QF', 14: 'SF', 15: 'Final' }
        };

        function populateWeeks(year) {
            weekSelect.innerHTML = '';
            const weeks = periodsByYear[year].sort((a, b) => b - a);
            weeks.forEach(week => {
                const option = document.createElement('option');
                option.value = week;
                
                const playoffLabel = PLAYOFF_WEEKS[year]?.[week];
                let displayLabel = `Week ${week}`;
                if (playoffLabel) {
                    displayLabel = `Week ${week} (${playoffLabel})`;
                }
                
                option.textContent = displayLabel;
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
