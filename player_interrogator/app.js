const TEAM_NAMES = {
    'ARC': 'Utah Archers',
    'OUT': 'Denver Outlaws',
    'RED': 'California Redwoods',
    'ATL': 'New York Atlas',
    'CHA': 'Carolina Chaos',
    'WHP': 'Maryland Whipsnakes',
    'WAT': 'Philadelphia Waterdogs',
    'CAN': 'Boston Cannons',
    'MDW': 'Maryland Whipsnakes',
    'NYA': 'New York Atlas',
    'PHI': 'Philadelphia Waterdogs',
    'BOS': 'Boston Cannons',
    'CAL': 'California Redwoods',
    'DEN': 'Denver Outlaws',
    'UTA': 'Utah Archers',
    'CAR': 'Carolina Chaos'
};

function getEventLabel(eventId, week) {
    const id = eventId.toLowerCase();
    if (id.includes('semifinal')) return 'SF';
    if (id.includes('quarterfinal')) return 'QF';
    if (id.includes('championship') || id.includes('final')) return 'Final';
    if (id.includes('allstar') || id.includes('all-star')) return 'ASG';
    if (week) return 'W' + week;
    const match = eventId.match(/game[-_](\d+)/);
    if (match) {
        const gameNum = parseInt(match[1]);
        if (gameNum <= 20) return 'W' + Math.ceil(gameNum / 4);
        return 'W' + (Math.ceil(gameNum / 4) + 1);
    }
    return eventId.split('_')[0];
}

function formatPoints(val) {
    if (val === null || val === undefined) return '-';
    const rounded = Math.round(val * 10) / 10;
    return Number.isInteger(rounded) ? rounded.toString() : rounded.toFixed(1);
}

function normalizeTeamCode(code) {
    if (!code) return code;
    const mapping = {
        'BOS': 'CAN',
        'MDW': 'WHP',
        'UTA': 'ARC',
        'NYA': 'ATL',
        'CAR': 'CHA',
        'DEN': 'OUT',
        'CAL': 'RED',
        'PHI': 'WAT'
    };
    return mapping[code.toUpperCase()] || code.toUpperCase();
}

let allPlayersStats = null;
let currentPlayerData = null;
let chart = null;

async function init() {
    try {
        const response = await fetch('all_players_stats.json');
        allPlayersStats = await response.json();
        
        // Ensure stats are sorted chronologically by event startTime for each player
        for (const slug in allPlayersStats) {
            if (allPlayersStats[slug].stats) {
                allPlayersStats[slug].stats.sort((a, b) => {
                    const timeA = parseInt(a.event?.startTime || 0);
                    const timeB = parseInt(b.event?.startTime || 0);
                    return timeA - timeB;
                });
            }
        }
        
        setupEventListeners();
        populatePlayerList();
        
        // Default to Jeff Teat if available
        const search = document.getElementById('playerSearch');
        if (allPlayersStats['jeff-teat']) {
            search.value = 'jeff-teat';
        } else if (search.options.length > 1) {
            search.selectedIndex = 1;
        }
        
        updateDashboard();
    } catch (error) {
        console.error("Failed to load data:", error);
        const statusEl = document.getElementById('cacheStatus');
        if (statusEl) {
            statusEl.textContent = '⚡ OFFLINE — data not loaded';
            statusEl.style.background = 'rgba(245, 101, 101, 0.12)';
            statusEl.style.color = '#f56565';
            statusEl.style.border = '1px solid rgba(245, 101, 101, 0.25)';
        }
    }
}

function setupEventListeners() {
    ['teamFilter', 'posFilter', 'activeOnly'].forEach(id => {
        document.getElementById(id).addEventListener('change', () => {
            populatePlayerList();
            updateDashboard();
        });
    });
    
    document.getElementById('playerSearch').addEventListener('change', updateDashboard);
    document.getElementById('yearSelect').addEventListener('change', updateDashboard);
    document.getElementById('weekSelect').addEventListener('change', updateDashboard);
}

function populatePlayerList() {
    const team = document.getElementById('teamFilter').value;
    const pos = document.getElementById('posFilter').value;
    const activeOnly = document.getElementById('activeOnly').checked;
    const search = document.getElementById('playerSearch');
    const currentVal = search.value;
    
    search.innerHTML = '<option value="">Select Player</option>';
    
    const players = Object.values(allPlayersStats).map(d => d.player);
    players.sort((a, b) => {
        const aParts = a.name.split(' ');
        const bParts = b.name.split(' ');
        const aLast = aParts[aParts.length - 1];
        const bLast = bParts[bParts.length - 1];
        return aLast.localeCompare(bLast) || aParts[0].localeCompare(bParts[0]);
    });
    
    players.forEach(p => {
        const data = allPlayersStats[p.slug];
        
        let isMatch = true;
        if (team !== 'ALL' && p.team !== team) isMatch = false;
        
        if (isMatch && pos !== 'ALL') {
            if (pos === 'D') isMatch = (p.position === 'D' || p.position === 'LSM');
            else isMatch = (p.position === pos);
        }
        
        if (isMatch && activeOnly && !data.isActive) isMatch = false;

        if (isMatch) {
            const nameParts = p.name.split(' ');
            const lastName = nameParts[nameParts.length - 1];
            const firstInitial = nameParts[0][0];
            const formattedName = `${lastName}, ${firstInitial}.`;
            
            const opt = document.createElement('option');
            opt.value = p.slug;
            opt.textContent = `${formattedName} (${p.position} - ${p.team})`;
            search.appendChild(opt);
        }
    });
    
    if (currentVal && Array.from(search.options).some(o => o.value === currentVal)) {
        search.value = currentVal;
    } else if (search.options.length > 1) {
        search.selectedIndex = 1;
    }
}

function updateDashboard() {
    const slug = document.getElementById('playerSearch').value;
    if (!slug || !allPlayersStats[slug]) return;
    
    currentPlayerData = allPlayersStats[slug];
    const player = currentPlayerData.player;
    const stats = currentPlayerData.stats;
    
    // Update Player Overview
    document.getElementById('playerName').textContent = player.name;
    const latestStat = stats[stats.length-1];
    document.getElementById('playerMeta').textContent = `#${latestStat.identity.jerseyNumber || '?'} | ${player.position} | ${TEAM_NAMES[player.team] || player.team}`;
    document.getElementById('playerAvatar').textContent = player.name.split(' ').map(n => n[0]).join('');

    // Calculate Summary
    const validPoints = stats.map(s => s.f2p.totalPoints || 0).filter(p => p !== 0);
    const avg = (validPoints.length > 0) ? formatPoints(validPoints.reduce((a, b) => a + b, 0) / validPoints.length) : "0";
    const total = formatPoints(validPoints.reduce((a, b) => a + b, 0));
    
    document.getElementById('avgFP').textContent = avg;
    document.getElementById('totalPoints').textContent = total;
    
    // Determine target opponents dynamically
    const year = document.getElementById('yearSelect').value;
    const week = document.getElementById('weekSelect').value;
    let targetOpponents = [];
    if (year && week) {
        const targetGames = stats.filter(s => {
            const sYear = s.event.eventId.split('_')[0];
            return sYear === year && s.week === parseInt(week);
        });
        
        targetGames.forEach(tg => {
            let opp = null;
            // Priority 1: Check standard event properties
            if (tg.event.homeTeam && tg.event.awayTeam) {
                opp = (tg.event.homeTeam === player.team) ? tg.event.awayTeam : tg.event.homeTeam;
            } 
            // Priority 2: Parse from displayString (common for future/unplayed games)
            else if (tg.f2p.displayString && tg.f2p.displayString.includes('vs')) {
                const parts = tg.f2p.displayString.split('vs');
                const rawOpp = parts[parts.length - 1].trim().split(' ')[0];
                opp = normalizeTeamCode(rawOpp);
            }
            
            if (opp) {
                opp = normalizeTeamCode(opp);
                if (!targetOpponents.includes(opp)) {
                    targetOpponents.push(opp);
                }
            }
        });
    }
    
    renderMatchupContext(targetOpponents);
    renderChart(stats, targetOpponents);
    renderTable(stats, targetOpponents);
}

function renderMatchupContext(targetOpponents) {
    const container = document.getElementById('historicalMatchups');
    const info = document.getElementById('opponentInfo');
    container.innerHTML = '';
    
    if (!targetOpponents || targetOpponents.length === 0) {
        info.style.display = 'block';
        info.innerHTML = '<p>Select a week to see opponent analysis.</p>';
        return;
    }

    info.style.display = 'none'; // Hide the placeholder box
    
    targetOpponents.forEach((targetOpponent, index) => {
        const opponentName = TEAM_NAMES[targetOpponent] || targetOpponent;
        
        // Add a header for each opponent
        const oppHeader = document.createElement('div');
        oppHeader.className = 'opponent-highlight';
        oppHeader.style.gridColumn = '1 / -1';
        if (index > 0) oppHeader.style.marginTop = '1.5rem';
        
        // Use different color for second opponent if needed
        const accentColor = index === 0 ? 'var(--accent-secondary)' : '#4fd1c5';
        
        // Calculate average points for these historical games (moved up for header)
        const historicalGames = currentPlayerData.stats.filter(s => {
            const home = s.event.homeTeam;
            const away = s.event.awayTeam;
            return (home === targetOpponent || away === targetOpponent) && s.event.eventId.indexOf('2026') === -1;
        });
        historicalGames.sort((a, b) => b.event.startTime - a.event.startTime);
        const displayGames = historicalGames.slice(0, 4);
        
        let avgStr = "";
        if (displayGames.length > 0) {
            const sum = displayGames.reduce((acc, g) => acc + (g.f2p.totalPoints || 0), 0);
            const avg = formatPoints(sum / displayGames.length);
            avgStr = `
                <div style="display: flex; flex-direction: column; align-items: flex-end;">
                    <span style="font-size: 0.7rem; color: var(--text-secondary); text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px;">vs Opponent Avg</span>
                    <span style="font-size: 1.8rem; font-weight: 800; color: ${accentColor}; line-height: 1;">${avg}</span>
                </div>`;
        }

        // Look up target game for salary information
        const year = document.getElementById('yearSelect').value;
        const week = document.getElementById('weekSelect').value;
        const player = currentPlayerData.player;
        
        const targetGame = currentPlayerData.stats.find(s => {
            const sYear = s.event.eventId.split('_')[0];
            const isTargetWeek = sYear === year && s.week === parseInt(week);
            if (!isTargetWeek) return false;
            
            let opp = null;
            if (s.event.homeTeam && s.event.awayTeam) {
                opp = (s.event.homeTeam === player.team) ? s.event.awayTeam : s.event.homeTeam;
            } else if (s.f2p.displayString && s.f2p.displayString.includes('vs')) {
                const parts = s.f2p.displayString.split('vs');
                const rawOpp = parts[parts.length - 1].trim().split(' ')[0];
                opp = normalizeTeamCode(rawOpp);
            }
            return opp && normalizeTeamCode(opp) === targetOpponent;
        });

        let salaryStr = "";
        if (targetGame && targetGame.f2p && targetGame.f2p.salary !== undefined) {
            salaryStr = `
                <span class="cost-badge" style="font-size: 0.85rem; font-weight: 600; color: var(--accent-secondary); background: rgba(236, 201, 75, 0.12); border: 1px solid rgba(236, 201, 75, 0.25); border-radius: 6px; padding: 3px 8px; margin-left: 12px; display: inline-flex; align-items: center; vertical-align: middle;">
                    ${targetGame.f2p.salary} Coins
                </span>`;
        }

        oppHeader.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
                <h3 style="color: ${accentColor}; margin-bottom: 0; font-size: 1.25rem; display: flex; align-items: center; flex-wrap: wrap;">Facing: ${opponentName} ${salaryStr}</h3>
                ${avgStr}
            </div>
            <p style="font-size: 0.9rem; margin-top: -0.2rem;">Analyzing historical performance against ${targetOpponent}...</p>`;
        container.appendChild(oppHeader);

        if (displayGames.length === 0) {
            oppHeader.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
                    <h3 style="color: ${accentColor}; margin-bottom: 0; font-size: 1.25rem; display: flex; align-items: center; flex-wrap: wrap;">Facing: ${opponentName} ${salaryStr}</h3>
                </div>
                <p>No previous matchups found against this opponent.</p>`;
            const noData = document.createElement('p');
            noData.className = 'no-data';
            noData.textContent = `No previous matchups found against ${opponentName}.`;
            noData.style.gridColumn = '1 / -1';
            noData.style.paddingLeft = '1rem';
            container.appendChild(noData);
        } else {
            displayGames.forEach(game => {
                const div = document.createElement('div');
                div.className = 'matchup-item';
                if (index > 0) div.style.borderTopColor = '#4fd1c5'; // Different top border for second opponent
                
                const matchupLog = currentPlayerData.matchup_logs[game.event.eventId];
                let matchupInfo = "No specific matchup logged";
                if (matchupLog) {
                    const m = matchupLog.matchups.find(ml => ml.playerA === currentPlayerData.player.name || ml.playerB === currentPlayerData.player.name);
                    if (m) {
                        const opponentPlayer = (m.playerA === currentPlayerData.player.name) ? m.playerB : m.playerA;
                        matchupInfo = `vs ${opponentPlayer}`;
                    }
                }

                const dateStr = new Date(game.event.startTime * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                const eventLabel = getEventLabel(game.event.eventId, game.week);
                
                const pointsColor = index === 0 ? 'var(--accent-secondary)' : '#4fd1c5';
                div.innerHTML = `
                    <div class="meta">${dateStr} | ${eventLabel}</div>
                    <div class="details">
                        <div><span class="opponent-name">${matchupInfo}</span></div>
                        <span class="points" style="color: ${pointsColor}">${formatPoints(game.f2p.totalPoints)} FP</span>
                    </div>
                `;
                container.appendChild(div);
            });
        }
    });
}

function renderChart(stats, targetOpponents) {
    const ctx = document.getElementById('fantasyChart').getContext('2d');
    const chartStats = [];
    stats.forEach((s, index) => {
        if (index > 0) {
            const prev = stats[index-1];
            const currYear = s.event.eventId.split('_')[0];
            const prevYear = prev.event.eventId.split('_')[0];
            if (currYear !== prevYear) {
                chartStats.push(null);
            }
        }
        if (s.week === 6 || s.event.eventId.toLowerCase().includes('allstar')) return;
        chartStats.push(s);
    });

    const labels = chartStats.map(s => {
        if (!s) return '';
        const season = s.event.eventId.split('_')[0];
        const eventLabel = getEventLabel(s.event.eventId, s.week);
        const dateStr = new Date(s.event.startTime * 1000).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const opp = s.event.homeTeam === s.identity.team ? s.event.awayTeam : s.event.homeTeam;
        return `${season} ${eventLabel} (${dateStr}) vs ${opp}`;
    });
    
    const data = chartStats.map(s => s ? s.f2p.totalPoints : null);
    const backgroundColors = chartStats.map(s => {
        if (!s) return 'transparent';
        if (!targetOpponents || targetOpponents.length === 0) return 'rgba(159, 122, 234, 0.2)';
        
        const home = s.event.homeTeam;
        const away = s.event.awayTeam;
        
        const oppIndex = targetOpponents.findIndex(opp => home === opp || away === opp);
        if (oppIndex === 0) return 'rgba(236, 201, 75, 0.8)'; // Gold
        if (oppIndex === 1) return 'rgba(79, 209, 197, 0.8)'; // Cyan
        if (oppIndex > 1) return 'rgba(72, 187, 120, 0.8)';  // Green for others
        
        return 'rgba(159, 122, 234, 0.2)';
    });

    if (chart) chart.destroy();
    chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Fantasy Points',
                data: data,
                borderColor: '#9f7aea',
                backgroundColor: 'rgba(159, 122, 234, 0.1)',
                fill: true,
                tension: 0.4,
                pointBackgroundColor: backgroundColors,
                pointRadius: 5,
                pointHoverRadius: 8,
                segment: {
                    borderDash: ctx => {
                        const p0 = chartStats[ctx.p0DataIndex];
                        const p1 = chartStats[ctx.p1DataIndex];
                        if (p0 && p1 && p1.week - p0.week > 1) return [5, 5];
                        return undefined;
                    }
                }
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const s = chartStats[context.dataIndex];
                            if (!s) return '';
                            return `${formatPoints(s.f2p.totalPoints)} FP (${s.event.homeTeam} vs ${s.event.awayTeam})`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#a0aec0' }
                },
                x: {
                    grid: { 
                        display: true,
                        color: (ctx) => {
                            if (ctx.index === 0) return 'rgba(255,255,255,0.1)';
                            const curr = chartStats[ctx.index];
                            const prev = chartStats[ctx.index - 1];
                            if (curr && (!prev || curr.event.eventId.split('_')[0] !== prev.event.eventId.split('_')[0])) return 'rgba(255,255,255,0.3)';
                            return 'transparent';
                        }
                    },
                    ticks: { 
                        color: '#a0aec0',
                        maxRotation: 0,
                        autoSkip: false,
                        callback: function(val, index) {
                            const s = chartStats[index];
                            if (!s) return '';
                            const year = s.event.eventId.split('_')[0];
                            const firstIndex = chartStats.findIndex(item => item && item.event.eventId.split('_')[0] === year);
                            if (index === firstIndex) return year;
                            return '';
                        }
                    }
                }
            }
        }
    });
}

function renderTable(stats, targetOpponents) {
    const header = document.getElementById('gameLogHeader');
    const body = document.getElementById('gameLogBody');
    body.innerHTML = '';
    
    const position = currentPlayerData.player.position; // G, FO, A, M, D, LSM, SSDM, etc.
    
    // Set headers dynamically based on position
    if (position === 'G') {
        header.innerHTML = `
            <tr>
                <th>Season</th>
                <th>Event</th>
                <th>Opponent</th>
                <th>Cost</th>
                <th>FP</th>
                <th>A</th>
                <th>CT</th>
                <th>GB</th>
                <th>GA</th>
                <th>Saves</th>
                <th>Matchup</th>
            </tr>
        `;
    } else if (position === 'FO') {
        header.innerHTML = `
            <tr>
                <th>Season</th>
                <th>Event</th>
                <th>Opponent</th>
                <th>Cost</th>
                <th>FP</th>
                <th>G</th>
                <th>A</th>
                <th>CT</th>
                <th>TO</th>
                <th>GB</th>
                <th>FOW</th>
                <th>FOL</th>
                <th>Matchup</th>
            </tr>
        `;
    } else {
        header.innerHTML = `
            <tr>
                <th>Season</th>
                <th>Event</th>
                <th>Opponent</th>
                <th>Cost</th>
                <th>FP</th>
                <th>G</th>
                <th>A</th>
                <th>CT</th>
                <th>TO</th>
                <th>GB</th>
                <th>T</th>
                <th>Matchup</th>
            </tr>
        `;
    }

    stats.slice().reverse().forEach(s => {
        const home = s.event.homeTeam;
        const away = s.event.awayTeam;
        const oppIndex = targetOpponents ? targetOpponents.findIndex(opp => home === opp || away === opp) : -1;
        
        const tr = document.createElement('tr');
        if (oppIndex !== -1) {
            tr.className = 'relevant';
            // Apply custom coloring for multiple opponents
            if (oppIndex === 0) {
                tr.style.backgroundColor = 'rgba(236, 201, 75, 0.15)';
                tr.style.borderLeft = '4px solid var(--accent-secondary)';
            } else if (oppIndex === 1) {
                tr.style.backgroundColor = 'rgba(79, 209, 197, 0.15)';
                tr.style.borderLeft = '4px solid #4fd1c5';
            } else {
                tr.style.backgroundColor = 'rgba(72, 187, 120, 0.15)';
                tr.style.borderLeft = '4px solid #48bb78';
            }
        }

        const season = s.event.eventId.split('_')[0];
        const opp = s.event.homeTeam === s.identity.team ? s.event.awayTeam : s.event.homeTeam;
        const matchupLog = currentPlayerData.matchup_logs[s.event.eventId];
        let opponentPlayer = "-";
        if (matchupLog) {
            const m = matchupLog.matchups.find(ml => ml.playerA === currentPlayerData.player.name || ml.playerB === currentPlayerData.player.name);
            if (m) opponentPlayer = (m.playerA === currentPlayerData.player.name) ? m.playerB : m.playerA;
        }
        const eventLabel = getEventLabel(s.event.eventId, s.week);
        
        const costStr = (s.f2p && s.f2p.salary !== undefined && s.f2p.salary !== null) ? `${s.f2p.salary}` : '-';
        
        let cells = '';
        if (position === 'G') {
            cells = `
                <td>${season}</td>
                <td>${eventLabel}</td>
                <td>${opp}</td>
                <td style="color:var(--text-secondary); font-weight: 500;">${costStr}</td>
                <td style="font-weight:700; color:var(--accent-secondary)">${formatPoints(s.f2p.totalPoints)}</td>
                <td>${s.stats.assists || 0}</td>
                <td>${s.stats.causedTurnovers || 0}</td>
                <td>${s.stats.groundBalls || 0}</td>
                <td>${s.stats.goalsAgainst || 0}</td>
                <td>${s.stats.saves || 0}</td>
                <td>${opponentPlayer}</td>
            `;
        } else if (position === 'FO') {
            const fow = s.stats.faceoffsWon || 0;
            const totalFo = s.stats.faceoffs || 0;
            const fol = Math.max(0, totalFo - fow);
            cells = `
                <td>${season}</td>
                <td>${eventLabel}</td>
                <td>${opp}</td>
                <td style="color:var(--text-secondary); font-weight: 500;">${costStr}</td>
                <td style="font-weight:700; color:var(--accent-secondary)">${formatPoints(s.f2p.totalPoints)}</td>
                <td>${s.stats.goals || 0}</td>
                <td>${s.stats.assists || 0}</td>
                <td>${s.stats.causedTurnovers || 0}</td>
                <td>${s.stats.turnovers || 0}</td>
                <td>${s.stats.groundBalls || 0}</td>
                <td>${fow}</td>
                <td>${fol}</td>
                <td>${opponentPlayer}</td>
            `;
        } else {
            cells = `
                <td>${season}</td>
                <td>${eventLabel}</td>
                <td>${opp}</td>
                <td style="color:var(--text-secondary); font-weight: 500;">${costStr}</td>
                <td style="font-weight:700; color:var(--accent-secondary)">${formatPoints(s.f2p.totalPoints)}</td>
                <td>${s.stats.goals || 0}</td>
                <td>${s.stats.assists || 0}</td>
                <td>${s.stats.causedTurnovers || 0}</td>
                <td>${s.stats.turnovers || 0}</td>
                <td>${s.stats.groundBalls || 0}</td>
                <td>${s.stats.touches || 0}</td>
                <td>${opponentPlayer}</td>
            `;
        }
        
        tr.innerHTML = cells;
        body.appendChild(tr);
    });
}

init();
