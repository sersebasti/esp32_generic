# wifi_ui.py
# Pagina HTML minimale per gestire le reti Wi-Fi:
# - mostra reti configurate (da /wifi/list) e reti disponibili (da /wifi/scan)
# - permette di aggiungere una rete (/wifi/add)
# - permette di eliminare una rete (/wifi/delete)
# - riavvia il dispositivo (/reboot)

def page():
    html = """
<!doctype html><html><head><meta charset="utf-8">
<title>WiFi Setup</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:16px;line-height:1.35}
h1{font-size:20px;margin:8px 0}
h2{font-size:16px;margin:8px 0}
section{border:1px solid #ddd;border-radius:8px;padding:12px;margin:12px 0}
label{display:block;margin:6px 0}
input,button{font-size:14px;padding:6px 8px;margin:4px 0}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #eee;padding:6px;font-size:13px;text-align:left}
.badge{padding:2px 6px;border-radius:10px;background:#eee}
.ok{color:#0a0}
.err{color:#a00}
small{color:#666}
#msg,#addMsg{min-height:1.3em}
.hide{display:none}
</style>
</head><body>
<h1>Configurazione Wi-Fi</h1>

<section>
  <button id="btnRefresh">🔄 Aggiorna liste</button>
  <button id="btnReboot">🔁 Riavvia dispositivo</button>
  <div id="msg"></div>
</section>

<section>
  <h2>Reti disponibili (scan)</h2>
  <table id="scanTbl"><thead>
    <tr><th>SSID</th><th>RSSI</th><th>Auth</th><th></th></tr>
  </thead><tbody></tbody></table>
  <small>Se non vedi la tua rete, premi “Aggiorna liste”.</small>
</section>

<section>
  <h2>Reti configurate (wifi.json)</h2>
  <table id="cfgTbl"><thead>
    <tr><th>#</th><th>SSID</th><th class="col-conn">Connessa</th><th></th></tr>
  </thead><tbody></tbody></table>
</section>

<section>
  <h2>Aggiungi rete</h2>
  <label>SSID <input id="ssid" placeholder="Nome rete"></label>
  <label>Password <input id="pwd" placeholder="Password" type="password"></label>
  <!--<label>Priorità (1 = più alta) <input id="prio" type="number" min="1" step="1" placeholder="opzionale"></label>-->
  <button id="btnAdd">➕ Aggiungi</button>
  <div id="addMsg"></div>
</section>

<script>
function qs(x){return document.querySelector(x)}
function qsa(x){return Array.from(document.querySelectorAll(x))}
function msg(el, t, ok){ el.innerHTML = '<span class="'+(ok?'ok':'err')+'">'+t+'</span>' }

async function getJSON(url){
  const r = await fetch(url);
  if(!r.ok) throw new Error('HTTP '+r.status);
  return r.json();
}
async function postJSON(url, data){
  const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  if(!r.ok) throw new Error('HTTP '+r.status);
  return r.json();
}

/* --- Mostra/nasconde la colonna "Connessa" in base allo stato STA --- */
let showConnCol = false; // default: nascosta (AP setup)

function toggleConnColumn(show){
  qsa('.col-conn').forEach(el=>{
    if(show) el.classList.remove('hide'); else el.classList.add('hide');
  });
}
function COLSPAN(){ return showConnCol ? 4 : 3; }

async function initMode(){
  showConnCol = false;
  try{
    const s = await getJSON('/status');
    // Supporta sia {"sta_connected": true} sia {"wifi":{"sta":{"active":...,"connected":...}}}
    const staConn = !!(s && (s.sta_connected === true ||
                   (s.wifi && s.wifi.sta && s.wifi.sta.connected === true)));
    const staActive = !!(s && (s.wifi && s.wifi.sta && s.wifi.sta.active === true));
    showConnCol = staConn || staActive; // mostra solo se lo STA è attivo/valido
  }catch(e){
    showConnCol = false; // se /status non c'è, assumo AP setup
  }
  toggleConnColumn(showConnCol);
}

async function loadScan(){
  const tbody = qs('#scanTbl tbody'); tbody.innerHTML = '<tr><td colspan="4">Scanning…</td></tr>';
  try{
    const data = await getJSON('/wifi/scan');
    tbody.innerHTML = '';
    data.forEach(n=>{
      const tr = document.createElement('tr');
      tr.innerHTML = '<td>'+n.ssid+'</td><td>'+n.rssi+'</td><td>'+ (n.auth||'') +'</td>'+
                     '<td><button data-ssid="'+n.ssid+'">Aggiungi…</button></td>';
      tbody.appendChild(tr);
    });
    qsa('#scanTbl button').forEach(b=>{
      b.onclick = ()=>{
        qs('#ssid').value = b.getAttribute('data-ssid');
        qs('#pwd').focus();
      };
    });
  }catch(e){
    tbody.innerHTML = '<tr><td colspan="4" class="err">Scan fallito</td></tr>';
  }
}

async function loadCfg(){
  const tbody = qs('#cfgTbl tbody'); tbody.innerHTML = '<tr><td colspan="'+COLSPAN()+'">Carico…</td></tr>';
  try{
    const data = await getJSON('/wifi/list');
    tbody.innerHTML = '';
    (data.configured_networks||[]).forEach((n,i)=>{
      const tr = document.createElement('tr');
      const left = '<td>'+(n.priority||i+1)+'</td><td>'+n.ssid+'</td>';
      const conn = showConnCol ? ('<td class="col-conn">'+(n.connected?'<span class="badge">connessa</span>':'')+'</td>') : '';
      const right = '<td><button data-ssid="'+n.ssid+'">Elimina</button></td>';
      tr.innerHTML = left + conn + right;
      tbody.appendChild(tr);
    });
    qsa('#cfgTbl button').forEach(b=>{
      b.onclick = async ()=>{
        const s = b.getAttribute('data-ssid');
        if(!confirm('Eliminare "'+s+'"?')) return;
        try{
          const r = await postJSON('/wifi/delete', {ssid:s});
          if(r.ok){ loadCfg(); msg(qs('#msg'),'Eliminata: '+s,true); }
          else{ msg(qs('#msg'),'Errore: '+(r.message||'fail'),false); }
        }catch(e){ msg(qs('#msg'),'Errore eliminazione',false); }
      };
    });
  }catch(e){
    tbody.innerHTML = '<tr><td colspan="'+COLSPAN()+'" class="err">Impossibile leggere wifi.json</td></tr>';
  }
}

qs('#btnAdd').onclick = async ()=>{
  const ssid = qs('#ssid').value.trim();
  const pwd  = qs('#pwd').value;
  const prio = parseInt(qs('#prio').value||'0',10);
  if(!ssid){ msg(qs('#addMsg'),'SSID mancante',false); return; }
  try{
    const r = await postJSON('/wifi/add', {ssid:ssid, password:pwd, priority: isNaN(prio)?undefined:prio});
    if(r.ok){ msg(qs('#addMsg'),'Aggiunta: '+ssid,true); qs('#pwd').value=''; loadCfg(); }
    else{ msg(qs('#addMsg'),'Errore: '+(r.message||'fail'),false); }
  }catch(e){
    msg(qs('#addMsg'),'Errore richiesta',false);
  }
};

qs('#btnRefresh').onclick = async ()=>{
  await initMode();
  loadScan(); loadCfg();
};
qs('#btnReboot').onclick = async ()=>{
  try{
    await postJSON('/reboot',{});
    msg(qs('#msg'),'Riavvio…',true);
    setTimeout(()=>location.reload(), 3000);
  }catch(e){
    msg(qs('#msg'),'Errore riavvio',false);
  }
};

/* Avvio: rileva modalità → carica tabelle */
initMode().then(()=>{ loadScan(); loadCfg(); });
</script>
</body></html>
"""
    return html.encode("utf-8")
