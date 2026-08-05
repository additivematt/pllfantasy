const DOM = {
    yearSelect: document.getElementById('yearSelect'),
    weekSelect: document.getElementById('weekSelect'),
    matchupSelect: document.getElementById('matchupSelect'),
    taggerPanel: document.getElementById('taggerPanel'),
    matchupsContainer: document.getElementById('matchupsContainer'),
    btnAddMatchup: document.getElementById('btnAddMatchup'),
    btnSave: document.getElementById('btnSave'),
    statusMessage: document.getElementById('statusMessage'),
    activeRosterBadge: document.getElementById('activeRosterBadge')
};

let rosterData = [];
let events = {};
let weeks = {};
let playersByTeam = {};
let selectedTeamA = null;
let selectedTeamB = null;
let seasonMatchups = {};
let activeRosters = null;

function cleanPlayerName(name) {
    if (!name) return "";
    return name.replace(/['\-\.\s]/g, "").toLowerCase();
}

const TEAM_NAMES = {
    'ARC': 'Utah Archers',
    'OUT': 'Denver Outlaws',
    'RED': 'California Redwoods',
    'ATL': 'New York Atlas',
    'CHA': 'Carolina Chaos',
    'WHP': 'Maryland Whipsnakes',
    'WAT': 'Philadelphia Waterdogs',
    'CAN': 'Boston Cannons'
};

// Initialize App
async function loadDataForYear(year) {
    try {
        DOM.weekSelect.innerHTML = '<option value="">Select Week</option>';
        DOM.matchupSelect.innerHTML = '<option value="">Select Matchup</option>';
        DOM.weekSelect.disabled = true;
        DOM.matchupSelect.disabled = true;
        DOM.taggerPanel.classList.add('hidden');

        const [response, matchupsResponse] = await Promise.all([
            fetch(`/data/${year}`),
            fetch(`/matchups/${year}`)
        ]);
        
        if (!response.ok) throw new Error(`No data for ${year}`);
        
        rosterData = await response.json();
        seasonMatchups = await matchupsResponse.json();
        
        processRosterData();
        populateWeeks();
        
        showMessage(`Loaded games for ${year}`, "success");
    } catch (error) {
        console.error("Failed to load roster data:", error);
        DOM.statusMessage.textContent = `Error loading data for ${year}. Ensure combined_player_stats_${year}.json exists.`;
        DOM.statusMessage.className = "status-message status-error";
    }
}

async function init() {
    await loadDataForYear(DOM.yearSelect.value);
    DOM.yearSelect.addEventListener('change', async (e) => {
        // Reset state
        events = {};
        weeks = {};
        playersByTeam = {};
        
        await loadDataForYear(e.target.value);
    });
}

function processRosterData() {
    events = {};
    playersByTeam = {};

    rosterData.forEach(player => {
        if (!player.identity || !player.identity.team || !player.event || !player.event.eventId) return;
        
        const teamId = player.identity.team;
        
        // Skip players with unknown/placeholder team codes (e.g. ZPP = unsigned/inactive)
        if (!TEAM_NAMES[teamId]) return;
        const eventId = player.event.eventId;
        
        if (!events[eventId]) {
            events[eventId] = {
                startTime: parseInt(player.event.startTime) || 0,
                week: player.week,
                teams: new Set()
            };
        }
        events[eventId].teams.add(teamId);
        
        if (!playersByTeam[teamId]) {
            playersByTeam[teamId] = [];
        }
        
        // Ensure we don't add duplicates since the stats file might have multiple entries per player
        const existingPlayer = playersByTeam[teamId].find(p => p.id === player.identity.officialId);
        if (existingPlayer) return;
        
        // standardise positions
        let stdPos = player.identity.position;
        if (['D', 'LSM'].includes(stdPos)) stdPos = 'DEF';
        if (['A'].includes(stdPos)) stdPos = 'ATT';
        if (['M', 'SSDM'].includes(stdPos)) stdPos = 'MID';
        
        playersByTeam[teamId].push({
            id: player.identity.officialId,
            name: `${player.identity.firstName} ${player.identity.lastName}`,
            position: player.identity.position,
            stdPos: stdPos,
            jersey: player.identity.jerseyNumber || '?' // jersey might not be in this new file
        });
    });
    
    // Sort players alphabetically
    for (let team in playersByTeam) {
        playersByTeam[team].sort((a, b) => a.name.localeCompare(b.name));
    }
}

function populateWeeks() {
    weeks = {};
    DOM.weekSelect.innerHTML = '<option value="">Select Week</option>';
    
    // Group events by their 'week' property
    Object.keys(events).forEach(eventId => {
        const weekVal = events[eventId].week;
        let weekKey;
        
        if (typeof weekVal === 'number') {
            weekKey = `Week ${weekVal}`;
        } else if (typeof weekVal === 'string') {
            weekKey = weekVal;
        } else {
            // Fallback for older data without week field
            weekKey = "Unknown";
        }
        
        if (!weeks[weekKey]) weeks[weekKey] = [];
        weeks[weekKey].push(eventId);
    });
    
    // Sort week keys
    const sortedWeekKeys = Object.keys(weeks).sort((a, b) => {
        // Try to sort numerically if both start with "Week"
        const numA = parseInt(a.replace('Week ', ''));
        const numB = parseInt(b.replace('Week ', ''));
        if (!isNaN(numA) && !isNaN(numB)) return numA - numB;
        
        // Otherwise alphabetical (handles "Quarterfinal", "Final", etc.)
        return a.localeCompare(b);
    });

    sortedWeekKeys.forEach(w => {
        DOM.weekSelect.add(new Option(w, w));
    });
    
    if (sortedWeekKeys.length > 0) {
        DOM.weekSelect.disabled = false;
    }
}

DOM.weekSelect.addEventListener('change', (e) => {
    const week = e.target.value;
    DOM.matchupSelect.innerHTML = '<option value="">Select Matchup</option>';
    DOM.taggerPanel.classList.add('hidden');
    
    if (week && weeks[week]) {
        weeks[week].forEach(eventId => {
            const ev = events[eventId];
            const teamsArr = Array.from(ev.teams);
            const nameA = TEAM_NAMES[teamsArr[0]] || teamsArr[0];
            const nameB = TEAM_NAMES[teamsArr[1]] || teamsArr[1] || teamsArr[0];
            const displayStr = teamsArr.length >= 2 ? `${nameA} vs ${nameB}` : eventId;
            DOM.matchupSelect.add(new Option(displayStr, eventId));
        });
        DOM.matchupSelect.disabled = false;
    } else {
        DOM.matchupSelect.disabled = true;
    }
});

DOM.matchupSelect.addEventListener('change', () => {
    if (DOM.matchupSelect.value) {
        loadGame();
        setTimeout(() => DOM.taggerPanel.scrollIntoView({ behavior: 'smooth', block: 'start' }), 150);
    } else {
        DOM.taggerPanel.classList.add('hidden');
    }
});

async function loadGame() {
    const eventId = DOM.matchupSelect.value;
    if (!eventId || !events[eventId]) return;

    const ev = events[eventId];
    const teamsArr = Array.from(ev.teams);
    selectedTeamA = teamsArr[0];
    selectedTeamB = teamsArr[1] || teamsArr[0];

    // Load existing tags if this game has been tagged before
    const existingGame = seasonMatchups[eventId];

    // Respect the teams stored in the matchup file if they match this event's teams
    if (existingGame && existingGame.team_a && existingGame.team_b) {
        if (ev.teams.has(existingGame.team_a) && ev.teams.has(existingGame.team_b)) {
            selectedTeamA = existingGame.team_a;
            selectedTeamB = existingGame.team_b;
        }
    }

    // Fetch active roster for this week
    const weekVal = ev.week;
    let weekNum = weekVal;
    if (typeof weekVal === 'string') {
        weekNum = weekVal.replace('Week ', '').trim();
    }
    
    activeRosters = null;
    try {
        const res = await fetch(`/active-rosters/${weekNum}`);
        if (res.ok) {
            const data = await res.json();
            if (data && data.data && data.data.items) {
                // Union active players across all games in the week to handle double-headers and placeholder roster limitations
                activeRosters = {
                    [selectedTeamA]: new Set(),
                    [selectedTeamB]: new Set()
                };
                
                const processTeamRoster = (teamObj, teamId) => {
                    if (teamObj && teamObj.gamedayRoster) {
                        teamObj.gamedayRoster.forEach(player => {
                            const status = player.rosterStatus ? player.rosterStatus.toLowerCase() : "";
                            const injury = player.injuryStatus ? player.injuryStatus.toUpperCase() : "";
                            if ((status === "active" || status === "starter") && injury !== "O" && injury !== "IR") {
                                const fullName = `${player.firstName} ${player.lastName}`;
                                activeRosters[teamId].add(cleanPlayerName(fullName));
                            }
                        });
                    }
                };

                data.data.items.forEach(item => {
                    for (let side of ['homeTeam', 'awayTeam']) {
                        const t = item[side];
                        if (t && t.officialId === selectedTeamA) {
                            processTeamRoster(t, selectedTeamA);
                        }
                        if (t && t.officialId === selectedTeamB) {
                            processTeamRoster(t, selectedTeamB);
                        }
                    }
                });
            }
        }
    } catch (e) {
        console.error("Error loading active rosters:", e);
    }

    if (activeRosters && (activeRosters[selectedTeamA].size > 0 || activeRosters[selectedTeamB].size > 0)) {
        DOM.activeRosterBadge.classList.remove('hidden');
    } else {
        DOM.activeRosterBadge.classList.add('hidden');
        activeRosters = null; // Ensure it's null so we bypass filtering
    }

    DOM.taggerPanel.classList.remove('hidden');

    // Clear any previous rows
    DOM.matchupsContainer.innerHTML = '';
    
    // Add column headers once at the top
    const header = document.createElement('div');
    header.className = 'matchups-header';
    
    const nameA = TEAM_NAMES[selectedTeamA] || selectedTeamA;
    const nameB = TEAM_NAMES[selectedTeamB] || selectedTeamB;
    
    header.innerHTML = `
        <div class="header-col">${nameA}</div>
        <div class="header-spacer"></div>
        <div class="header-col">${nameB}</div>
        <div class="header-spacer-small"></div>
    `;
    DOM.matchupsContainer.appendChild(header);
 
    if (existingGame && existingGame.matchups && existingGame.matchups.length > 0) {
        existingGame.matchups.forEach(m => addMatchupRow(m));
        showMessage(`Loaded ${existingGame.matchups.length} existing matchup(s)`, "success");
    } else {
        addMatchupRow();
    }
}

DOM.btnAddMatchup.addEventListener('click', () => addMatchupRow(null, true));

function createPlayerOptions(teamId, forceIncludeNames = []) {
    const players = playersByTeam[teamId];
    if (!players) return '<option value="">No Players</option>';
    
    // Group players by standard position
    const grouped = {
        'ATT': [],
        'MID': [],
        'DEF': [],
        'FO': [],
        'G': []
    };
    
    const forceIncludeCleaned = new Set(forceIncludeNames.map(name => cleanPlayerName(name)));

    players.forEach(p => {
        // If there is active roster info for this team, restrict to active players (unless forced included)
        if (activeRosters && activeRosters[teamId]) {
            const cleanedName = cleanPlayerName(p.name);
            if (!activeRosters[teamId].has(cleanedName) && !forceIncludeCleaned.has(cleanedName)) {
                return; // Skip inactive player
            }
        }

        if (grouped[p.stdPos]) {
            grouped[p.stdPos].push(p);
        } else {
            // Default bucket
            grouped['MID'].push(p);
        }
    });

    let options = '<option value="">Select Player</option>';
    
    // Same fixed order for both teams: ATT, DEF, FO, MID, G
    const displayOrder = ['ATT', 'DEF', 'FO', 'MID', 'G'];
        
    const labels = {
        'ATT': 'Attackmen',
        'MID': 'Midfielders / SSDM',
        'DEF': 'Defensemen / LSM',
        'FO': 'Faceoff',
        'G': 'Goalies'
    };
    
    displayOrder.forEach(pos => {
        if (grouped[pos] && grouped[pos].length > 0) {
            options += `<optgroup label="${labels[pos]}">`;
            grouped[pos].forEach(p => {
                options += `<option value="${p.name}">[${p.position}] ${p.name} #${p.jersey}</option>`;
            });
            options += `</optgroup>`;
        }
    });
    
    return options;
}

function addMatchupRow(existingData = null, insertAtTop = false) {
    const row = document.createElement('div');
    row.className = 'matchup-row';
    
    const forceA = existingData ? [existingData.playerA || existingData.defender].filter(Boolean) : [];
    const forceB = existingData ? [existingData.playerB || existingData.attacker].filter(Boolean) : [];

    const teamAOptions = createPlayerOptions(selectedTeamA, forceA);
    const teamBOptions = createPlayerOptions(selectedTeamB, forceB);
    
    row.innerHTML = `
        <div class="matchup-col">
            <select class="player-a-select">
                ${teamAOptions}
            </select>
        </div>
        <div class="matchup-icon">↔️</div>
        <div class="matchup-col">
            <select class="player-b-select">
                ${teamBOptions}
            </select>
        </div>
        <button class="btn-danger remove-row" title="Remove Matchup">×</button>
    `;
    
    row.querySelector('.remove-row').addEventListener('click', () => {
        row.remove();
        updateAvailableOptions();
    });
    
    // Pre-fill if loading an existing matchup
    if (existingData) {
        // Support both old and new schema during transition
        row.querySelector('.player-a-select').value = existingData.playerA || existingData.defender || '';
        row.querySelector('.player-b-select').value = existingData.playerB || existingData.attacker || '';
    }
    
    // Wire up change events to enforce unique selection
    row.querySelector('.player-a-select').addEventListener('change', updateAvailableOptions);
    row.querySelector('.player-b-select').addEventListener('change', updateAvailableOptions);
    
    if (insertAtTop) {
        const header = DOM.matchupsContainer.querySelector('.matchups-header');
        if (header) {
            DOM.matchupsContainer.insertBefore(row, header.nextSibling);
        } else {
            DOM.matchupsContainer.appendChild(row);
        }
    } else {
        DOM.matchupsContainer.appendChild(row);
    }
    
    updateAvailableOptions();
}

/**
 * Disables options that are already selected in any other row,
 * so each player can only be picked once across the whole session.
 */
function updateAvailableOptions() {
    const allSelects = [...document.querySelectorAll('.player-a-select, .player-b-select')];
    const selectedValues = new Set(
        allSelects.map(s => s.value).filter(v => v !== '')
    );

    allSelects.forEach(sel => {
        const myValue = sel.value;
        [...sel.options].forEach(opt => {
            if (opt.value === '') return; // always keep the placeholder
            // Disable if selected elsewhere, unless it's this select's own current value
            opt.disabled = selectedValues.has(opt.value) && opt.value !== myValue;
        });
    });
}

DOM.btnSave.addEventListener('click', async () => {
    const rows = document.querySelectorAll('.matchup-row');
    const matchups = [];
    
    rows.forEach(row => {
        const pA = row.querySelector('.player-a-select').value;
        const pB = row.querySelector('.player-b-select').value;
        
        if (pA && pB) {
            matchups.push({ playerA: pA, playerB: pB });
        }
    });
    
    if (matchups.length === 0) {
        showMessage("No matchups to save! Please tag at least one.", "error");
        return;
    }
    
    const payload = {
        year: DOM.yearSelect.value,
        game_id: DOM.matchupSelect.value,
        team_a: selectedTeamA,
        team_b: selectedTeamB,
        matchups: matchups,
        timestamp: new Date().toISOString()
    };
    
    DOM.btnSave.disabled = true;
    DOM.btnSave.textContent = 'Saving...';
    
    try {
        const res = await fetch('/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            showMessage("Matchups saved successfully!", "success");
            // Update local cache so re-loading same game restores tags
            seasonMatchups[payload.game_id] = payload;
        } else {
            throw new Error("Server returned " + res.status);
        }
    } catch (err) {
        showMessage("Failed to save: " + err.message, "error");
    } finally {
        DOM.btnSave.disabled = false;
        DOM.btnSave.textContent = 'Save Matchup Data';
    }
});

function showMessage(msg, type) {
    DOM.statusMessage.textContent = msg;
    DOM.statusMessage.className = `status-message status-${type}`;
    setTimeout(() => {
        DOM.statusMessage.textContent = "";
    }, 4000);
}

// Start
init();
