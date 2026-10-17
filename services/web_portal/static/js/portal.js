/**
 * ==============================================================================
 * Software-Defined Vehicle (SDV) Cyber-Physical Cabin Environmental Control
 * Frontend Interactivity and Real-Time Multi-Vehicle Telemetry Client
 * ==============================================================================
 */

let currentVehicle = localStorage.getItem('sdv_active_vehicle') || 'vehicle_01';
let fleetVehicles = [];

document.addEventListener('DOMContentLoaded', () => {
    initHudClock();
    loadFleetVehicles();
    initTelemetryStream();
    selectActiveVehicle(currentVehicle);
});

/**
 * Formats a Date object as a local timestamp string with the client timezone.
 * Example output: "2026-10-05 00:04:01 CEST"
 */
function formatLocalDateTime(date) {
    const pad = (n) => String(n).padStart(2, '0');
    const year = date.getFullYear();
    const month = pad(date.getMonth() + 1);
    const day = pad(date.getDate());
    const hours = pad(date.getHours());
    const minutes = pad(date.getMinutes());
    const seconds = pad(date.getSeconds());

    let tzString = '';
    try {
        const parts = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' }).formatToParts(date);
        const tzPart = parts.find((p) => p.type === 'timeZoneName');
        if (tzPart && tzPart.value) {
            tzString = tzPart.value;
        }
    } catch (_) {}

    if (!tzString) {
        try {
            tzString = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
        } catch (_) {}
    }

    if (!tzString) {
        const offset = -date.getTimezoneOffset();
        const sign = offset >= 0 ? '+' : '-';
        const absOffset = Math.abs(offset);
        tzString = `UTC${sign}${pad(Math.floor(absOffset / 60))}`;
    }

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds} ${tzString}`.trim();
}

/**
 * Updates the local HUD clock every second using the current client timezone and local time.
 */
function initHudClock() {
    function updateClock() {
        const now = new Date();
        const el = document.getElementById('hud-clock');
        if (el) {
            el.textContent = formatLocalDateTime(now);
            try {
                const tzResolved = Intl.DateTimeFormat().resolvedOptions().timeZone;
                if (tzResolved) {
                    el.title = `Local Timezone: ${tzResolved}`;
                }
            } catch (_) {}
        }
    }
    setInterval(updateClock, 1000);
    updateClock();
}

/**
 * Discovers and renders the registered vehicles roster across the SDV fleet.
 */
async function loadFleetVehicles() {
    try {
        const response = await fetch('/api/vehicles');
        if (!response.ok) return;
        const data = await response.json();
        if (data.vehicles && data.vehicles.length > 0) {
            fleetVehicles = data.vehicles;
            renderFleetDropdown(fleetVehicles);
            renderVehiclePills(fleetVehicles);
        }
    } catch (err) {
        console.debug('Fleet vehicles discovery poll failed:', err);
    }
}

/**
 * Selects the active vehicular node across the UI consoles.
 */
function selectActiveVehicle(carId) {
    if (!carId) return;
    currentVehicle = carId;
    localStorage.setItem('sdv_active_vehicle', carId);

    // 1. Update global HUD badge in navigation bar
    const globalBadge = document.getElementById('globalActiveVehicleBadge');
    if (globalBadge) {
        globalBadge.textContent = carId.toUpperCase();
    }

    // 2. Update breadcrumb badge on overview console
    const breadcrumbBadge = document.getElementById('breadcrumbVehicleBadge');
    if (breadcrumbBadge) {
        breadcrumbBadge.textContent = carId.toUpperCase();
    }

    // 3. Update Downlink Actuation Controller target badge
    const actuationBadge = document.getElementById('actuationTargetBadge');
    if (actuationBadge) {
        actuationBadge.textContent = `TARGET: ${carId}`;
    }

    // 4. Update stream filter badge
    const filterBadge = document.getElementById('logFilterBadge');
    if (filterBadge) {
        filterBadge.textContent = `FILTER: ${carId}`;
    }

    // 5. Update pipeline CSE container path
    const pipelinePath = document.getElementById('pipelineCsePath');
    if (pipelinePath) {
        const digits = carId.replace(/\D/g, '');
        const suffix = digits ? `Car${digits.padStart(2, '0')}` : carId.replace('vehicle_', 'Car');
        pipelinePath.textContent = `/sdv-cse/AE_CabinNode_${suffix}/cnt_raw_telemetry`;
    }

    // 6. Refresh active highlights in dropdown and pills
    renderFleetDropdown(fleetVehicles);
    renderVehiclePills(fleetVehicles);

    // 7. Trigger immediate telemetry fetch for newly selected vehicle
    if (typeof fetchActiveVehicleTelemetry === 'function') {
        fetchActiveVehicleTelemetry();
    }
}

/**
 * Renders the vehicle items inside the global navigation dropdown.
 */
function renderFleetDropdown(vehicles) {
    const listEl = document.getElementById('fleetVehicleMenuItems');
    if (!listEl) return;

    const roster = (vehicles && vehicles.length > 0) ? vehicles : [
        { id: 'vehicle_01', name: 'VEHICLE 01', ae_rn: 'AE_CabinNode_Car01' }
    ];

    listEl.innerHTML = roster.map(v => {
        const isActive = v.id === currentVehicle;
        return `
            <li>
                <a class="dropdown-item ${isActive ? 'active' : ''} d-flex align-items-center justify-content-between" 
                   href="javascript:void(0)" 
                   onclick="selectActiveVehicle('${v.id}')">
                    <span>
                        <i class="bi ${isActive ? 'bi-check2 text-success' : 'bi-truck text-secondary'} me-2"></i>
                        <strong>${v.id}</strong> <span class="text-secondary small">(${v.ae_rn})</span>
                    </span>
                    ${isActive ? '<span class="badge bg-success-subtle text-success border border-success-subtle ms-2 font-monospace">ACTIVE</span>' : ''}
                </a>
            </li>
        `;
    }).join('');
}

/**
 * Renders vehicle pill buttons on the overview console.
 */
function renderVehiclePills(vehicles) {
    const pillsGroup = document.getElementById('vehiclePillsGroup');
    if (!pillsGroup) return;

    const roster = (vehicles && vehicles.length > 0) ? vehicles : [
        { id: 'vehicle_01', name: 'VEHICLE 01' }
    ];

    pillsGroup.innerHTML = roster.map(v => {
        const isActive = v.id === currentVehicle;
        return `
            <button type="button" 
                    class="btn ${isActive ? 'btn-primary active' : 'btn-outline-primary'} font-monospace px-2 py-0" 
                    onclick="selectActiveVehicle('${v.id}')">
                ${v.name || v.id.toUpperCase()}
            </button>
        `;
    }).join('');
}

let fetchActiveVehicleTelemetry = null;

/**
 * Polls the backend API for real-time cabin telemetry metrics and updates the console.
 */
function initTelemetryStream() {
    const streamConsole = document.getElementById('streamConsole');
    if (!streamConsole) return;

    fetchActiveVehicleTelemetry = async function() {
        try {
            const response = await fetch(`/api/telemetry/latest?car_id=${encodeURIComponent(currentVehicle)}`);
            if (!response.ok) return;
            const data = await response.json();
            updateTelemetryDisplay(data);
        } catch (err) {
            console.debug('Telemetry stream poll skipped:', err);
        }
    };

    // Initial poll followed by 2-second interval
    fetchActiveVehicleTelemetry();
    setInterval(fetchActiveVehicleTelemetry, 2000);
}

/**
 * Updates dashboard DOM nodes with freshly ingested telemetry metrics.
 */
function updateTelemetryDisplay(data) {
    if (!data || !data.scd30) return;

    // SCD30 CO2
    const co2El = document.getElementById('val-co2');
    if (co2El && data.scd30.co2_ppm !== null && data.scd30.co2_ppm !== undefined) {
        co2El.textContent = parseFloat(data.scd30.co2_ppm).toFixed(1);
    }

    // SCD30 Temperature
    const tempScdEl = document.getElementById('val-temp-scd30');
    if (tempScdEl && data.scd30.temperature_c !== null && data.scd30.temperature_c !== undefined) {
        tempScdEl.textContent = parseFloat(data.scd30.temperature_c).toFixed(1);
    }

    // Relative Humidity
    const rhEl = document.getElementById('val-humidity');
    if (rhEl && data.scd30.humidity_pct !== null && data.scd30.humidity_pct !== undefined) {
        rhEl.textContent = parseFloat(data.scd30.humidity_pct).toFixed(1);
    }

    // Fan RPM and Duty
    if (data.actuator_state) {
        const rpmEl = document.getElementById('val-fan-rpm');
        if (rpmEl && data.actuator_state.tachometer_rpm !== undefined) {
            rpmEl.textContent = data.actuator_state.tachometer_rpm;
        }
        const dutyBadge = document.getElementById('badge-fan-duty');
        if (dutyBadge && data.actuator_state.pwm_duty_pct !== undefined) {
            dutyBadge.textContent = `DUTY: ${data.actuator_state.pwm_duty_pct}%`;
        }
    }

    // DHT22 Cross-Check & Delta-T
    if (data.dht22 && data.dht22.temperature_c !== null && data.scd30.temperature_c !== null) {
        const deltaT = Math.abs(parseFloat(data.scd30.temperature_c) - parseFloat(data.dht22.temperature_c));
        const deltaBadge = document.getElementById('badge-delta-t');
        if (deltaBadge) {
            deltaBadge.textContent = `ΔT: ${deltaT.toFixed(1)}°C`;
            if (deltaT > 1.5) {
                deltaBadge.className = 'badge bg-warning text-dark font-monospace py-0 px-2';
            } else {
                deltaBadge.className = 'badge bg-fhtw-green text-white font-monospace py-0 px-2';
            }
        }
    }

    // Health State Badge
    const healthBadge = document.getElementById('badge-health-state');
    if (healthBadge && data.health_state) {
        healthBadge.textContent = data.health_state;
        if (data.health_state === 'FRESH') {
            healthBadge.className = 'badge bg-fhtw-green text-white font-monospace px-2 py-1';
            healthBadge.style.backgroundColor = '';
            healthBadge.style.color = '';
        } else if (data.health_state === 'STALE') {
            healthBadge.className = 'badge bg-warning text-dark font-monospace px-2 py-1';
            healthBadge.style.backgroundColor = '';
            healthBadge.style.color = '';
        } else if (data.health_state === 'DEGRADED') {
            healthBadge.className = 'badge font-monospace px-2 py-1';
            healthBadge.style.backgroundColor = '#e67e22';
            healthBadge.style.color = '#ffffff';
        } else {
            healthBadge.className = 'badge bg-danger text-white font-monospace px-2 py-1';
            healthBadge.style.backgroundColor = '';
            healthBadge.style.color = '';
        }
    }

    // Append to live terminal log
    appendStreamLog(data);
}

/**
 * Appends a formatted telemetry ingress log entry to the terminal window.
 */
function appendStreamLog(data) {
    const streamConsole = document.getElementById('streamConsole');
    if (!streamConsole) return;

    const timeStr = formatLocalDateTime(new Date());
    const state = data.health_state || 'FRESH';
    const stateClass = state === 'FRESH' ? 'text-success' : (state === 'FAULT' ? 'text-danger' : 'text-warning');
    const co2 = data.scd30 ? (data.scd30.co2_ppm || 'N/A') : 'N/A';
    const tScd = data.scd30 ? (data.scd30.temperature_c || 'N/A') : 'N/A';
    const tDht = data.dht22 ? (data.dht22.temperature_c || 'N/A') : 'N/A';
    const pwm = data.actuator_state ? data.actuator_state.pwm_duty_pct : 25;
    const rpm = data.actuator_state ? data.actuator_state.tachometer_rpm : 980;
    const carId = data.car_id || currentVehicle || 'vehicle_01';

    const logLine = document.createElement('div');
    logLine.className = 'text-muted py-0.5 border-bottom border-grid-subtle';
    logLine.innerHTML = `[${timeStr}] <span class="text-info">INGRESS</span> car_id=<strong>${carId}</strong> CO2=${co2}ppm T_scd30=${tScd}°C T_dht22=${tDht}°C PWM=${pwm}% RPM=${rpm} &rarr; <span class="${stateClass} fw-bold">state=${state}</span>`;

    streamConsole.insertBefore(logLine, streamConsole.firstChild);

    // Limit log entries to 50
    while (streamConsole.children.length > 50) {
        streamConsole.removeChild(streamConsole.lastChild);
    }
}

/**
 * Dispatches an actuator command directive to the backend via POST targeting the active vehicle.
 */
async function dispatchActuation() {
    const pwmSlider = document.getElementById('pwmSlider');
    const pwm = pwmSlider ? parseInt(pwmSlider.value, 10) : 25;
    const modeEl = document.querySelector('input[name="ventMode"]:checked');
    const mode = modeEl ? modeEl.value : 'AUTOMATIC';

    const statusFeedback = document.getElementById('actuationFeedback');

    try {
        if (statusFeedback) {
            statusFeedback.innerHTML = `<span class="text-info font-monospace small"><i class="bi bi-arrow-repeat spin me-1"></i>Dispatching directive for ${currentVehicle} to oneM2M CSE...</span>`;
        }

        const response = await fetch('/api/actuator/dispatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                car_id: currentVehicle,
                target_pwm: pwm,
                mode: mode,
                source_entity: 'WebPortal_Console'
            })
        });

        const result = await response.json();
        if (response.ok) {
            if (statusFeedback) {
                statusFeedback.innerHTML = `<span class="text-success font-monospace small"><i class="bi bi-check-circle me-1"></i>Directive dispatched to ${result.car_id || currentVehicle} [HTTP ${result.status_code || 201}]: PWM=${pwm}%, Mode=${mode}</span>`;
            }
        } else {
            if (statusFeedback) {
                statusFeedback.innerHTML = `<span class="text-danger font-monospace small"><i class="bi bi-exclamation-octagon me-1"></i>Dispatch failure: ${result.error || 'Server error'}</span>`;
            }
        }
    } catch (err) {
        if (statusFeedback) {
            statusFeedback.innerHTML = `<span class="text-danger font-monospace small"><i class="bi bi-exclamation-octagon me-1"></i>Network error: ${err.message}</span>`;
        }
    }
}

/**
 * Triggers emergency shutdown of cabin ventilation on the active vehicle.
 */
async function triggerEStop() {
    if (!confirm(`CONFIRM IMMEDIATE EMERGENCY SHUTDOWN OF CABIN VENTILATION ACTUATORS FOR ${currentVehicle.toUpperCase()}?`)) {
        return;
    }

    const pwmSlider = document.getElementById('pwmSlider');
    if (pwmSlider) {
        pwmSlider.value = 0;
        const display = document.getElementById('pwmDisplay');
        if (display) display.textContent = '0%';
    }

    const modeManual = document.getElementById('modeManual');
    if (modeManual) modeManual.checked = true;

    const statusFeedback = document.getElementById('actuationFeedback');
    try {
        const response = await fetch('/api/actuator/dispatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                car_id: currentVehicle,
                target_pwm: 0,
                mode: 'MANUAL',
                source_entity: 'WebPortal_EStop'
            })
        });
        const result = await response.json();
        if (statusFeedback) {
            statusFeedback.innerHTML = `<span class="badge bg-danger rounded-0 font-monospace p-2 w-100"><i class="bi bi-slash-circle me-1"></i>E-STOP ENGAGED FOR ${currentVehicle.toUpperCase()}: ACTUATOR PWM FORCED TO 0%</span>`;
        }
    } catch (err) {
        console.error('E-Stop dispatch error:', err);
    }
}

/**
 * Clears the telemetry stream log.
 */
function clearStreamLog() {
    const streamConsole = document.getElementById('streamConsole');
    if (streamConsole) {
        streamConsole.innerHTML = '<div class="text-muted py-1">Stream log cleared. Awaiting live frame ingestion...</div>';
    }
}
