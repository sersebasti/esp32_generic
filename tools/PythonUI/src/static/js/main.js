// --- Variabili globali iniettate dal template ---
// ip, sensorsList

const select = document.getElementById('sensor-select');
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
    const chartContainer = document.getElementById('calibrazione-chart-container');
    if (!cal) {
        container.innerHTML = '<em>Nessun dato di calibrazione.</em>';
        if (chartContainer) chartContainer.style.display = 'none';
        return;
    }
    // Baseline
    let hasBaseline = false;
    if (cal.baseline_mean !== undefined) {
        html += `<div style=\"margin-bottom:0.5em;\">`;
        html += `<b>Baseline:</b> <span id='baseline-value'>${cal.baseline_mean}</span>`;
        html += `</div>`;
        hasBaseline = true;
    }
    // Punti
    let hasPoints = false;
    let points = [];
    if (cal.points && cal.points.length) {
        html += '<b>Punti calibrazione:</b><ul style="margin:0 0 0 1.2em;">';
        cal.points.forEach((p,i) => {
            html += `<li>rms_counts: ${p.rms_counts}, volts: ${p.volts} <button class='btn-elimina-punto' data-idx='${i}'>Elimina</button></li>`;
            points.push(p);
        });
        html += '</ul>';
        hasPoints = true;
    } else {
        html += '<em>Nessun punto di calibrazione.</em>';
    }
    container.innerHTML = html;
    // Aggiungi handler ai pulsanti Elimina punto
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
                label: 'Calibrazione (volts vs rms_counts)',
                data: points.map(p => ({x: p.volts, y: p.rms_counts})),
                backgroundColor: 'rgba(32, 120, 240, 0.3)',
                borderColor: 'rgba(32, 120, 240, 1)',
                showLine: true,
                fill: false,
                tension: 0.1,
                pointRadius: 5
            }]
        };
        if (calibChart) calibChart.destroy();
        calibChart = new Chart(ctx, {
            type: 'scatter',
            data: data,
            options: {
                plugins: {legend: {display: false}},
                scales: {
                    x: {title: {display: true, text: 'Volts'}},
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
        } else {
            boxes.style.display = 'none';
            showMsg('');
            showCalibInfoHtml(null);
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
    callCalibEndpoint(`http://${ip}/calibrate?amp=7.0&sensor_id=${sid}&fast=1`);
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
function fetchMisure() {
    const sid = getSensorId();
    console.log('Sensore selezionato per misure:', sid);
    if (!sid) {
        document.getElementById('misure-content').textContent = 'Seleziona un sensore per vedere le misure.';
        return;
    }
    document.getElementById('misure-content').textContent = 'Caricamento...';
    fetch(`http://${ip}/adc/scope_counts?sensor_id=${sid}&n=1024&sr=4000&fast=0`)
        .then(r => r.json())
        .then(data => {
            let html = '';
            const chartId = 'misure-chart';
            // Se ci sono almeno 2 campioni, mostra grafico
            if (data && data.counts && Array.isArray(data.counts) && data.counts.length > 1) {
                html += `<b>Campioni acquisiti:</b> ${data.counts.length}<br>`;
                html += `<div style='max-height:120px; overflow:auto; font-size:0.95em; background:#fff; border:1px solid #eee; padding:6px; margin-top:0.5em;'>`;
                html += data.counts.slice(0,32).join(', ') + (data.counts.length>32 ? ' ...' : '');
                html += '</div>';
                html += `<div style='margin-top:1em;'><canvas id='${chartId}' height='180'></canvas></div>`;
            } else {
                html = '<em>Dati non disponibili o formato non valido.</em>';
            }
            document.getElementById('misure-content').innerHTML = html;
            // Mostra grafico se possibile
            if (window.Chart && data && data.counts && Array.isArray(data.counts) && data.counts.length > 1) {
                const ctx = document.getElementById(chartId).getContext('2d');
                if (window._misureChart) { window._misureChart.destroy(); }
                window._misureChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: data.counts.map((_,i) => i+1),
                        datasets: [{
                            label: 'ADC Counts',
                            data: data.counts,
                            borderColor: 'rgba(32,120,240,1)',
                            backgroundColor: 'rgba(32,120,240,0.15)',
                            pointRadius: 0,
                            borderWidth: 1.5,
                            fill: true,
                            tension: 0.1
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
            }
        })
        .catch(() => {
            document.getElementById('misure-content').textContent = 'Errore nel recupero misure.';
        });
}
if (btnMisure) btnMisure.onclick = fetchMisure;
