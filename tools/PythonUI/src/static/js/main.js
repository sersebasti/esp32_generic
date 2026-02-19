// --- Variabili globali iniettate dal template ---
// ip, sensorsList

const select = document.getElementById('sensor-select');
const btnMisureBis = document.getElementById('btn-aggiorna-misure-bis');
const boxes = document.getElementById('sensor-boxes');
// ip e sensorsList devono essere iniettati dal template
// Esempio:
// <script>const ip = '{{ ip }}'; var sensorsList = ...</script>

var sensorTypeMap = {};
if (typeof sensorsList !== 'undefined' && Array.isArray(sensorsList)) {
    sensorsList.forEach(function(s) { sensorTypeMap[s.id] = s.type; });
}
function getSensorId() { return select.value; }
function getSensorType() { return sensorTypeMap[select.value] || ''; }
function getPointReferenceValue(point, sensorType) {
    if (sensorType === 'current') {
        return point.amps ?? point.amp ?? point.current ?? point.volts;
    }
    return point.volts ?? point.amp ?? point.amps;
}
function getBisRmsMeta(sensorType) {
    if (sensorType === 'current') {
        return { key: 'amps_rms', unit: 'A', endpoint: 'amps' };
    }
    return { key: 'volts_rms', unit: 'V', endpoint: 'volts' };
}
function getSensorsByType(sensorType) {
    if (!Array.isArray(sensorsList)) return [];
    return sensorsList.filter(s => s && s.type === sensorType);
}
function showMsg(msg) {
    document.getElementById('calibrazione-msg').textContent = msg;
}
// Chart.js CDN
if (!window.Chart) {
  var script = document.createElement('script');
  script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
  document.head.appendChild(script);
}

let calibChart = null;
function showCalibInfoHtml(cal) {
    const container = document.getElementById('calibrazione-list');
    let html = '';
    const sensorType = getSensorType();
    const refLabel = sensorType === 'current' ? 'amps' : 'volts';
    const chartContainer = document.getElementById('calibrazione-chart-container');
    if (!cal) {
        container.innerHTML = '<em>Nessun dato di calibrazione.</em>';
        if (chartContainer) chartContainer.style.display = 'none';
        return;
    }
    // Baseline
    let hasBaseline = false;
    if (cal.baseline_mean !== undefined) {
        html += `<div style="margin-bottom:0.5em;">`;
        html += `<b>Baseline:</b> <span id='baseline-value'>${cal.baseline_mean}</span>`;
        html += `</div>`;
        hasBaseline = true;
    }
    // Punti
    let hasPoints = false;
    let points = [];
    // Log di debug e messaggi se mancano dati
    console.log("Dati calibrazione ricevuti:", cal);
    if (cal.points && cal.points.length) {
        html += '<b>Punti calibrazione:</b><ul style="margin:0 0 0 1.2em;">';
        cal.points.forEach((p,i) => {
            const refValue = getPointReferenceValue(p, sensorType);
            const displayRef = (refValue === undefined || refValue === null) ? '-' : refValue;
            html += `<li>rms_counts: ${p.rms_counts}, ${refLabel}: ${displayRef} <button class='btn-elimina-punto' data-idx='${i}'>Elimina</button></li>`;
            points.push(p);
        });
        html += '</ul>';
        hasPoints = true;
    } else {
        html += '<em>Nessun punto di calibrazione.</em>';
    }
    if (!hasBaseline) {
        showMsg("Attenzione: baseline mancante, grafico non mostrato.");
    } else if (!hasPoints) {
        showMsg("Attenzione: nessun punto di calibrazione, grafico non mostrato.");
    } else {
        showMsg('');
    }
    container.innerHTML = html;
    // Aggiungi handler ai pulsanti Elimina punto (dopo aver aggiornato l'HTML!)
    document.querySelectorAll('.btn-elimina-punto').forEach(btn => {
        btn.onclick = function() {
            const idx = this.getAttribute('data-idx');
            const sid = getSensorId();
            if (!sid) return showMsg('Seleziona un sensore!');
            showMsg('Eliminazione in corso...');
            fetch(`http://${ip}/calibrate/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ index: Number(idx), sensor_id: sid })
            })
            .then(r => r.json())
            .then(data => {
                showMsg('Punto eliminato!');
                fetchCalibInfo(); // aggiorna lista
            })
            .catch(() => showMsg('Errore durante eliminazione punto.'));
        };
    });
    // Mostra grafico se baseline e almeno un punto
    if (hasBaseline && hasPoints && window.Chart) {
        chartContainer.style.display = '';
        const ctx = document.getElementById('calibrazione-chart').getContext('2d');
        const data = {
            labels: points.map((p,i) => `P${i+1}`),
            datasets: [{
                label: 'ADC Counts',
                data: points
                    .map(p => ({x: Number(getPointReferenceValue(p, sensorType)), y: Number(p.rms_counts)}))
                    .filter(p => Number.isFinite(p.x) && Number.isFinite(p.y)),
                borderColor: 'rgba(32,120,240,1)',
                pointRadius: 4,
                borderWidth: 1.5,
                fill: false,
                tension: 0.1
            }]
        };
        if (calibChart) calibChart.destroy();
        calibChart = new Chart(ctx, {
            type: 'scatter',
            data: data,
            options: {
                plugins: {legend: {display: false}},
                scales: {
                    x: {title: {display: true, text: sensorType === 'current' ? 'Amps' : 'Volts'}},
                    y: {title: {display: true, text: 'rms_counts'}}
                }
            }
        });
    } else if (chartContainer) {
        chartContainer.style.display = 'none';
        if (calibChart) { calibChart.destroy(); calibChart = null; }
    }
}
function fetchCalibInfo() {
    const sid = getSensorId();
    if (!sid) return showCalibInfoHtml(null);
    fetch(`http://${ip}/calibrate?sensor_id=${sid}`)
        .then(r => r.json())
        .then(data => {
            const cal = data.cal || {};
            // Salva la calibrazione aggiornata globalmente
            window._lastCalibInfo = {sensor_id: sid, cal: cal};
            showCalibInfoHtml(cal);
        })
        .catch(() => showCalibInfoHtml(null));
}
if (select) {
    select.addEventListener('change', function() {
        if (this.value) {
            boxes.style.display = 'block';
            showMsg('');
            updateCalibButtons();
            fetchCalibInfo();
            // DEBUG: log cambio sensore
            console.log('Cambio sensore:', this.value, 'Tipo:', getSensorType());
            // Forza ricreazione canvas e chart delle misure
            let misureContent = document.getElementById('misure-content');
            let chart = document.getElementById('misure-chart');
            if (window._misureChart) { window._misureChart.destroy(); window._misureChart = null; }
            if (chart) {
                chart.remove();
            }
            // Ricrea il canvas
            let chartDiv = document.createElement('div');
            chartDiv.style.marginTop = '1em';
            let newCanvas = document.createElement('canvas');
            newCanvas.id = 'misure-chart';
            newCanvas.height = 180;
            newCanvas.width = 600;
            newCanvas.style.display = 'block';
            newCanvas.style.boxSizing = 'border-box';
            newCanvas.style.height = '180px';
            newCanvas.style.width = '600px';
            chartDiv.appendChild(newCanvas);
            misureContent.appendChild(chartDiv);
            let infoDiv = document.getElementById('misure-info-div');
            if (infoDiv) infoDiv.innerHTML = '';
            let effLabel = document.getElementById('misure-eff-label');
            if (effLabel) effLabel.style.display = 'none';
            let bisInfoDiv = document.getElementById('misure-bis-info-div');
            if (bisInfoDiv) bisInfoDiv.innerHTML = '';
            let bisRmsDiv = document.getElementById('misure-bis-rms');
            if (bisRmsDiv) {
                const bisMeta = getBisRmsMeta(getSensorType());
                bisRmsDiv.textContent = `${bisMeta.key}: - ${bisMeta.unit}`;
            }
            if (autoMisureBisTimeout) {
                clearTimeout(autoMisureBisTimeout);
                autoMisureBisTimeout = null;
            }
        } else {
            boxes.style.display = 'none';
            showMsg('');
            showCalibInfoHtml(null);
            // Nascondi anche grafico misure
            let misureContent = document.getElementById('misure-content');
            let chart = document.getElementById('misure-chart');
            if (window._misureChart) { window._misureChart.destroy(); window._misureChart = null; }
            if (chart) {
                chart.remove();
            }
            let infoDiv = document.getElementById('misure-info-div');
            if (infoDiv) infoDiv.innerHTML = '';
            let effLabel = document.getElementById('misure-eff-label');
            if (effLabel) effLabel.style.display = 'none';
            let bisInfoDiv = document.getElementById('misure-bis-info-div');
            if (bisInfoDiv) bisInfoDiv.innerHTML = '';
            let bisRmsDiv = document.getElementById('misure-bis-rms');
            if (bisRmsDiv) bisRmsDiv.textContent = 'volts_rms: - V';
            if (autoMisureBisTimeout) {
                clearTimeout(autoMisureBisTimeout);
                autoMisureBisTimeout = null;
            }
        }
    });
}
// Aggiorna la visibilità dei pulsanti in base al tipo sensore selezionato
function updateCalibButtons() {
    const type = getSensorType();
    const btnCorrente = document.getElementById('btn-corrente');
    const btnVolt = document.getElementById('btn-volt');
    if (btnCorrente) btnCorrente.style.display = (type === 'current') ? '' : 'none';
    if (btnVolt) btnVolt.style.display = (type === 'voltage') ? '' : 'none';
}
// Inizializza stato pulsanti
updateCalibButtons();
function callCalibEndpoint(url) {
    showMsg('Attendi...');
    fetch(url)
        .then(r => r.text())
        .then(t => showMsg('Risposta: ' + t))
        .catch(e => showMsg('Errore: ' + e));
}
const btnBaseline = document.getElementById('btn-baseline');
const btnCorrente = document.getElementById('btn-corrente');
const btnVolt = document.getElementById('btn-volt');
const powerVoltageSelect = document.getElementById('power-voltage-select');
const powerCurrentSelect = document.getElementById('power-current-select');
const btnAggiornaPotenza = document.getElementById('btn-aggiorna-potenza');
const powerMain = document.getElementById('power-main');
const powerDetails = document.getElementById('power-details');

function setPowerPlaceholder() {
    if (powerMain) powerMain.textContent = 'power_w: - W';
    if (powerDetails) powerDetails.innerHTML = '';
}

function populatePowerSensorSelects() {
    if (!powerVoltageSelect || !powerCurrentSelect) return;
    const voltageSensors = getSensorsByType('voltage');
    const currentSensors = getSensorsByType('current');

    powerVoltageSelect.innerHTML = '';
    powerCurrentSelect.innerHTML = '';

    if (voltageSensors.length === 0) {
        powerVoltageSelect.innerHTML = '<option value="">Nessun sensore tensione</option>';
        powerVoltageSelect.disabled = true;
    } else {
        voltageSensors.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = `${s.name || s.id} (${s.id})`;
            powerVoltageSelect.appendChild(opt);
        });
        powerVoltageSelect.disabled = false;
    }

    if (currentSensors.length === 0) {
        powerCurrentSelect.innerHTML = '<option value="">Nessun sensore corrente</option>';
        powerCurrentSelect.disabled = true;
    } else {
        currentSensors.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = `${s.name || s.id} (${s.id})`;
            powerCurrentSelect.appendChild(opt);
        });
        powerCurrentSelect.disabled = false;
    }
}

function fetchPower() {
    if (!powerVoltageSelect || !powerCurrentSelect) return;
    const voltageSensorId = powerVoltageSelect.value;
    const currentSensorId = powerCurrentSelect.value;

    if (!voltageSensorId || !currentSensorId) {
        setPowerPlaceholder();
        return;
    }

    if (btnAggiornaPotenza) btnAggiornaPotenza.disabled = true;
    if (powerMain) powerMain.textContent = 'power_w: ...';
    if (powerDetails) powerDetails.innerHTML = '';

    const n = 1600;
    const sr = 4000;

    fetch(`http://${ip}/power?voltage_sensor_id=${encodeURIComponent(voltageSensorId)}&current_sensor_id=${encodeURIComponent(currentSensorId)}&n=${n}&sr=${sr}&fast=1`)
        .then(r => r.json())
        .then(data => {
            if (!data || data.ok === false) {
                throw new Error('Risposta /power non valida');
            }

            const powerW = Number(data.power_w);
            const apparentPower = Number(data.apparent_power_va);
            const pf = Number(data.power_factor);
            const voltsRms = Number(data.volts_rms);
            const ampsRms = Number(data.amps_rms);

            if (powerMain) {
                powerMain.textContent = Number.isFinite(powerW)
                    ? `power_w: ${powerW.toFixed(3)} W`
                    : 'power_w: - W';
            }

            if (powerDetails) {
                const vMin = data.voltage && Number.isFinite(Number(data.voltage.min)) ? Number(data.voltage.min) : null;
                const vMax = data.voltage && Number.isFinite(Number(data.voltage.max)) ? Number(data.voltage.max) : null;
                const vBase = data.voltage && Number.isFinite(Number(data.voltage.baseline_mean)) ? Number(data.voltage.baseline_mean) : null;
                const cMin = data.current && Number.isFinite(Number(data.current.min)) ? Number(data.current.min) : null;
                const cMax = data.current && Number.isFinite(Number(data.current.max)) ? Number(data.current.max) : null;
                const cBase = data.current && Number.isFinite(Number(data.current.baseline_mean)) ? Number(data.current.baseline_mean) : null;

                powerDetails.innerHTML =
                    `<b>volts_rms:</b> ${Number.isFinite(voltsRms) ? voltsRms.toFixed(3) : '-'} V<br>` +
                    `<b>amps_rms:</b> ${Number.isFinite(ampsRms) ? ampsRms.toFixed(3) : '-'} A<br>` +
                    `<b>apparent_power_va:</b> ${Number.isFinite(apparentPower) ? apparentPower.toFixed(3) : '-'} VA<br>` +
                    `<b>power_factor:</b> ${Number.isFinite(pf) ? pf.toFixed(4) : '-'}<br>` +
                    `<b>clipping:</b> ${data.clipping ? 'SI' : 'NO'}<br>` +
                    `<b>mode:</b> ${data.mode || '-'}<br>` +
                    `<b>fast:</b> ${data.fast === true ? 'true' : data.fast === false ? 'false' : '-'}<br>` +
                    `<b>n:</b> ${Number.isFinite(Number(data.n)) ? Number(data.n) : '-'}<br>` +
                    `<b>sample_rate_hz:</b> ${Number.isFinite(Number(data.sample_rate_hz)) ? Number(data.sample_rate_hz) : '-'}<br>` +
                    `<b>voltage min/max/baseline:</b> ${vMin ?? '-'} / ${vMax ?? '-'} / ${vBase ?? '-'}<br>` +
                    `<b>current min/max/baseline:</b> ${cMin ?? '-'} / ${cMax ?? '-'} / ${cBase ?? '-'}`;
            }
        })
        .catch((e) => {
            console.log('Errore fetchPower:', e);
            setPowerPlaceholder();
        })
        .finally(() => {
            if (btnAggiornaPotenza) btnAggiornaPotenza.disabled = false;
        });
}

populatePowerSensorSelects();
setPowerPlaceholder();
if (btnAggiornaPotenza) btnAggiornaPotenza.onclick = fetchPower;

if (btnBaseline) btnBaseline.onclick = function() {
    const sid = getSensorId();
    if (!sid) return showMsg('Seleziona un sensore!');
    showMsg('Attendi...');
    fetch(`http://${ip}/calibrate?amp=0&sensor_id=${sid}&fast=1`)
        .then(r => r.json())
        .then(data => {
            showMsg('Baseline acquisita!');
            // Aggiorna la baseline se presente in saved o cal
            let newBaseline = undefined;
            if (data.saved && data.saved.baseline_mean !== undefined) {
                newBaseline = data.saved.baseline_mean;
            } else if (data.cal && data.cal.baseline_mean !== undefined) {
                newBaseline = data.cal.baseline_mean;
            }
            if (newBaseline !== undefined) {
                const el = document.getElementById('baseline-value');
                if (el) el.textContent = newBaseline;
            } else {
                showMsg('Baseline aggiornata, ma valore non ricevuto.');
            }
        })
        .catch(() => showMsg('Errore durante acquisizione baseline.'));
};
if (btnCorrente) btnCorrente.onclick = function() {
    const sid = getSensorId();
    if (!sid) return showMsg('Seleziona un sensore!');
    let a = prompt('Inserisci il valore della corrente (A):', '7.0');
    if (a === null || a.trim() === '' || isNaN(Number(a))) {
        showMsg('Valore corrente non valido!');
        return;
    }
    showMsg('Attendi...');
    fetch(`http://${ip}/calibrate?amp=${encodeURIComponent(a)}&sensor_id=${sid}&fast=1`)
        .then(r => r.json())
        .then(data => {
            showMsg('Punto di calibrazione corrente aggiunto!');
            fetchCalibInfo();
        })
        .catch(() => showMsg('Errore durante aggiunta punto corrente.'));
};
if (btnVolt) btnVolt.onclick = function() {
    const sid = getSensorId();
    if (!sid) return showMsg('Seleziona un sensore!');
    let v = prompt('Inserisci il valore della tensione (volt):', '220');
    if (v === null || v.trim() === '' || isNaN(Number(v))) {
        showMsg('Valore tensione non valido!');
        return;
    }
    showMsg('Attendi...');
    fetch(`http://${ip}/calibrate?volt=${encodeURIComponent(v)}&sensor_id=${sid}&fast=1`)
        .then(r => r.json())
        .then(data => {
            showMsg('Punto di calibrazione aggiunto!');
            fetchCalibInfo();
        })
        .catch(() => showMsg('Errore durante aggiunta punto.'));
};
// Inizializza stato pulsanti
updateCalibButtons();
// --- Misure ---
const btnMisure = document.getElementById('btn-aggiorna-misure');
let autoMisureBisTimeout = null;

let autoBisSwitch = null;
if (btnMisureBis) {
    const autoBisSwitchLabel = document.createElement('label');
    autoBisSwitchLabel.style.display = 'inline-flex';
    autoBisSwitchLabel.style.alignItems = 'center';
    autoBisSwitchLabel.style.marginLeft = '1em';

    autoBisSwitch = document.createElement('input');
    autoBisSwitch.type = 'checkbox';
    autoBisSwitch.id = 'auto-bis-switch';
    autoBisSwitch.style.marginRight = '0.5em';
    autoBisSwitch.checked = false;

    autoBisSwitchLabel.appendChild(autoBisSwitch);
    const autoBisSwitchText = document.createElement('span');
    autoBisSwitchText.textContent = 'Auto';
    autoBisSwitchLabel.appendChild(autoBisSwitchText);

    btnMisureBis.parentNode.insertBefore(autoBisSwitchLabel, btnMisureBis.nextSibling);

    autoBisSwitch.addEventListener('change', function() {
        if (autoBisSwitch.checked) {
            console.log('Levetta BIS su: AUTO');
        } else {
            console.log('Levetta BIS su: NO AUTO');
            if (autoMisureBisTimeout) {
                clearTimeout(autoMisureBisTimeout);
                autoMisureBisTimeout = null;
            }
        }
    });
}


function fetchMisure() {
    return new Promise((resolve) => {
        const sid = getSensorId();
        console.log('Sensore selezionato per misure:', sid);
        if (!sid) {
            document.getElementById('misure-content').textContent = 'Seleziona un sensore per vedere le misure.';
            resolve();
            return;
        }
        // Prendi i valori dagli input
        const n = 1024;
        const sr = 4000;
        const btn = document.getElementById('btn-aggiorna-misure');
        if (btn) btn.disabled = true;
        // Pulisci solo la parte testuale, non il canvas
        let misureContent = document.getElementById('misure-content');
        let chart = document.getElementById('misure-chart');
        Array.from(misureContent.children).forEach(child => {
            if (child.id !== 'misure-chart' && child.tagName !== 'DIV') misureContent.removeChild(child);
        });
        // Mostra messaggio di caricamento
        let loadingMsg = document.createElement('div');
        loadingMsg.id = 'misure-loading-msg';
        loadingMsg.textContent = 'Caricamento...';
        misureContent.insertBefore(loadingMsg, chart ? chart.parentNode.nextSibling : null);
        // Timeout helper
        function fetchWithTimeout(resource, options = {}) {
            const { timeout = 5000 } = options;
            return Promise.race([
                fetch(resource, options),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout richiesta')), timeout))
            ]);
        }
        fetchWithTimeout(`http://${ip}/adc/scope_counts?sensor_id=${sid}&n=${n}&sr=${sr}&fast=1`, {timeout: 5000})
            .then(r => {
                console.log('fetchWithTimeout: risposta ricevuta');
                return r.json();
            })
            .then(data => {
                console.log('fetchWithTimeout: dati json:', data);
                // Aggiorna solo la parte testuale e la lista dei campioni
                let misureContent = document.getElementById('misure-content');
                let chart = document.getElementById('misure-chart');
                console.log('misureContent:', misureContent, 'chart:', chart);
                // Rimuovi messaggio di caricamento
                let loadingMsg = document.getElementById('misure-loading-msg');
                if (loadingMsg) misureContent.removeChild(loadingMsg);
                // Se ci sono almeno 2 campioni, mostra grafico
                if (data && data.counts && Array.isArray(data.counts) && data.counts.length > 1) {
                    console.log('Dati validi, aggiorno grafico. Campioni:', data.counts.length);
                    // Aggiorna la parte testuale e la lista dei campioni
                    let infoDiv = document.getElementById('misure-info-div');
                    if (!infoDiv) {
                        infoDiv = document.createElement('div');
                        infoDiv.id = 'misure-info-div';
                        misureContent.insertBefore(infoDiv, chart ? chart.parentNode.nextSibling : null);
                    }
                    infoDiv.innerHTML = `<b>Campioni acquisiti:</b> ${data.counts.length}<br>` +
                        `<div id='misure-campioni' style='display:none; max-height:120px; overflow:auto; font-size:0.95em; background:#fff; border:1px solid #eee; padding:6px; margin-top:0.5em;'>` +
                        data.counts.slice(0,32).join(', ') + (data.counts.length>32 ? ' ...' : '') + '</div>';
                    // Canvas già presente, aggiorna solo i dati
                    const ctx = chart.getContext('2d');
                    if (!window._misureChart) {
                        window._misureChart = new Chart(ctx, {
                            type: 'scatter',
                            data: {
                                datasets: [{
                                    label: 'ADC Counts',
                                    data: data.counts.map((y, x) => ({x: x + 1, y})),
                                    backgroundColor: 'rgba(32,120,240,1)',
                                    pointRadius: 1.5,
                                    showLine: false,
                                    fill: false,
                                }]
                            },
                            options: {
                                plugins: {legend: {display: false}},
                                scales: {
                                    x: {title: {display: true, text: 'Campione'}},
                                    y: {title: {display: true, text: 'Counts'}}
                                }
                            }
                        });
                        console.log('Creato nuovo Chart.js');
                    } else {
                        window._misureChart.data.datasets[0].data = data.counts.map((y, x) => ({x: x + 1, y}));
                        window._misureChart.update();
                        console.log('Aggiornato Chart.js esistente');
                    }
                    // Calcolo valore efficace in Volt o Ampere se calibrazione disponibile
                    let valoreEff = null;
                    let labelEff = '';
                    // Recupera la calibrazione dal sensore selezionato
                    const sid = getSensorId();
                    const cal = window._lastCalibInfo && window._lastCalibInfo.sensor_id === sid ? (window._lastCalibInfo.cal || {}) : {};
                    if (window._lastCalibInfo && window._lastCalibInfo.sensor_id === sid) {
                        Object.assign(cal, window._lastCalibInfo.cal || {});
                    }
                    // Calcola RMS dei campioni rispetto alla baseline
                    let baseline = cal.baseline_mean;
                    if (typeof baseline !== 'number') baseline = 0;
                    let sum = 0;
                    for (let i = 0; i < data.counts.length; i++) {
                        let d = data.counts[i] - baseline;
                        sum += d * d;
                    }
                    let rms_counts = Math.sqrt(sum / data.counts.length);
                    // Determina tipo sensore e costante di calibrazione
                    let tipo = getSensorType();
                    if (tipo === 'voltage' && cal.k_V_per_count) {
                        valoreEff = cal.k_V_per_count * rms_counts;
                        labelEff = `Valore efficace: ${valoreEff.toFixed(2)} V`;
                    } else if (tipo === 'current' && cal.k_A_per_count) {
                        valoreEff = cal.k_A_per_count * rms_counts;
                        labelEff = `Valore efficace: ${valoreEff.toFixed(2)} A`;
                    }
                    // Mostra il label sotto il grafico
                    let effLabel = document.getElementById('misure-eff-label');
                    if (!effLabel) {
                        effLabel = document.createElement('div');
                        effLabel.id = 'misure-eff-label';
                        effLabel.style = 'margin-top:0.7em; color:#2a7ae2; font-weight:bold;';
                        misureContent.appendChild(effLabel);
                    }
                    if (valoreEff !== null) {
                        effLabel.textContent = labelEff;
                        effLabel.style.display = '';
                    } else {
                        effLabel.style.display = 'none';
                    }
                } else {
                    console.log('Dati non validi o meno di 2 campioni:', data);
                    // Rimuovi messaggio di caricamento
                    let loadingMsg = document.getElementById('misure-loading-msg');
                    if (loadingMsg) misureContent.removeChild(loadingMsg);
                    // Mostra solo canvas vuoto e messaggio
                    let infoDiv = document.getElementById('misure-info-div');
                    if (infoDiv) infoDiv.innerHTML = '<em>Dati non disponibili o formato non valido.</em>';
                    if (window._misureChart) { window._misureChart.destroy(); window._misureChart = null; }
                }
            })
            .catch((e) => {
                console.log('Errore fetchMisure:', e);
                document.getElementById('misure-content').textContent = 'Errore nel recupero misure: ' + (e && e.message ? e.message : e);
            })
            .finally(() => {
                console.log('fetchMisure: finally');
                if (btn) btn.disabled = false;
                resolve();
            });
    });
}



function fetchMisureBisVolts() {
    return new Promise((resolve) => {
        const sid = getSensorId();
        const sensorType = getSensorType();
        const bisMeta = getBisRmsMeta(sensorType);
        console.log('Sensore selezionato per misure BIS:', sid);
        const rmsDiv = document.getElementById('misure-bis-rms');
        const infoDiv = document.getElementById('misure-bis-info-div');
        const btn = document.getElementById('btn-aggiorna-misure-bis');

        if (!sid) {
            if (infoDiv) infoDiv.innerHTML = '';
            if (rmsDiv) rmsDiv.textContent = `${bisMeta.key}: - ${bisMeta.unit}`;
            resolve();
            return;
        }

        const n = 1024;
        const sr = 4000;

        if (btn) btn.disabled = true;
        if (infoDiv) infoDiv.innerHTML = '';
        if (rmsDiv) rmsDiv.textContent = `${bisMeta.key}: - ${bisMeta.unit}`;

        function fetchWithTimeout(resource, options = {}) {
            const { timeout = 5000 } = options;
            return Promise.race([
                fetch(resource, options),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout richiesta')), timeout))
            ]);
        }

        fetchWithTimeout(`http://${ip}/${bisMeta.endpoint}?sensor_id=${sid}&n=${n}&sr=${sr}&fast=1`, {timeout: 5000})
            .then(r => {
                console.log(`fetch /${bisMeta.endpoint}: risposta ricevuta`);
                return r.json();
            })
            .then(data => {
                console.log(`fetch /${bisMeta.endpoint}: dati json:`, data);
                if (!data || data.ok === false) {
                    throw new Error(`Risposta /${bisMeta.endpoint} non valida`);
                }

                if (infoDiv) infoDiv.innerHTML = '';
                const rmsValue = data[bisMeta.key] ?? data.volts_rms ?? data.amps_rms;
                if (rmsDiv) {
                    if (typeof rmsValue === 'number') {
                        rmsDiv.textContent = `${bisMeta.key}: ${rmsValue.toFixed(3)} ${bisMeta.unit}`;
                    } else {
                        rmsDiv.textContent = `${bisMeta.key}: - ${bisMeta.unit}`;
                    }
                }
            })
            .catch((e) => {
                console.log('Errore fetchMisureBisVolts:', e);
                if (infoDiv) infoDiv.innerHTML = '';
                if (rmsDiv) rmsDiv.textContent = `${bisMeta.key}: - ${bisMeta.unit}`;
            })
            .finally(() => {
                if (btn) btn.disabled = false;
                if (autoBisSwitch && autoBisSwitch.checked) {
                    autoMisureBisTimeout = setTimeout(() => {
                        fetchMisureBisVolts();
                    }, 5000);
                }
                resolve();
            });
    });
}


if (btnMisure) btnMisure.onclick = function() {
    fetchMisure();
};

if (btnMisureBis) btnMisureBis.onclick = function() {
    fetchMisureBisVolts();
};
