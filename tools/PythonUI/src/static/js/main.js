window.esp32Ui = function esp32Ui(defaultIp) {
  return {
    ip: defaultIp || '192.168.1.116',
    statusMessage: '',
    sensors: [],
    selectedSensorId: '',
    sampleN: 1024,
    sampleSr: 4000,
    sampleYMin: 0,
    sampleYMax: 4500,

    powerVoltageSensorId: '',
    powerCurrentSensorId: '',
    powerData: { watt: null, volt: null, amp: null, pf: null },

    measureData: null,
    sampleData: null,

    calibrationMessage: '',
    calibrationBaseline: null,
    calibrationPoints: [],
    calibrationBySensor: {},
    calibrationChartVisible: false,

    loading: {
      connect: false,
      measure: false,
      sample: false,
      power: false,
      calibrate: false,
    },

    autoMeasure: false,
    autoSample: false,
    autoPower: false,

    _measureTimer: null,
    _sampleTimer: null,
    _powerTimer: null,
    _chart: null,
    _calibrationChart: null,

    init() {
      try {
        const storedYMin = Number(window.localStorage.getItem('sampleYMin'));
        if (Number.isFinite(storedYMin) && storedYMin >= 0) {
          this.sampleYMin = Math.round(storedYMin);
        }
      } catch {
      }

      try {
        const storedYMax = Number(window.localStorage.getItem('sampleYMax'));
        if (Number.isFinite(storedYMax) && storedYMax > 0) {
          this.sampleYMax = Math.round(storedYMax);
        }
      } catch {
      }

      this.$watch('autoMeasure', (v) => {
        if (v) this.fetchMeasure();
        else this.clearTimer('_measureTimer');
      });
      this.$watch('autoSample', (v) => {
        if (v) this.fetchSample();
        else this.clearTimer('_sampleTimer');
      });
      this.$watch('autoPower', (v) => {
        if (v) this.fetchPower();
        else this.clearTimer('_powerTimer');
      });
      this.$watch('powerVoltageSensorId', () => {
        this.ensureCalibrationStatus(this.powerVoltageSensorId);
      });
      this.$watch('powerCurrentSensorId', () => {
        this.ensureCalibrationStatus(this.powerCurrentSensorId);
      });
      this.$watch('selectedSensorId', () => {
        this.measureData = null;
        this.sampleData = null;
        this.calibrationMessage = '';
        if (this._chart) {
          this._chart.destroy();
          this._chart = null;
        }
        this.fetchCalibrationInfo();
      });
    },

    get measureRawPretty() {
      return this.pretty(this.measureData);
    },

    get sampleRawPretty() {
      return this.pretty(this.sampleData);
    },

    get powerRawPretty() {
      return this.pretty(this.powerData && this.powerData._raw ? this.powerData._raw : null);
    },

    get voltageSensors() {
      return this.sensors.filter((s) => (s.type || '').toLowerCase().includes('volt'));
    },

    get currentSensors() {
      return this.sensors.filter((s) => (s.type || '').toLowerCase().includes('curr'));
    },

    fmt(value) {
      if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
      return Number(value).toFixed(3);
    },

    pretty(obj) {
      if (!obj) return 'Nessun dato';
      try {
        return JSON.stringify(obj, null, 2);
      } catch {
        return String(obj);
      }
    },

    measureLabel() {
      if (!this.measureData) return 'Valore: -';
      const sensor = this.sensors.find((s) => String(s.id) === String(this.selectedSensorId));
      const isCurrent = (sensor?.type || '').toLowerCase().includes('curr');
      const rms = isCurrent
        ? (this.measureData.amps_rms ?? this.measureData.rms ?? this.measureData.value ?? this.measureData.val ?? null)
        : (this.measureData.volts_rms ?? this.measureData.rms ?? this.measureData.value ?? this.measureData.val ?? null);
      if (rms === null || rms === undefined) return 'Valore: -';
      return `${isCurrent ? 'Amper (rms)' : 'Volt (rms)'}: ${this.fmt(rms)}`;
    },

    selectedSensor() {
      return this.sensors.find((s) => String(s.id) === String(this.selectedSensorId)) || null;
    },

    selectedSensorType() {
      return (this.selectedSensor()?.type || '').toLowerCase();
    },

    showCurrentPointButton() {
      return this.selectedSensorType() === 'current';
    },

    showVoltagePointButton() {
      return this.selectedSensorType() === 'voltage';
    },

    calibrationBaselineText() {
      if (this.calibrationBaseline === null || this.calibrationBaseline === undefined) return '-';
      return String(this.calibrationBaseline);
    },

    canQuickMeasure() {
      const hasBaseline = this.calibrationBaseline !== null && this.calibrationBaseline !== undefined;
      const hasPoint = Array.isArray(this.calibrationPoints) && this.calibrationPoints.length > 0;
      return hasBaseline && hasPoint;
    },

    hasCalibrationForSensor(sensorId) {
      if (!sensorId) return false;
      const info = this.calibrationBySensor[String(sensorId)];
      if (!info) return false;
      return info.baseline !== null && info.baseline !== undefined && Number(info.points || 0) > 0;
    },

    canMeasurePower() {
      return this.hasCalibrationForSensor(this.powerVoltageSensorId) && this.hasCalibrationForSensor(this.powerCurrentSensorId);
    },

    setCalibrationStatus(sensorId, baseline, points) {
      if (!sensorId) return;
      this.calibrationBySensor = {
        ...this.calibrationBySensor,
        [String(sensorId)]: {
          baseline,
          points: Array.isArray(points) ? points.length : 0,
        },
      };
    },

    async ensureCalibrationStatus(sensorId) {
      if (!sensorId) return;
      const key = String(sensorId);
      if (this.calibrationBySensor[key]) return;
      try {
        const data = await this.fetchJson(`http://${this.ip}/calibrate?sensor_id=${encodeURIComponent(key)}`);
        const cal = data?.cal ?? data ?? {};
        this.setCalibrationStatus(key, cal?.baseline_mean ?? null, Array.isArray(cal?.points) ? cal.points : []);
      } catch {
        this.setCalibrationStatus(key, null, []);
      }
    },

    calibrationPointReferenceValue(point) {
      const type = this.selectedSensorType();
      if (type === 'current') return point?.amps ?? point?.amp ?? point?.current ?? point?.volts ?? null;
      return point?.volts ?? point?.volt ?? point?.amp ?? point?.amps ?? null;
    },

    calibrationPointText(point) {
      const refLabel = this.selectedSensorType() === 'current' ? 'A' : 'V';
      const ref = this.calibrationPointReferenceValue(point);
      const rms = point?.rms_counts ?? '-';
      return `rms_counts: ${rms}, ref (${refLabel}): ${ref ?? '-'}`;
    },

    normalizeSensors(rawSensors) {
      if (!Array.isArray(rawSensors)) return [];
      return rawSensors
        .filter((s) => s && s.id && s.type)
        .map((s) => ({
          id: String(s.id),
          type: String(s.type).toLowerCase(),
          adc_pin: s.adc_pin,
          name: s.name || s.id,
        }));
    },

    sensorOptionLabel(sensor) {
      const name = sensor?.name || sensor?.id || 'n/a';
      const type = sensor?.type || 'n/a';
      const hasPin = sensor?.adc_pin !== undefined && sensor?.adc_pin !== null;
      return hasPin ? `${name} (${type}) (pin ${sensor.adc_pin})` : `${name} (${type})`;
    },

    async connect() {
      this.loading.connect = true;
      try {
        const sensorsWrap = await this.fetchJson(`http://${this.ip}/sensors`);

        if (!sensorsWrap || sensorsWrap.ok !== true || !Array.isArray(sensorsWrap.sensors)) {
          throw new Error('Risposta /sensors non valida');
        }

        this.sensors = this.normalizeSensors(sensorsWrap.sensors);

        this.selectedSensorId = this.sensors[0]?.id || '';
        this.powerVoltageSensorId = this.voltageSensors[0]?.id || '';
        this.powerCurrentSensorId = this.currentSensors[0]?.id || '';
        await this.fetchCalibrationInfo();
        await this.ensureCalibrationStatus(this.powerVoltageSensorId);
        await this.ensureCalibrationStatus(this.powerCurrentSensorId);

        this.statusMessage = `Connesso a ${this.ip}: trovati ${this.sensors.length} sensori`;
      } catch (err) {
        this.statusMessage = `Errore connessione: ${err.message}`;
        this.sensors = [];
        this.selectedSensorId = '';
        this.powerVoltageSensorId = '';
        this.powerCurrentSensorId = '';
        this.resetCalibrationState();
      } finally {
        this.loading.connect = false;
      }
    },

    resetCalibrationState() {
      this.calibrationBaseline = null;
      this.calibrationPoints = [];
      this.calibrationChartVisible = false;
      if (this._calibrationChart) {
        this._calibrationChart.destroy();
        this._calibrationChart = null;
      }
    },

    async fetchCalibrationInfo() {
      if (!this.selectedSensorId) {
        this.resetCalibrationState();
        return;
      }
      try {
        const data = await this.fetchJson(`http://${this.ip}/calibrate?sensor_id=${encodeURIComponent(this.selectedSensorId)}`);
        const cal = data?.cal ?? data ?? {};
        this.calibrationBaseline = cal?.baseline_mean ?? null;
        this.calibrationPoints = Array.isArray(cal?.points) ? cal.points : [];
        this.setCalibrationStatus(this.selectedSensorId, this.calibrationBaseline, this.calibrationPoints);
        this.calibrationChartVisible = this.calibrationBaseline !== null && this.calibrationPoints.length > 0;
        if (this.calibrationChartVisible) {
          this.$nextTick(() => this.renderCalibrationChart());
        } else if (this._calibrationChart) {
          this._calibrationChart.destroy();
          this._calibrationChart = null;
        }
      } catch {
        this.setCalibrationStatus(this.selectedSensorId, null, []);
        this.resetCalibrationState();
      }
    },

    renderCalibrationChart() {
      const canvas = document.getElementById('calibration-chart');
      if (!canvas || !window.Chart) return;

      const points = this.calibrationPoints
        .map((p) => ({
          x: Number(this.calibrationPointReferenceValue(p)),
          y: Number(p?.rms_counts),
        }))
        .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));

      if (points.length === 0) return;

      if (this._calibrationChart) {
        this._calibrationChart.destroy();
        this._calibrationChart = null;
      }

      try {
        this._calibrationChart = new Chart(canvas.getContext('2d'), {
          type: 'scatter',
          data: {
            datasets: [{
              label: 'Calibrazione',
              data: points,
              borderColor: 'rgba(32,120,240,1)',
              pointRadius: 4,
              borderWidth: 1.5,
              showLine: false,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            legend: { display: false },
            scales: {
              xAxes: [{
                display: true,
                scaleLabel: { display: true, labelString: this.selectedSensorType() === 'current' ? 'Amps' : 'Volts' },
              }],
              yAxes: [{
                display: true,
                scaleLabel: { display: true, labelString: 'rms_counts' },
              }],
            },
          },
        });
      } catch {
        this._calibrationChart = null;
      }
    },

    async fetchMeasure() {
      if (!this.selectedSensorId) return;
      if (!this.canQuickMeasure()) {
        this.measureData = { error: 'Calibrazione incompleta: acquisisci baseline e almeno un punto.' };
        return;
      }
      this.loading.measure = true;
      try {
        const type = this.selectedSensorType();
        const endpoint = type.includes('volt') ? 'volts' : 'amps';
        const q = `n=1024&sr=4000&sensor_id=${encodeURIComponent(this.selectedSensorId)}&fast=1`;
        const data = await this.fetchJson(`http://${this.ip}/${endpoint}?${q}`);
        if (data && data.ok === false) {
          throw new Error(data.err || 'misura_non_valida');
        }
        this.measureData = data;
      } catch (err) {
        this.measureData = { error: err.message };
      } finally {
        this.loading.measure = false;
        this.loopIfAuto('autoMeasure', '_measureTimer', () => this.fetchMeasure(), 1200);
      }
    },

    async fetchSample() {
      if (!this.selectedSensorId) return;
      this.loading.sample = true;
      try {
        const q = `sensor_id=${encodeURIComponent(this.selectedSensorId)}&n=${encodeURIComponent(this.sampleN)}&sr=${encodeURIComponent(this.sampleSr)}&fast=1&binary=true`;
        const data = await this.fetchSampleData(`http://${this.ip}/adc/scope_counts?${q}`);
        this.sampleData = data;
        this.renderSampleChart(data);
      } catch (err) {
        this.sampleData = { error: err.message };
      } finally {
        this.loading.sample = false;
        this.loopIfAuto('autoSample', '_sampleTimer', () => this.fetchSample(), 1500);
      }
    },

    async fetchPower() {
      if (!this.powerVoltageSensorId || !this.powerCurrentSensorId) return;
      this.loading.power = true;
      try {
        const q = `voltage_sensor_id=${encodeURIComponent(this.powerVoltageSensorId)}&current_sensor_id=${encodeURIComponent(this.powerCurrentSensorId)}&n=1600&sr=4000&fast=1`;
        const data = await this.fetchJson(`http://${this.ip}/power?${q}`);
        this.powerData = {
          watt: data?.watt ?? data?.power_w ?? data?.p,
          volt: data?.volt ?? data?.volts_rms ?? data?.vrms ?? data?.v,
          amp: data?.amp ?? data?.amps_rms ?? data?.irms ?? data?.i,
          pf: data?.pf ?? data?.power_factor,
          _raw: data,
        };
      } catch (err) {
        this.powerData = { watt: null, volt: null, amp: null, pf: null, _raw: { error: err.message } };
      } finally {
        this.loading.power = false;
        this.loopIfAuto('autoPower', '_powerTimer', () => this.fetchPower(), 1200);
      }
    },

    async acquireBaseline() {
      if (!this.selectedSensorId) return;
      this.loading.calibrate = true;
      try {
        const data = await this.fetchJson(`http://${this.ip}/calibrate?amp=0&sensor_id=${encodeURIComponent(this.selectedSensorId)}&fast=1`);
        this.calibrationMessage = `Baseline acquisita: ${this.pretty(data)}`;
        await this.fetchCalibrationInfo();
      } catch (err) {
        this.calibrationMessage = `Errore baseline: ${err.message}`;
      } finally {
        this.loading.calibrate = false;
      }
    },

    async addCurrentPoint() {
      if (!this.selectedSensorId) return;
      if (!this.showCurrentPointButton()) return;
      const amp = window.prompt('Inserisci il valore della corrente (A):', '7.0');
      if (amp === null) return;
      this.loading.calibrate = true;
      try {
        const data = await this.fetchJson(`http://${this.ip}/calibrate?amp=${encodeURIComponent(amp)}&sensor_id=${encodeURIComponent(this.selectedSensorId)}&fast=1`);
        this.calibrationMessage = `Punto corrente aggiunto: ${this.pretty(data)}`;
        await this.fetchCalibrationInfo();
      } catch (err) {
        this.calibrationMessage = `Errore calibrazione corrente: ${err.message}`;
      } finally {
        this.loading.calibrate = false;
      }
    },

    async addVoltagePoint() {
      if (!this.selectedSensorId) return;
      if (!this.showVoltagePointButton()) return;
      const volt = window.prompt('Inserisci il valore della tensione (V):', '220');
      if (volt === null) return;
      this.loading.calibrate = true;
      try {
        const data = await this.fetchJson(`http://${this.ip}/calibrate?volt=${encodeURIComponent(volt)}&sensor_id=${encodeURIComponent(this.selectedSensorId)}&fast=1`);
        this.calibrationMessage = `Punto tensione aggiunto: ${this.pretty(data)}`;
        await this.fetchCalibrationInfo();
      } catch (err) {
        this.calibrationMessage = `Errore calibrazione tensione: ${err.message}`;
      } finally {
        this.loading.calibrate = false;
      }
    },

    async deleteCalibrationPoint(index) {
      if (!this.selectedSensorId) return;
      this.loading.calibrate = true;
      try {
        const payload = {
          index,
          sensor_id: this.selectedSensorId,
        };
        const data = await this.postJson(`http://${this.ip}/calibrate/delete`, payload);
        if (data && data.ok === false) {
          throw new Error(data.err || 'delete_failed');
        }
        this.calibrationMessage = `Punto calibrazione eliminato: ${this.pretty(data)}`;
        await this.fetchCalibrationInfo();
      } catch (err) {
        this.calibrationMessage = `Errore elimina punto: ${err.message}`;
      } finally {
        this.loading.calibrate = false;
      }
    },

    async fetchJson(url) {
      const parsed = new URL(url, window.location.origin);
      const ip = parsed.host;
      const path = `${parsed.pathname}${parsed.search}`;
      const proxyUrl = `/api/generic-get?ip=${encodeURIComponent(ip)}&path=${encodeURIComponent(path)}`;

      const response = await fetch(proxyUrl, { method: 'GET' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    },

    async postJson(url, payload) {
      const parsed = new URL(url, window.location.origin);
      const ip = parsed.host;
      const path = `${parsed.pathname}${parsed.search}`;
      const proxyUrl = '/api/generic-post';

      const response = await fetch(proxyUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip, path, payload }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      return response.json();
    },

    async fetchSampleData(url) {
      const parsed = new URL(url, window.location.origin);
      const ip = parsed.host;
      const path = `${parsed.pathname}${parsed.search}`;
      const proxyUrl = `/api/generic-get?ip=${encodeURIComponent(ip)}&path=${encodeURIComponent(path)}`;

      const response = await fetch(proxyUrl, { method: 'GET' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const contentType = (response.headers.get('content-type') || '').toLowerCase();
      if (contentType.includes('application/octet-stream')) {
        const buffer = await response.arrayBuffer();
        return this.decodeScopeCountsBinary(buffer);
      }

      return response.json();
    },

    decodeScopeCountsBinary(buffer) {
      const view = new DataView(buffer);
      if (view.byteLength < 14) {
        throw new Error('Binary payload troppo corto');
      }

      const magic = String.fromCharCode(
        view.getUint8(0),
        view.getUint8(1),
        view.getUint8(2),
        view.getUint8(3),
      );
      if (magic !== 'SCB1') {
        throw new Error(`Header binario non valido: ${magic}`);
      }

      const version = view.getUint16(4, true);
      const n = view.getUint32(6, true);
      const sampleRateHz = view.getUint32(10, true);
      const expectedSize = 14 + (n * 2);
      if (view.byteLength < expectedSize) {
        throw new Error('Payload binario incompleto');
      }

      const counts = new Array(n);
      let offset = 14;
      for (let index = 0; index < n; index += 1) {
        counts[index] = view.getUint16(offset, true);
        offset += 2;
      }

      return {
        ok: true,
        mode: 'binary',
        version,
        n,
        sample_rate_hz: sampleRateHz,
        counts,
      };
    },

    changeSampleYMin() {
      const current = Number(this.sampleYMin) || 0;
      const raw = window.prompt('Imposta Y min (counts):', String(current));
      if (raw === null) return;

      const parsed = Number(raw);
      if (!Number.isFinite(parsed) || parsed < 0) {
        this.statusMessage = 'Y min non valido';
        return;
      }

      const nextMin = Math.round(parsed);
      if (nextMin >= this.sampleYMax) {
        this.statusMessage = 'Y min deve essere minore di Y max';
        return;
      }

      this.sampleYMin = nextMin;
      try {
        window.localStorage.setItem('sampleYMin', String(this.sampleYMin));
      } catch {
      }

      if (this.sampleData) {
        this.renderSampleChart(this.sampleData);
      }
    },

    changeSampleYMax() {
      const current = Number(this.sampleYMax) || 4500;
      const raw = window.prompt('Imposta Y max (counts):', String(current));
      if (raw === null) return;

      const parsed = Number(raw);
      if (!Number.isFinite(parsed) || parsed <= 0) {
        this.statusMessage = 'Y max non valido';
        return;
      }

      const nextMax = Math.round(parsed);
      if (nextMax <= this.sampleYMin) {
        this.statusMessage = 'Y max deve essere maggiore di Y min';
        return;
      }

      this.sampleYMax = nextMax;
      try {
        window.localStorage.setItem('sampleYMax', String(this.sampleYMax));
      } catch {
      }

      if (this.sampleData) {
        this.renderSampleChart(this.sampleData);
      }
    },

    renderSampleChart(data) {
      const canvas = document.getElementById('sample-chart');
      if (!canvas || !window.Chart) return;

      let values = [];
      if (Array.isArray(data?.counts)) values = data.counts;
      else if (Array.isArray(data?.values)) values = data.values;
      else if (Array.isArray(data?.samples)) values = data.samples;
      else if (Array.isArray(data?.adc)) values = data.adc;

      if (!Array.isArray(values) || values.length === 0) return;

      const safeValues = values
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value));

      if (safeValues.length === 0) return;

      const scatterPoints = safeValues.map((value, index) => ({ x: index + 1, y: value }));

      if (this._chart) {
        this._chart.destroy();
        this._chart = null;
      }

      try {
        this._chart = new Chart(canvas.getContext('2d'), {
          type: 'scatter',
          data: {
            datasets: [{
              label: 'Campioni',
              data: scatterPoints,
              borderColor: '#2f83eb',
              borderWidth: 1,
              pointRadius: 1,
              pointHoverRadius: 5,
              pointBackgroundColor: '#2f83eb',
              pointBorderColor: '#2f83eb',
              showLine: false,
              fill: false,
              lineTension: 0.12,
            }],
          },
          options: {
            responsive: false,
            maintainAspectRatio: false,
            animation: false,
            legend: { display: false },
            scales: {
              xAxes: [{
                type: 'linear',
                display: true,
                scaleLabel: { display: false },
                ticks: { min: 1, max: safeValues.length, maxTicksLimit: 10 },
              }],
              yAxes: [{
                display: true,
                scaleLabel: { display: false },
                ticks: { min: this.sampleYMin, max: this.sampleYMax, stepSize: 500 },
              }],
            },
          },
        });
      } catch {
        this._chart = null;
      }
    },

    loopIfAuto(flagName, timerName, callback, delayMs) {
      this.clearTimer(timerName);
      if (this[flagName]) {
        this[timerName] = window.setTimeout(callback, delayMs);
      }
    },

    clearTimer(timerName) {
      if (this[timerName]) {
        clearTimeout(this[timerName]);
        this[timerName] = null;
      }
    },
  };
}
