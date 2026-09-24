const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n,d=2) => n==null?'—':Number(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const cls = n => n==null?'':(n>=0?'pos':'neg');
async function api(path, opts={}){
  const r = await fetch('/api'+path,{headers:{'Content-Type':'application/json'},...opts,
    body: opts.body?JSON.stringify(opts.body):undefined});
  const data = await r.json().catch(()=>({}));
  if(r.status===401 && path!=='/me'){ showLogin(); throw new Error('sesión'); }
  if(!r.ok){ data._status=r.status; throw data; }
  return data;
}
function showLogin(){ $('#view').replaceChildren(); $('#l-pass').value=''; $('#login').classList.remove('hidden'); $('#layout').classList.add('hidden'); }
function showApp(){ $('#login').classList.add('hidden'); $('#layout').classList.remove('hidden'); route(); }
async function doLogin(){ try{ await api('/login',{method:'POST',body:{email:$('#l-email').value,password:$('#l-pass').value}}); showApp(); }catch(e){ $('#l-msg').textContent=e.detail||'Error'; } }
async function doRegister(){ try{ await api('/register',{method:'POST',body:{email:$('#l-email').value,password:$('#l-pass').value}}); showApp(); }catch(e){ $('#l-msg').textContent=e.detail||'Error'; } }
async function logout(){ await api('/logout',{method:'POST'}); showLogin(); }
window.addEventListener('hashchange', route);
async function route(){
  const [page, arg] = location.hash.replace('#','').split('/');
  document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active', a.hash==='#'+(page||'inicio')));
  const views = {inicio,cartera,asistente,analisis,comparador,simulador,oportunidades,alertas:alertasView,diario,historial,perfil,config};
  try{ await (views[page||'inicio']||inicio)(arg); }
  catch(e){ if(e.message!=='sesión') $('#view').innerHTML=`<div class="card">Error: ${esc(e.detail||e.message||JSON.stringify(e))}</div>`; }
}
const DISC = '<p class="disc">Herramienta de apoyo con datos aportados por el usuario y fuentes públicas citadas. No es asesoría financiera regulada, no garantiza rentabilidad y no ejecuta operaciones.</p>';

/* ---------- 1. Inicio (panel principal) ---------- */
async function inicio(){
  const d = await api('/dashboard');
  const t = d.portfolio.totals;
  const positions = d.portfolio.positions;
  const verified = positions.filter(p=>p.verified).length;
  const withPrice = positions.length-t.sin_precio_vigente.length;
  const pending = !positions.length || t.sin_precio_vigente.length || t.sin_costo.length || verified<positions.length || d.portfolio.cash_currency!=='USD';
  const deskTitle = !positions.length ? 'Empieza por registrar tu cartera' : t.sin_precio_vigente.length ? 'Faltan precios para decidir' : t.sin_costo.length ? 'Completa tus costos de compra' : verified<positions.length ? 'Confirma lo que aparece en tu cartera' : d.portfolio.cash_currency!=='USD' ? 'Revisa la moneda de tu efectivo' : 'Tus datos están listos para revisar';
  const deskCopy = !positions.length ? 'Sube una captura de Hapi o registra tus posiciones manualmente. Ninguna cifra de la foto se confirma sola.' : pending ? 'Antes de comparar alternativas, comprueba importes, fechas y fuentes. Lo pendiente no se presenta como certeza.' : 'Ya puedes estudiar cada posición con sus supuestos visibles. La decisión final siempre es tuya.';
  $('#view').innerHTML = `
  <h2>Resumen de inversión</h2><p class="sub">El estado de los datos va primero; las cifras vienen después.</p>
  <section class="desk ${pending?'needs-review':''}" aria-label="Estado de la cartera">
    <div><h3>${deskTitle}</h3><p>${deskCopy}</p>
      <div class="desk-counts"><span><strong>${withPrice}/${positions.length}</strong> con precio vigente</span>
        <span><strong>${verified}/${positions.length}</strong> confirmadas por ti</span></div></div>
    <a class="desk-action" href="${pending?'#cartera':'#analisis'}">${pending?'Revisar mi cartera':'Analizar un activo'}</a>
  </section>
  ${t.sin_precio_vigente.length?`<div class="alert riesgo_elevado">Total y riesgo no calculables: faltan valores vigentes en USD para ${esc(t.sin_precio_vigente.join(', '))}. Revisa precios y monedas en <a href="#cartera">Cartera</a>.</div>`:''}
  ${d.portfolio.cash_currency!=='USD'?'<div class="alert riesgo_elevado">El efectivo no está en USD; el riesgo no se puede calcular sin un tipo de cambio verificable.</div>':''}
  ${t.sin_costo.length?`<div class="alert">Resultado no calculable: falta el costo invertido de ${esc(t.sin_costo.join(', '))}.</div>`:''}
  <div class="stat-strip" aria-label="Resumen numérico">
    <div><div class="mut sm">Valor actual</div><div class="big">${t.valor_actual==null?'—':'$ '+fmt(t.valor_actual)}</div></div>
    <div><div class="mut sm">Capital invertido</div><div class="big">${t.invertido==null?'—':'$ '+fmt(t.invertido)}</div></div>
    <div><div class="mut sm">Resultado</div><div class="big ${cls(t.resultado)}">${t.resultado==null?'—':'$ '+fmt(t.resultado)}</div></div>
    <div><div class="mut sm">Rendimiento</div><div class="big ${cls(t.rendimiento_pct)}">${t.rendimiento_pct==null?'—':fmt(t.rendimiento_pct)+' %'}</div></div>
  </div>
  <div class="grid g2">
  <div class="card"><h3>Distribución y concentración</h3>
    ${Object.entries(t.pesos_pct||{}).map(([k,v])=>`<div class="row sm"><span style="width:60px"><b>${k}</b></span><span>${v} %</span></div>`).join('')||`<p class="mut sm">${t.sin_precio_vigente.length?'Pendiente de valores vigentes en USD':'Sin posiciones valoradas'}</p>`}
    ${d.risk.error?`<p class="sm mut">${esc(d.risk.error)}</p>`:`<p class="sm" style="margin-top:8px">Concentración: <span class="pill ${d.risk.nivel_concentracion==='alta'?'err':'ok'}">${esc(d.risk.nivel_concentracion||'—')}</span>
     · HHI ${d.risk.hhi||'—'} · diversificación efectiva ≈ ${d.risk.diversificacion_efectiva||'—'} posiciones</p>`}
    ${(d.risk.correlacion||[]).map(c=>`<div class="alert">${esc(c)}</div>`).join('')}
  </div>
  <div class="card"><h3>Alertas (${d.alerts.length})</h3>
    ${d.alerts.slice(0,6).map(a=>`<div class="alert ${a.level}"><span class="pill mut">${esc(a.level.replaceAll('_',' '))}</span> ${esc(a.text)}</div>`).join('')||'<p class="mut sm">Sin alertas</p>'}
  </div></div>
  <div class="grid g2">
  <div class="card"><h3>Calidad de los datos</h3>
    <table><tr><th>Ticker</th><th>Precio</th><th>Verificada</th></tr>
    ${d.calidad_datos.map(q=>`<tr><td>${q.ticker}</td><td><span class="pill ${q.estado_precio==='actual'?'ok':'warn'}">${esc(q.estado_precio.replaceAll('_',' '))}</span></td>
      <td>${q.verificada?'✅':'⏳ pendiente'}</td></tr>`).join('')}</table>
    <div class="row" style="margin-top:8px"><button class="mini" onclick="refreshPrices().then(inicio)">Actualizar precios</button></div></div>
  <div class="card"><h3>Tesis recientes (Diario)</h3>
    ${(d.tesis_recientes||[]).map(x=>`<div class="qbox"><b>${esc(x.ticker||'cartera')}</b> · ${esc(x.action||'')}
      ${x.done?'<span class="pill ok">evaluada</span>':(x.review_date?`<span class="pill warn">revisar ${esc(x.review_date)}</span>`:'')}
      <span class="mut sm">${(x.created_at||'').slice(0,10)}</span></div>`).join('')||'<p class="mut sm">Aún no registras tesis. Anota una en el Diario antes de operar.</p>'}
  </div></div>
  ${d.portfolio.positions.length?'':`<div class="card"><h3>Empezar</h3>
    <p class="sm">Carga la cartera que reportaste desde Hapi (NVDA + MSFT, quedará marcada «pendiente de verificación») o registra posiciones manualmente en Cartera.</p>
    <button onclick="api('/seed_hapi',{method:'POST'}).then(r=>{alert(r.detail);inicio()})">Cargar mi cartera de Hapi</button></div>`}
  ${DISC}`;
}
async function refreshPrices(){
  const r = await api('/prices/refresh',{method:'POST'});
  if(r.errors.length) alert('Algunos precios no se pudieron obtener:\n'+r.errors.map(e=>e.ticker+': '+e.error).join('\n')+'\nPuedes ingresarlos manualmente en Cartera.');
  return r;
}

/* ---------- Consulta de solo lectura a Luna ---------- */
async function asistente(){
  $('#view').innerHTML = `<div class="assistant-wrap">
    <h2>Consultar a Luna</h2>
    <p class="sub">Pregunta por tus posiciones, riesgos, tesis o conceptos de inversión. Luna no modifica la cartera ni ejecuta operaciones.</p>
    <div class="card assistant-form">
      <form onsubmit="assistantAsk(event)">
        <label for="ai-question">¿Qué quieres revisar?</label>
        <textarea id="ai-question" maxlength="600" required placeholder="Por ejemplo: ¿Qué datos me faltan para revisar mi concentración?"></textarea>
        <div class="row" style="margin-top:10px">
          <button id="ai-submit" type="submit" disabled>Preguntar a Luna</button>
          <span id="ai-status" class="sm mut" role="status"></span>
        </div>
      </form>
    </div>
    <div id="ai-result" class="card hidden" aria-live="polite">
      <h3>Respuesta</h3><div id="ai-answer" class="assistant-answer"></div>
      <p id="ai-asof" class="sm mut"></p>
    </div>
    <p class="sm mut">Se envían al proveedor de IA tu pregunta y un resumen de tu cartera, precios con fuente y fecha, riesgo, perfil resumido, fundamentales y hasta cinco tesis recientes. No se envían tu correo, contraseña ni la foto. La consulta no actualiza precios; verifica cualquier dato antes de decidir.</p>
    ${DISC}</div>`;
  try{
    const s = await api('/assistant/status');
    if(!$('#ai-status')) return;
    $('#ai-status').textContent = s.configured ? `Modelo: ${s.model}` : s.hint;
    $('#ai-submit').disabled = !s.configured;
  }catch(e){ if($('#ai-status')) $('#ai-status').textContent = e.detail||'No se pudo consultar el estado de Luna'; }
}
async function assistantAsk(event){
  event.preventDefault();
  const button = $('#ai-submit'), status = $('#ai-status');
  if(button.disabled) return;
  button.disabled = true;
  status.textContent = 'Consultando a Luna…';
  $('#ai-result').classList.add('hidden');
  try{
    const r = await api('/assistant/ask',{method:'POST',body:{question:$('#ai-question').value}});
    if(!$('#ai-result')) return;
    $('#ai-answer').textContent = r.answer;
    $('#ai-asof').textContent = `Consulta: ${r.asof} · Modelo: ${r.model}. Comprueba las fuentes y fechas citadas.`;
    $('#ai-result').classList.remove('hidden');
    status.textContent = 'Respuesta recibida';
  }catch(e){ if($('#ai-status')) status.textContent = e.detail||'No se pudo consultar a Luna. Inténtalo de nuevo.'; }
  finally{ if($('#ai-submit')) button.disabled = false; }
}

/* ---------- 2. Cartera ---------- */
async function cartera(){
  const [pf, val] = await Promise.all([api('/portfolio'), api('/validate')]);  $('#view').innerHTML = `
  <h2>Cartera</h2><p class="sub">Registro manual, importación desde tu reporte de Hapi y validación de datos (Módulos 1 y 2).</p>
  <div class="card"><div class="row">
    <button class="sec" onclick="api('/seed_hapi',{method:'POST'}).then(cartera)">Cargar cartera reportada de Hapi</button>
    <button class="sec" onclick="refreshPrices().then(cartera)">Actualizar precios (Yahoo Finance)</button>
    <span class="sm mut">Efectivo disponible (USD): $</span><input id="cash" style="width:110px" value="${pf.cash??''}">
    <button class="mini" onclick="if($('#cash').value===''){alert('Ingresa el efectivo en USD antes de guardarlo.');return}api('/cash',{method:'PUT',body:{amount:+$('#cash').value}}).then(cartera)">Guardar</button>
  </div></div>
  <div class="card"><h3>Sincronizar con Hapi — foto de tu cartera (IA)</h3>
    <p class="sm mut">Sube una captura de tus posiciones en la app de Hapi: el modelo de visión configurado
      extrae los datos, tú los revisas en una tabla editable y confirmas para sincronizar. Nada se guarda sin tu confirmación.</p>
    <div class="row">
      <input type="file" id="ph-file" accept="image/*" style="max-width:320px" onchange="photoPreviewName(this)">
      <button onclick="photoAnalyze()">Analizar captura</button>
      <span id="ph-status" class="sm mut"></span>
    </div>
    <div id="ph-map"></div>
  </div>
  <div class="card"><h3>Operaciones ejecutadas — revisar captura</h3>
    <p class="sm mut">Solo órdenes ejecutadas, no posiciones ni órdenes pendientes. El modelo puede omitir datos: contrasta cada fila con Hapi. Analizar la foto puede generar costo del proveedor de IA; importar no calcula ni aplica costos.</p>
    <div class="row"><input type="file" id="tr-file" accept="image/*" style="max-width:320px" onchange="tradePhotoChanged()">
      <button id="tr-analyze" type="button" onclick="tradePhotoAnalyze()">Analizar operaciones</button>
      <span id="tr-status" class="sm mut" role="status"></span></div>
    <div id="tr-review"></div>
  </div>
  <div class="card"><h3>Libro de operaciones y costo por ticker</h3>
    <p class="sm mut">Comprueba que el libro incluya todas las compras y ventas desde cero. Si hubo splits o transferencias, este libro no puede reflejarlos: no apliques el costo. Un historial parcial tampoco permite calcularlo. SQLite puede perder precisión al almacenar los importes.</p>
    <div class="row"><label for="tr-ticker" style="margin:0">Ticker</label>
      <input id="tr-ticker" style="width:135px" placeholder="p. ej. VOO" oninput="tradeLedgerChanged()">
      <button class="sec" type="button" onclick="loadTrades()">Ver operaciones guardadas</button></div>
    <div id="tr-ledger" class="sm mut" role="status">Elige un ticker para ver el libro.</div>
    <div class="review-step"><h4>Conciliar costo con la posición</h4>
      <p class="sm mut">Solo con historial completo, sin ajustes no modelados y una posición verificada en USD. La vista previa no modifica la posición.</p>
      <label for="tr-confirmed-qty">Acciones actuales comprobadas en Hapi (escríbelas, no se rellenan automáticamente)</label>
      <input id="tr-confirmed-qty" inputmode="decimal" style="max-width:210px" oninput="clearReconcile()" placeholder="Cantidad exacta">
      <label class="review-check"><input id="tr-complete" type="checkbox" onchange="clearReconcile()">Confirmo que revisé todas las compras y ventas desde el inicio y que el libro está completo.</label>
      <label class="review-check"><input id="tr-no-adjust" type="checkbox" onchange="clearReconcile()">Confirmo que no hubo splits, transferencias ni otros ajustes de acciones o costo no representados en el libro.</label>
      <button class="sec" type="button" onclick="previewReconcile()">Calcular vista previa</button>
      <div id="tr-reconcile" role="status"></div>
    </div>
  </div>
  <div class="card"><h3>Sincronizar con Hapi — importar archivo (CSV)</h3>
    <p class="sm mut">Exportá tus posiciones desde la app de Hapi y subí el archivo aquí. <b>No se piden tus credenciales</b> ni se conecta a tu cuenta: lees el archivo vos. Los datos entran marcados «pendiente de verificación».</p>
    <input type="file" id="csv-file" accept=".csv,.txt,text/csv" onchange="parseCsv(this)">
    <div id="csv-map"></div>
  </div>
  <div class="card"><h3>Posiciones</h3>
  ${pf.totals.sin_precio_vigente.length?`<div class="alert riesgo_elevado">El valor de algunas filas proviene de capturas, no está disponible o no está en USD. No hay un total actual fiable: ${esc(pf.totals.sin_precio_vigente.join(', '))}.</div>`:''}
  ${pf.cash_currency!=='USD'?`<div class="alert riesgo_elevado">Efectivo registrado en ${esc(pf.cash_currency)}: introduce el importe real en USD solo si lo verificaste; no se convierte automáticamente.</div>`:''}
  <table><tr><th>Ticker</th><th>Cantidad</th><th>Costo prom.</th><th>Invertido</th><th>Valor de referencia</th><th>P/L</th><th>Precio usado</th><th></th></tr>
  ${pf.positions.map(p=>`<tr>
    <td><b>${p.ticker}</b><br><span class="sm mut">${esc(p.name||'')}</span></td>
    <td>${p.qty}</td><td>$ ${fmt(p.avg_cost)}</td><td>$ ${fmt(p.invested)}</td>
    <td>${p.market_value==null?'—':`${esc(p.currency)} ${fmt(p.market_value)}`}</td><td class="${cls(p.unrealized_pl)}">${p.unrealized_pl==null?'—':`${esc(p.currency)} ${fmt(p.unrealized_pl)} (${fmt(p.return_pct)}%)`}</td>
    <td class="sm">${fmt(p.price_info.precio_usado)}<br><span class="mut">${esc(p.price_info.fuente||'')}</span><br>
      <span class="mut">${esc(p.price_info.asof||'fecha no registrada')}</span><br>
      <span class="pill ${p.price_status==='actual'?'ok':'warn'}">${esc(p.price_status.replaceAll('_',' '))}</span>
      ${p.verified?'<span class="pill ok">verificada</span>':`<button class="mini sec" onclick="api('/positions/${p.ticker}/verify',{method:'POST'}).then(cartera)">Confirmar datos</button>`}</td>
    <td><button class="mini danger" onclick="if(confirm('¿Eliminar ${p.ticker}?'))api('/positions/${p.ticker}',{method:'DELETE'}).then(cartera)">✕</button></td>
  </tr>`).join('')}</table>
  <p class="sm" style="margin-top:8px"><b>Totales:</b> invertido $ ${fmt(pf.totals.invertido)} · valor $ ${fmt(pf.totals.valor_actual)} ·
   resultado <span class="${cls(pf.totals.resultado)}">$ ${fmt(pf.totals.resultado)} (${fmt(pf.totals.rendimiento_pct)}%)</span></p></div>
  <div class="grid g2">
  <div class="card"><h3>Agregar / editar posición</h3>
    <div class="grid g2">
    <div><label>Ticker</label><input id="p-tk"></div><div><label>Nombre</label><input id="p-name"></div>
    <div><label>Cantidad</label><input id="p-qty" type="number" step="any"></div>
    <div><label>Costo promedio (USD)</label><input id="p-avg" type="number" step="any"></div>
    <div><label>Invertido total (USD, opcional)</label><input id="p-inv" type="number" step="any"></div>
    <div><label>Fuente del dato</label><input id="p-src" value="manual"></div></div>
    <button style="margin-top:10px" onclick="addPos()">Guardar posición</button></div>
  <div class="card"><h3>Precio manual (si la fuente falla)</h3>
    <div class="grid g2"><div><label>Ticker</label><input id="mp-tk"></div>
    <div><label>Precio USD</label><input id="mp-p" type="number" step="any"></div>
    <div><label>Fecha/hora (ISO)</label><input id="mp-asof" value="${new Date().toISOString().slice(0,16)}"></div>
    <div><label>Fuente</label><input id="mp-src" placeholder="p. ej. app de Hapi, 19/07 10:30"></div></div>
    <button class="sec" style="margin-top:10px" onclick="manualPrice()">Registrar precio</button></div>
  </div>
  <div class="card"><h3>Validación de datos (Módulo 2)</h3>
  ${val.report.map(r=>`<details><summary>${r.ticker} ${r.inconsistencias.length?`<span class="pill err">${r.inconsistencias.length} inconsistencia(s)</span>`:'<span class="pill ok">coherente</span>'}</summary>
    ${r.inconsistencias.map(x=>`<div class="alert riesgo_elevado">⚠️ ${esc(x)}</div>`).join('')}
    <p class="sm"><b>Confirmados:</b></p><ul class="sm">${r.confirmados.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
    <p class="sm"><b>Calculados:</b></p><ul class="sm">${r.calculados.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
    <p class="sm"><b>Pendientes de verificación:</b></p><ul class="sm">${r.pendientes.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
  </details>`).join('')||'<p class="mut sm">Sin posiciones que validar.</p>'}</div>${DISC}`;
  photoStatus();
}
async function addPos(){
  await api('/positions',{method:'POST',body:{ticker:$('#p-tk').value,name:$('#p-name').value,
    qty:+$('#p-qty').value, avg_cost:$('#p-avg').value?+$('#p-avg').value:null,
    invested:$('#p-inv').value?+$('#p-inv').value:null, source:$('#p-src').value||'manual'}});
  cartera();
}
async function manualPrice(){
  await api('/prices/manual',{method:'POST',body:{ticker:$('#mp-tk').value,price:+$('#mp-p').value,
    asof:$('#mp-asof').value,source:$('#mp-src').value||'ingreso manual'}});
  alert('Precio registrado con su fuente y fecha'); cartera();
}

/* ---------- Importador de CSV de Hapi (sin credenciales, se lee en el navegador) ---------- */
let _csv=null;
function csvSplit(line, delim){
  const out=[]; let cur='', q=false;
  for(let i=0;i<line.length;i++){ const c=line[i];
    if(q){ if(c==='"'){ if(line[i+1]==='"'){cur+='"';i++;} else q=false; } else cur+=c; }
    else { if(c==='"') q=true; else if(c===delim){ out.push(cur); cur=''; } else cur+=c; } }
  out.push(cur); return out.map(s=>s.trim());
}
function csvNum(s){ if(s==null) return null; const c=String(s).replace(/[^0-9.\-]/g,''); const n=parseFloat(c); return isNaN(n)?null:n; }
function csvGuess(headers, kws){ for(let i=0;i<headers.length;i++){ const h=headers[i].toLowerCase(); if(kws.some(k=>h.includes(k))) return i; } return -1; }
function parseCsv(input){
  const f=input.files[0]; if(!f) return;
  const rd=new FileReader();
  rd.onload=()=>{
    const text=String(rd.result).replace(/\r/g,'');
    const lines=text.split('\n').filter(l=>l.trim()!=='');
    if(lines.length<2){ $('#csv-map').innerHTML='<p class="sm warn">El archivo no tiene filas de datos.</p>'; return; }
    const delim = lines[0].split(';').length > lines[0].split(',').length ? ';' : ',';
    _csv = {headers: csvSplit(lines[0], delim), rows: lines.slice(1).map(l=>csvSplit(l, delim))};
    renderCsvMap();
  };
  rd.readAsText(f);
}
function renderCsvMap(){
  const h=_csv.headers;
  const opt=(sel)=>h.map((x,i)=>`<option value="${i}" ${i===sel?'selected':''}>${esc(x||('columna '+(i+1)))}</option>`).join('');
  const none='<option value="-1">— ninguna —</option>';
  $('#csv-map').innerHTML=`
   <p class="sm" style="margin-top:10px">Confirmá qué columna es cada dato (se detectaron automáticamente):</p>
   <div class="grid g4">
    <div><label>Ticker *</label><select id="m-tk">${opt(csvGuess(h,['ticker','symbol','simbolo','activo','instrument']))}</select></div>
    <div><label>Cantidad *</label><select id="m-qty">${opt(csvGuess(h,['cantidad','qty','shares','acciones','units','particip','quantity']))}</select></div>
    <div><label>Costo prom. (opcional)</label><select id="m-avg">${none}${opt(csvGuess(h,['costo','avg','promedio','average','precio prom','cost per']))}</select></div>
    <div><label>Invertido (opcional)</label><select id="m-inv">${none}${opt(csvGuess(h,['invertido','invested','basis','aporte']))}</select></div>
   </div>
   <div class="row" style="margin-top:8px"><button onclick="previewCsv()">Previsualizar</button>
     <span class="sm mut">${_csv.rows.length} fila(s) en el archivo</span></div>
   <div id="csv-prev"></div>`;
}
function previewCsv(){
  const iT=+$('#m-tk').value, iQ=+$('#m-qty').value, iA=+$('#m-avg').value, iI=+$('#m-inv').value;
  const rows=_csv.rows.map(r=>({ ticker:String(r[iT]||'').toUpperCase().trim(), qty:csvNum(r[iQ]),
    avg_cost: iA>=0?csvNum(r[iA]):null, invested: iI>=0?csvNum(r[iI]):null }))
    .filter(x=>x.ticker && x.qty>0);
  if(!rows.length){ $('#csv-prev').innerHTML='<p class="sm warn" style="margin-top:8px">Con ese mapeo no hay filas válidas (ticker + cantidad > 0). Revisá las columnas.</p>'; return; }
  window._csvRows=rows;
  $('#csv-prev').innerHTML=`<table style="margin-top:10px"><tr><th>Ticker</th><th>Cantidad</th><th>Costo prom.</th><th>Invertido</th></tr>
    ${rows.map(x=>`<tr><td><b>${esc(x.ticker)}</b></td><td>${x.qty}</td><td>${x.avg_cost??'—'}</td><td>${x.invested??'—'}</td></tr>`).join('')}</table>
    <div class="row" style="margin-top:8px"><button onclick="doImportCsv()">Importar ${rows.length} posición(es)</button>
      <span class="sm mut">Entrarán marcadas «pendiente de verificación».</span></div>`;
}
async function doImportCsv(){
  try{
    const r=await api('/positions/import',{method:'POST',body:{rows:window._csvRows}});
    alert(r.detail + (r.omitidas.length?`\n\nOmitidas ${r.omitidas.length} fila(s) por ticker o cantidad inválidos.`:''));
    cartera();
  }catch(e){ alert(e.detail||'Error al importar'); }
}

/* ---------- Sincronizar con Hapi por foto (IA de visión) ---------- */
async function photoStatus(){
  try{
    const s = await api('/hapi/photo/status');
    $('#ph-status').innerHTML = s.configured
      ? `<span class="pill ok">IA lista</span> <span class="sm mut">${esc(s.model)}</span>`
      : `<span class="pill warn">IA no configurada</span> <span class="sm mut">${esc(s.hint)}</span>`;
    return s.configured;
  }catch(e){ return false; }
}
function photoPreviewName(input){
  $('#ph-status').textContent = input.files[0] ? `Listo para analizar: ${input.files[0].name}` : '';
}
function photoShrink(file){
  return new Promise((res, rej)=>{
    const img = new Image(), fr = new FileReader();
    fr.onload = ()=>{ img.onload = ()=>{
      const mx = 1600, s = Math.min(1, mx/Math.max(img.width, img.height));
      const cv = document.createElement('canvas');
      cv.width = Math.round(img.width*s); cv.height = Math.round(img.height*s);
      cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height);
      res(cv.toDataURL('image/jpeg', 0.85));
    }; img.onerror = ()=>rej('imagen ilegible'); img.src = fr.result; };
    fr.onerror = ()=>rej('no se pudo leer el archivo');
    fr.readAsDataURL(file);
  });
}
async function photoAnalyze(){
  const f = $('#ph-file').files[0];
  if(!f){ alert('Primero elige una captura de tu cartera en Hapi.'); return; }
  $('#ph-map').innerHTML = '<p class="mut">Analizando la captura con el modelo de visión…</p>';
  let b64;
  try{ b64 = await photoShrink(f); }
  catch(e){ $('#ph-map').innerHTML = `<p class="sm" style="color:var(--err)">${esc(String(e))}</p>`; return; }
  let r;
  try{ r = await api('/hapi/photo/analyze',{method:'POST',body:{image_b64:b64,mime:'image/jpeg'}}); }
  catch(e){ $('#ph-map').innerHTML = `<div class="alert riesgo_elevado">${esc(e.detail||'Error al analizar')}</div>`; return; }
  if(!r.rows.length){
    $('#ph-map').innerHTML = '<div class="alert">La IA no detectó posiciones en la captura. ' +
      (r.omitted.length? esc(JSON.stringify(r.omitted)) : 'Usa una captura de la pantalla de Portafolio/Posiciones, completa y legible.') + '</div>';
    return;
  }
  const num=(k,v)=>`<input id="ph-${k}" type="number" step="any" value="${v??''}">`;
  $('#ph-map').innerHTML = `
   <p class="sm" style="margin-top:10px">Detectado con <b>${esc(r.model)}</b>. Revisa cada dato contra tu app de Hapi y corrige lo que haga falta
     (los campos vacíos son datos que la IA no vio; no se inventan):</p>
   <table><tr><th>Ticker</th><th>Cantidad</th><th>Costo prom.</th><th>Invertido</th><th>Valor</th><th>P/L</th><th>P/L %</th></tr>
   ${r.rows.map((x,i)=>`<tr><td><b>${esc(x.ticker)}</b><br><span class="sm mut">${esc(x.name||'')}</span></td>
     <td>${num(i+'-qty',x.qty)}</td><td>${num(i+'-avg',x.avg_cost)}</td><td>${num(i+'-inv',x.invested)}</td>
     <td>${num(i+'-val',x.hapi_value)}</td><td>${num(i+'-pl',x.hapi_pl)}</td><td>${num(i+'-plp',x.hapi_return_pct)}</td></tr>`).join('')}
   </table>
   ${r.omitted.length?`<p class="sm mut">${r.omitted.length} fila(s) descartada(s) por datos incompletos: ${esc(JSON.stringify(r.omitted))}</p>`:''}
   <div class="row" style="margin-top:8px">
     <label style="margin:0">Efectivo / poder de compra (USD)</label>
     <input id="ph-cash" type="number" step="any" style="width:120px" value="${r.cash??''}">
     <button onclick="photoSave(${r.rows.length})">Sincronizar ${r.rows.length} posición(es)</button>
     <span class="sm mut">Entrarán marcadas «pendiente de verificación» con la captura como fuente.</span>
   </div>`;
  window._photoRows = r.rows;
}
async function photoSave(n){
  const rows = [];
  window._photoRows.forEach((x,i)=>{
    const g=k=>{ const v=$('#ph-'+i+'-'+k).value; return v===''?null:+v; };
    rows.push({ticker:x.ticker, name:x.name, qty:g('qty'), avg_cost:g('avg'),
      invested:g('inv'), hapi_value:g('val'), hapi_pl:g('pl'), hapi_return_pct:g('plp')});
  });
  const cashEl = $('#ph-cash');
  const body = {rows};
  if(cashEl && cashEl.value!=='') body.cash = +cashEl.value;
  try{
    const r = await api('/hapi/photo/save',{method:'POST',body});
    alert(r.detail + (r.omitidas.length?`\n\nOmitidas ${r.omitidas.length} fila(s).`:''));
    cartera();
  }catch(e){ alert(e.detail||'Error al sincronizar'); }
}

/* ---------- Órdenes ejecutadas: foto, libro y conciliación explícita ---------- */
let _tradeRows = null, _tradeModel = null, _reconcilePreview = null, _tradeVersion = 0;
const reviewError = (e, fallback) => typeof e?.detail === 'string' ? e.detail : (e?.detail ? JSON.stringify(e.detail) : fallback);
function imagePayload(dataUrl){
  const b64 = dataUrl.split(',')[1];
  if(!b64 || b64.length > 6*1024*1024) throw new Error('La imagen comprimida supera 6 MB en base64. Recorta la captura y vuelve a intentarlo.');
  return b64;
}
function tradePhotoChanged(){
  _tradeVersion++; _tradeRows = null; _tradeModel = null;
  $('#tr-review').replaceChildren();
  $('#tr-status').textContent = $('#tr-file').files[0] ? `Listo para analizar: ${$('#tr-file').files[0].name}` : '';
}
async function tradePhotoAnalyze(){
  const file = $('#tr-file').files[0], button = $('#tr-analyze');
  if(!file || !file.type.startsWith('image/')){ $('#tr-status').textContent='Selecciona una imagen de órdenes ejecutadas.'; return; }
  const version=++_tradeVersion;
  _tradeRows = null; _tradeModel = null; $('#tr-review').replaceChildren();
  button.disabled = true; $('#tr-status').textContent='Analizando con el proveedor de IA…';
  try{
    const image_b64 = imagePayload(await photoShrink(file));
    const r = await api('/trades/photo/analyze',{method:'POST',body:{image_b64,mime:'image/jpeg'}});
    if(!$('#tr-review') || version!==_tradeVersion || $('#tr-file').files[0]!==file) return;
    _tradeRows = r.rows; _tradeModel = r.model;
    $('#tr-status').textContent = `${r.rows.length} orden(es) para revisar · modelo: ${r.model}`;
    $('#tr-review').innerHTML = `
      <div class="review-step"><h4>Revisa cada orden contra Hapi</h4>
        <p class="sm mut">Vacío significa no visible, no cero. Cantidad, precio y comisión se escriben como decimales sin separadores; cero en comisión solo si está comprobado. Fecha ISO y USD deben constar en la orden o en tu fuente verificable.</p>
        ${r.rows.length?`<table class="review-table"><tr><th>Revisé</th><th>Ticker</th><th>Compra/venta</th><th>Acciones</th><th>USD/acción</th><th>Comisión USD</th><th>Fecha/hora ISO</th><th>Moneda</th><th>ID orden</th></tr>
          ${r.rows.map((x,i)=>`<tr>
            <td><input id="tr-${i}-review" type="checkbox" aria-label="Revisé orden ${i+1}"></td>
            <td><input id="tr-${i}-ticker" class="narrow-field" aria-label="Ticker orden ${i+1}" value="${esc(x.ticker??'')}"></td>
            <td><select id="tr-${i}-side" aria-label="Lado orden ${i+1}"><option value="">Sin identificar</option><option value="comprar" ${x.side==='comprar'?'selected':''}>Compra</option><option value="vender" ${x.side==='vender'?'selected':''}>Venta</option></select></td>
            <td><input id="tr-${i}-qty" class="narrow-field" inputmode="decimal" aria-label="Acciones orden ${i+1}" value="${esc(x.qty??'')}"></td>
            <td><input id="tr-${i}-price" class="narrow-field" inputmode="decimal" aria-label="Precio orden ${i+1}" value="${esc(x.price??'')}"></td>
            <td><input id="tr-${i}-fees" class="narrow-field" inputmode="decimal" aria-label="Comisión orden ${i+1}" value="${esc(x.fees??'')}"></td>
            <td><input id="tr-${i}-at" class="wide-field" aria-label="Fecha ISO orden ${i+1}" placeholder="YYYY-MM-DD o fecha y hora" value="${esc(x.at??'')}"></td>
            <td><select id="tr-${i}-currency" aria-label="Moneda orden ${i+1}"><option value="">No confirmada</option><option value="USD" ${x.currency==='USD'?'selected':''}>USD</option></select></td>
            <td><input id="tr-${i}-order_id" class="wide-field" aria-label="ID orden ${i+1}" value="${esc(x.order_id??'')}"></td></tr>`).join('')}</table>`:'<p class="alert">No se detectaron órdenes ejecutadas. Revisa las omisiones y usa una captura legible.</p>'}
        ${r.omitted.length?`<div class="alert"><b>Operaciones omitidas (${r.omitted.length}):</b><ul>${r.omitted.map(x=>`<li class="review-output">${esc(typeof x==='string'?x:JSON.stringify(x))}</li>`).join('')}</ul>Comprueba estas operaciones antes de considerar completo el libro.</div>`:''}
        ${r.rows.length?`<label for="tr-source">Fuente de estas órdenes (obligatoria)</label>
          <input id="tr-source" placeholder="p. ej. Historial de órdenes Hapi (indica la fecha de la captura)">
          <p class="sm mut">Al importar solo se registran estas órdenes. Duplicados requieren una segunda confirmación; no se marca el libro como completo ni se cambia el costo de la posición.</p>
          <button id="tr-import" type="button" onclick="tradeImport()">Importar órdenes revisadas</button>
          <p id="tr-import-status" class="sm" role="status"></p>`:''}
      </div>`;
  }catch(e){ if($('#tr-status') && version===_tradeVersion) $('#tr-status').textContent=reviewError(e,e.message||'No se pudo analizar la imagen.'); }
  finally{ if($('#tr-analyze')) button.disabled=false; }
}
function reviewedTradeRows(){
  if(!_tradeRows?.length) throw new Error('Analiza una captura con operaciones antes de importar.');
  const decimal = /^(?:0|[1-9]\d*)(?:\.\d+)?$/;
  return _tradeRows.map((_,i)=>{
    const g=k=>$('#tr-'+i+'-'+k).value.trim();
    if(!$('#tr-'+i+'-review').checked) throw new Error(`Revisa y marca la orden ${i+1} antes de importar todas las filas.`);
    const row={ticker:g('ticker').toUpperCase(),side:g('side'),qty:g('qty'),price:g('price'),
      fees:g('fees'),at:g('at'),currency:g('currency'),order_id:g('order_id')||null};
    if(!/^[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,5})?$/.test(row.ticker) || !row.side ||
       !decimal.test(row.qty) || row.qty==='0' || !decimal.test(row.price) || row.price==='0' ||
       !decimal.test(row.fees) || !row.at || row.currency!=='USD')
      throw new Error(`Orden ${i+1}: confirma ticker, compra/venta, cantidad y precio positivos, comisión visible (0 solo si consta), fecha ISO y moneda USD.`);
    return row;
  });
}
async function tradeImport(){
  const button=$('#tr-import'), status=$('#tr-import-status');
  let rows, source;
  try{ rows=reviewedTradeRows(); source=$('#tr-source').value.trim(); if(!source) throw new Error('Indica la fuente verificable de las órdenes.'); }
  catch(e){ status.textContent=e.message; return; }
  button.disabled=true; status.textContent='Importando órdenes revisadas…';
  const body={rows,source,model:_tradeModel,reviewed:true,allow_duplicates:false};
  try{
    let result;
    try{ result=await api('/trades/import',{method:'POST',body}); }
    catch(e){
      const detail=reviewError(e,'Error al importar órdenes.');
      if(!(e._status===409 || /duplicad/i.test(detail))) throw e;
      status.textContent=detail;
      if(!confirm(`${detail}\n\n¿Confirmas importar estas mismas órdenes aunque puedan estar duplicadas? Comprueba los ID y las fechas en Hapi.`)) return;
      result=await api('/trades/import',{method:'POST',body:{...body,allow_duplicates:true}});
    }
    if(!$('#tr-import-status')) return;
    status.textContent=result.detail||'Órdenes guardadas con su fuente. El costo de la posición no cambió.';
    _tradeRows=null; button.disabled=true;
    const tickers=[...new Set(rows.map(x=>x.ticker))];
    $('#tr-ticker').value=tickers[0];
    clearReconcile();
    await loadTrades();
    if(tickers.length>1) status.textContent+=` Otros tickers importados: ${tickers.slice(1).join(', ')}. Consúltalos por separado.`;
  }catch(e){ if($('#tr-import-status')) status.textContent=reviewError(e,'No se pudieron importar las órdenes.'); }
  finally{ if($('#tr-import') && _tradeRows) button.disabled=false; }
}
function tradeLedgerChanged(){ clearReconcile(); $('#tr-ledger').textContent='Pulsa «Ver operaciones guardadas» para este ticker.'; }
async function loadTrades(){
  const ticker=$('#tr-ticker').value.trim().toUpperCase(), output=$('#tr-ledger');
  clearReconcile();
  if(!/^[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,5})?$/.test(ticker)){ output.textContent='Indica un ticker válido.'; return; }
  output.textContent='Consultando libro…';
  try{
    const r=await api('/trades?ticker='+encodeURIComponent(ticker));
    if($('#tr-ticker')?.value.trim().toUpperCase()!==ticker) return;
    output.innerHTML=r.trades.length?`<p><b>${esc(ticker)}</b>: ${r.trades.length} operación(es) guardada(s). Verifica que no falten compras, ventas, splits ni transferencias.</p>
      <table class="review-table"><tr><th>Fecha</th><th>Lado</th><th>Acciones</th><th>USD/acción</th><th>Comisión</th><th>Moneda</th><th>ID orden</th><th>Fuente</th></tr>
      ${r.trades.map(x=>`<tr><td>${esc(x.at)}</td><td>${esc(x.side)}</td><td>${esc(x.qty)}</td><td>${esc(x.price)}</td><td>${esc(x.fees)}</td><td>${esc(x.currency)}</td><td>${esc(x.order_id)}</td><td>${esc(x.source)}</td></tr>`).join('')}</table>`:
      '<p class="alert">No hay órdenes guardadas para este ticker. No concilies sin un historial completo.</p>';
  }catch(e){ if($('#tr-ledger')) output.textContent=reviewError(e,'No se pudo cargar el libro.'); }
}
function clearReconcile(){ _reconcilePreview=null; if($('#tr-reconcile')) $('#tr-reconcile').replaceChildren(); }
function canonicalQty(value){
  const s=String(value??'').trim();
  if(!/^\d+(?:\.\d+)?$/.test(s)) return null;
  const [whole, frac='']=s.split('.');
  return (whole.replace(/^0+(?=\d)/,'')||'0')+(frac.replace(/0+$/,'')?'.'+frac.replace(/0+$/,''):'');
}
async function previewReconcile(){
  clearReconcile();
  const output=$('#tr-reconcile'), ticker=$('#tr-ticker').value.trim().toUpperCase(), qty=$('#tr-confirmed-qty').value.trim();
  if(!/^[A-Z][A-Z0-9]{0,9}(?:[.-][A-Z0-9]{1,5})?$/.test(ticker) ||
     !$('#tr-complete').checked || !$('#tr-no-adjust').checked || !canonicalQty(qty) || canonicalQty(qty)==='0'){
    output.textContent='Indica ticker y cantidad comprobada; confirma historial completo y ausencia de ajustes no modelados.'; return;
  }
  output.textContent='Calculando vista previa; la posición no se modifica…';
  try{
    const r=await api('/trades/'+encodeURIComponent(ticker)+'/reconcile',{
      method:'POST',body:{complete_history:true,apply:false,confirmed_qty:qty}});
    if(!$('#tr-reconcile') || $('#tr-ticker').value.trim().toUpperCase()!==ticker ||
       $('#tr-confirmed-qty').value.trim()!==qty || !$('#tr-complete').checked || !$('#tr-no-adjust').checked) return;
    const matches=r.reconciled===true && !!r.preview_token;
    _reconcilePreview=matches?{ticker,qty,token:r.preview_token}:null;
    output.innerHTML=`<div class="review-step"><h4>Vista previa, sin aplicar</h4>
      <p class="sm review-output">Libro: <b>${esc(r.qty)} acciones</b> · Posición registrada: <b>${esc(r.position_qty)} acciones</b> · Comprobadas en Hapi: <b>${esc(qty)} acciones</b>.</p>
      <p class="sm review-output">Invertido calculado: USD ${esc(r.invested)} · Costo promedio: USD ${esc(r.avg_cost)} por acción.</p>
      <p class="alert">${esc(r.warning)}</p>
      ${matches?`<p class="pill ok">El servidor concilió las cantidades (tolerancia de 0,00001 acción)</p>
        <label class="review-check"><input id="tr-apply-check" type="checkbox">He comparado el costo previo con la vista previa y autorizo actualizar solo el costo de ${esc(ticker)}.</label>
        <button type="button" onclick="applyReconcile()">Confirmar y aplicar costo</button>`:
        '<div class="alert riesgo_elevado">Las cantidades no coinciden exactamente o falta la posición. No se puede aplicar. Revisa el libro, los splits y las transferencias.</div>'}</div>`;
  }catch(e){ if($('#tr-reconcile')) output.textContent=reviewError(e,'No se pudo calcular la vista previa.'); }
}
async function applyReconcile(){
  const preview=_reconcilePreview, output=$('#tr-reconcile');
  if(!preview || !$('#tr-apply-check')?.checked || !$('#tr-complete').checked ||
     $('#tr-ticker').value.trim().toUpperCase()!==preview.ticker || !$('#tr-no-adjust').checked ||
     $('#tr-confirmed-qty').value.trim()!==preview.qty){ output.textContent='Repite la vista previa y confirma la conciliación antes de aplicar.'; return; }
  if(!confirm(`¿Aplicar el costo calculado a ${preview.ticker}? Confirma que el libro está completo y las cantidades coinciden con Hapi.`)) return;
  _reconcilePreview=null;
  output.textContent='Aplicando costo confirmado…';
  try{
    const r=await api('/trades/'+encodeURIComponent(preview.ticker)+'/reconcile',{
      method:'POST',body:{complete_history:true,no_unmodeled_adjustments:true,apply:true,
        confirmed_qty:preview.qty,preview_token:preview.token}});
    if($('#tr-reconcile')) output.textContent='Costo aplicado. La posición quedó pendiente de verificación otra vez. Revísala en Cartera; SQLite almacena números flotantes.';
  }catch(e){ if($('#tr-reconcile')) output.textContent=reviewError(e,'No se pudo aplicar el costo.'); }
}

/* ---------- 3. Análisis y decisión (detalle del activo) ---------- */
async function analisis(arg){
  const pf = await api('/portfolio');
  const tickers = pf.positions.map(p=>p.ticker);
  const tk = (arg||tickers[0]||'').toUpperCase();
  $('#view').innerHTML = `
  <h2>Análisis y decisión</h2>
  <p class="sub">Responde: qué ocurre, si la valoración es razonable, qué riesgos hay y qué alternativa conviene — con argumentos y supuestos visibles.</p>
  <div class="card"><div class="row">
    <select id="an-tk" style="width:140px">${tickers.map(t=>`<option ${t===tk?'selected':''}>${t}</option>`).join('')}</select>
    <button onclick="runAnalysis()">Analizar</button>
    <button class="sec" onclick="fundForm($('#an-tk').value)">Fundamentales…</button>
    <span class="sm mut">Supuestos DCF:</span>
    <label class="sm" style="margin:0">crec. 1-5a %</label><input id="as-g" style="width:70px" value="15">
    <label class="sm" style="margin:0">descuento %</label><input id="as-r" style="width:70px" value="10">
    <label class="sm" style="margin:0">terminal %</label><input id="as-t" style="width:70px" value="2.5">
  </div></div>
  <div id="an-out">${tk?'<p class="mut">Pulsa Analizar.</p>':'<p class="mut">Registra posiciones primero.</p>'}</div>${DISC}`;
  if(arg) runAnalysis();
}
async function runAnalysis(){
  const tk = $('#an-tk').value;
  $('#an-out').innerHTML = '<p class="mut">Analizando (obteniendo histórico de la fuente)…</p>';
  let r;
  try{
    r = await api('/analysis/'+tk,{method:'POST',body:{assumptions:{
      growth_1_5_pct:+$('#as-g').value, discount_rate_pct:+$('#as-r').value, terminal_growth_pct:+$('#as-t').value}}});
  }catch(e){
    if($('#an-out')) $('#an-out').innerHTML = `<div class="alert riesgo_elevado">${esc(e.detail||'No se pudo generar el análisis. Revisa los precios en Cartera.')}</div>`;
    return;
  }
  const d = r.decision, sc = r.valoracion.escenarios, tec = r.situacion_tecnica||{};
  const scoreRow = Object.entries(r.analisis_fundamental.scores||{}).map(([k,v])=>
    `<tr><td>${k.replaceAll('_',' ')}</td><td>${v.score==null?'<span class="pill warn">falta dato</span>':`<b>${v.score}</b>/10`}</td><td class="sm mut">${esc(v.reason)}</td></tr>`).join('');
  $('#an-out').innerHTML = `
  <div class="card"><h3>${r.ticker} — ${esc(r.empresa)} <span class="sm mut">(${r.fecha_hora.replace('T',' ')})</span></h3>
    <div class="row sm">
      <span>Precio: <b>$ ${fmt(r.precio_actual.valor)}</b> <span class="pill ${r.precio_actual.estado==='actual'?'ok':'warn'}">${esc(r.precio_actual.estado)}</span>
      <span class="mut">${esc(r.precio_actual.fuente||'')} ${esc(r.precio_actual.asof||'')}</span></span>
      <span>· Cantidad ${r.cantidad} · Valor $ ${fmt(r.valor_total)} · Costo prom. $ ${fmt(r.costo_promedio)}
      · Resultado <span class="${cls(r.resultado)}">$ ${fmt(r.resultado)}</span> · Peso ${fmt(r.peso_en_cartera_pct,1)} %</span>
    </div></div>
  <div class="card" style="border-left:5px solid var(--acc)">
    <h3>Decisión propuesta: <span class="pill">${esc(d.decision_propuesta.replaceAll('_',' '))}</span>
     <span class="pill ${d.nivel_confianza==='baja'?'warn':'ok'}">confianza ${d.nivel_confianza}</span></h3>
    <p class="sm"><b>Pregunta obligatoria:</b> ${esc(d.pregunta_obligatoria)}</p>
    <ul class="sm">${d.argumentos.map(a=>`<li>${esc(a)}</li>`).join('')}</ul>
    <div class="row">
      ${['comprar','agregar_gradualmente','mantener','reducir','vender','esperar'].map(a=>
        `<button class="mini sec" onclick="recordDecision(${r.decision_id},'${a}')">Registrar: ${a.replaceAll('_',' ')}</button>`).join('')}
    </div>
    <p class="sm mut" style="margin-top:6px">${esc(d.nota)} Próxima revisión: ${esc(r.proxima_revision)}.</p>
    <button class="mini sec" type="button" onclick="explainDecision(${r.decision_id})">Explicar esta propuesta con Luna</button>
    <p class="sm mut">Luna pone en palabras la propuesta ya guardada; no produce otra recomendación. La consulta al proveedor de IA puede generar costo.</p>
    <div id="explain-${r.decision_id}" class="assistant-answer sm" role="status"></div></div>
  ${d.checklist_promediar?`<div class="card"><h3>Checklist antes de promediar a la baja</h3>
    ${d.checklist_promediar.map(c=>`<div class="qbox"><b>${esc(c.pregunta)}</b><br>${esc(c.respuesta)}</div>`).join('')}</div>`:''}
  <div class="grid g2">
  <div class="card"><h3>Alternativas comparadas</h3>
    ${Object.entries(d.alternativas).filter(([k,v])=>v.a_favor.length||v.en_contra.length||v.condiciones.length).map(([k,v])=>`
      <details><summary>${k.replaceAll('_',' ')}</summary>
      ${v.a_favor.map(x=>`<div class="sm">✅ ${esc(x)}</div>`).join('')}
      ${v.en_contra.map(x=>`<div class="sm">❌ ${esc(x)}</div>`).join('')}
      ${v.condiciones.map(x=>`<div class="sm">📌 ${esc(x)}</div>`).join('')}</details>`).join('')}</div>
  <div class="card"><h3>Valoración por escenarios (DCF)</h3>
    ${r.valoracion.calculable? `<table><tr><th>Escenario</th><th>Valor/acción</th><th>Margen seg.</th></tr>
      ${Object.entries(sc).map(([k,v])=>`<tr><td>${k}</td><td>$ ${fmt(v.valor_estimado_por_accion)}</td>
        <td class="${cls(v.margen_de_seguridad_pct)}">${fmt(v.margen_de_seguridad_pct,1)} %</td></tr>`).join('')}</table>
      <details><summary class="sm">Supuestos del escenario base (modificables arriba)</summary>
      <pre>${esc(JSON.stringify(sc.base.supuestos,null,1))}</pre></details>`
     :`<p class="sm warn">No calculable: ${r.valoracion.faltantes.map(esc).join('; ')}.</p>`}
    <p class="sm mut">${esc(r.valoracion.nota)}</p>
    <h3>Múltiplos</h3>
    ${Object.keys(r.multiplos.multiples).length?`<table>${Object.entries(r.multiplos.multiples).map(([k,v])=>`<tr><td>${k}</td><td><b>${v}</b></td></tr>`).join('')}</table>`:''}
    ${r.multiplos.missing.length?`<p class="sm mut">Faltan: ${r.multiplos.missing.map(esc).join('; ')}</p>`:''}
  </div></div>
  <div class="grid g2">
  <div class="card"><h3>Análisis fundamental</h3><table>${scoreRow}</table>
    <p class="sm mut">${esc(r.analisis_fundamental.nota||'')}</p>
    <p class="sm">Fuente de fundamentales: ${esc(r.calidad_de_datos.fundamentales_fuente||'no registrados')} ${r.calidad_de_datos.fundamentales_asof?`(${esc(r.calidad_de_datos.fundamentales_asof)})`:''}</p></div>
  <div class="card"><h3>Situación técnica (complementaria)</h3>
    ${tec.error?`<p class="sm warn">${esc(tec.error)}</p>`:`
    <table>
      <tr><td>Tendencia</td><td><b>${esc(tec.tendencia||'—')}</b></td></tr>
      <tr><td>SMA50 / SMA200</td><td>${fmt(tec.sma50)} / ${fmt(tec.sma200)}</td></tr>
      <tr><td>RSI(14)</td><td>${tec.rsi14??'—'}</td></tr>
      <tr><td>Distancia al máx. del periodo</td><td>${fmt(tec.distancia_a_maximo_pct,1)} %</td></tr>
      <tr><td>Volatilidad anualizada</td><td>${fmt(tec.volatilidad_anualizada_pct,1)} %</td></tr>
      <tr><td>Caída máx. del periodo</td><td>${fmt(tec.caida_maxima_periodo_pct,1)} %</td></tr>
      <tr><td>Soporte / resistencia aprox.</td><td>${fmt(tec.soporte_aproximado)} / ${fmt(tec.resistencia_aproximada)}</td></tr>
    </table><p class="sm mut">${esc(tec.nota||'')} Fuente: ${esc(tec.fuente||'')}</p>`}</div>
  </div>`;
}
async function recordDecision(id,choice){
  const ok = confirm(`Vas a registrar tu decisión: «${choice.replaceAll('_',' ')}».\nRecuerda: la ejecución la haces tú en Hapi; esta app nunca opera por ti. ¿Confirmas el registro?`);
  if(!ok) return;
  const r = await api(`/decisions/${id}/record`,{method:'POST',body:{choice,authorized:true}});
  alert(r.detail);
}
async function explainDecision(id){
  const output=$('#explain-'+id);
  if(!output) return;
  output.textContent='Consultando a Luna sobre la propuesta guardada…';
  try{
    const result=await api(`/decisions/${id}/explain`,{method:'POST'});
    if($('#explain-'+id)===output) output.textContent=`${result.explanation}\nModelo: ${result.model}. Explicación de una propuesta existente; no es una nueva decisión.`;
  }catch(e){ if($('#explain-'+id)===output) output.textContent=reviewError(e,'No se pudo explicar la propuesta.'); }
}
let _fundPhotoContext=null, _fundPhotoVersion=0;
async function fundForm(tk){
  const f = await api('/fundamentals/'+tk);
  const cur = f.fundamentals;
  _fundPhotoContext={ticker:tk,fields:f.fields,existing:Object.keys(cur).length>0,source:f.source,period:f.period};
  $('#an-out').innerHTML = `
  <div class="card"><h3>Fundamentales de ${esc(tk)}</h3>
  <p class="sub">Ingresa datos anuales o TTM de un informe verificable. No mezcles cifras trimestrales con anuales para el DCF. Fuente y fecha obligatorias; sin datos el sistema no inventa nada.</p>
  <div class="review-step"><h4>Extraer un informe por foto</h4>
    <p class="sm mut">Una captura legible de un informe puede aportar cifras sin escalarlas. El modelo de IA puede generar costo y devolver campos vacíos. Comprueba período, fecha de cierre y escalas de dinero y acciones en el informe; un trimestre aislado no se guarda como anual.</p>
    <div class="row"><input id="fp-file" type="file" accept="image/*" style="max-width:320px" onchange="fundPhotoChanged()">
      <button id="fp-analyze" type="button" onclick="fundPhotoAnalyze()">Analizar informe</button>
      <span id="fp-status" class="sm mut" role="status"></span></div>
    <div id="fp-review"></div>
  </div>
  <h3>Registro manual</h3>
  <div class="grid g3">
  ${f.fields.map(([k,label])=>`<div><label>${esc(label)}</label><input id="f-${k}" value="${esc(cur[k]??'')}"></div>`).join('')}
  </div>
  <div class="grid g2" style="margin-top:8px">
    <div><label>Fuente (obligatoria)</label><input id="f-source" value="${esc(f.source||'')}" placeholder="p. ej. informe 10-K FY2026, ir.nvidia.com"></div>
    <div><label>Fecha del dato (obligatoria)</label><input id="f-asof" value="${esc(f.asof||'')}" placeholder="2026-05-28"></div>
  </div>
  <button style="margin-top:10px" onclick="saveFund('${tk}',${JSON.stringify(f.fields.map(x=>x[0]))
    .replaceAll('"',"'")})">Guardar fundamentales</button></div>`;
}
function fundPhotoChanged(){
  _fundPhotoVersion++;
  if($('#fp-review')) $('#fp-review').replaceChildren();
  if($('#fp-status')) $('#fp-status').textContent=$('#fp-file').files[0] ? `Listo para analizar: ${$('#fp-file').files[0].name}` : '';
}
async function fundPhotoAnalyze(){
  const file=$('#fp-file')?.files[0], button=$('#fp-analyze'), ctx=_fundPhotoContext;
  if(!file || !file.type.startsWith('image/')){ $('#fp-status').textContent='Selecciona una imagen de un informe.'; return; }
  const version=++_fundPhotoVersion;
  $('#fp-review').replaceChildren(); button.disabled=true;
  $('#fp-status').textContent='Extrayendo datos con el proveedor de IA…';
  try{
    const image_b64=imagePayload(await photoShrink(file));
    const r=await api('/fundamentals/photo/analyze',{method:'POST',body:{image_b64,mime:'image/jpeg'}});
    if(!$('#fp-review') || _fundPhotoContext!==ctx || version!==_fundPhotoVersion || $('#fp-file').files[0]!==file) return;
    $('#fp-status').textContent=`Borrador extraído · modelo: ${r.model}`;
    const units=['USD','miles USD','millones USD','miles de millones USD'];
    const shares=['acciones','miles acciones','millones acciones','miles de millones acciones'];
    const options=(values,selected)=>'<option value="">Selecciona tras verificar el informe</option>'+values.map(v=>`<option value="${esc(v)}" ${v===selected?'selected':''}>${esc(v)}</option>`).join('');
    $('#fp-review').innerHTML=`<div class="review-step"><h4>Borrador sin guardar</h4>
      <p class="sm mut">Las cifras monetarias se transcriben sin escalar y se convertirán a USD al guardar. Acciones tienen escala independiente; EPS es USD por acción y no se escala. Un campo vacío significa que no se vio.</p>
      ${r.warnings.length?`<div class="alert"><b>Advertencias de extracción</b><ul>${r.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></div>`:''}
      <table class="review-table"><tr><th>Dato del informe</th><th>Valor visible / corregido</th></tr>
      ${ctx.fields.map(([key,label])=>`<tr><td><label for="fp-${key}">${esc(label)}</label></td>
        <td>${['moat','key_risks','business_model','customer_concentration'].includes(key)
          ?`<textarea id="fp-${key}" maxlength="500">${esc(r.data[key]??'')}</textarea>`
          :`<input id="fp-${key}" ${key==='next_earnings_date'?'type="date"':'inputmode="decimal"'} value="${esc(r.data[key]??'')}">`}</td></tr>`).join('')}</table>
      <div class="grid g2">
        <div><label for="fp-source">Fuente exacta del informe (obligatoria)</label><input id="fp-source" placeholder="Título del informe y emisor"></div>
        <div><label for="fp-asof">Fecha de cierre del informe (obligatoria)</label><input id="fp-asof" type="date" value="${esc(r.report_asof??'')}"></div>
        <div><label for="fp-period">Período de las cifras (anual o TTM)</label><select id="fp-period">${options(['anual','TTM'],r.period)}</select>
          ${r.period==='trimestral'?'<p class="alert">Informe trimestral: no se guarda como anual ni TTM. Usa un informe anual o TTM verificable.</p>':''}</div>
        <div><label for="fp-unit">Escala de importes (ingresos, FCF, deuda, caja, EBITDA, recompras)</label><select id="fp-unit">${options(units,r.unit)}</select></div>
        <div><label for="fp-shares-unit">Escala independiente de acciones en circulación</label><select id="fp-shares-unit">${options(shares,r.shares_unit)}</select></div>
      </div>
      ${ctx.existing?`<div class="alert riesgo_elevado">Ya hay fundamentales para ${esc(ctx.ticker)} (fuente: ${esc(fundCurrentSource(ctx.ticker))}). Guardar esta foto reemplazará los datos anteriores, incluidos campos que ahora queden vacíos.
        <label class="review-check"><input id="fp-replace" type="checkbox">Acepto reemplazar los fundamentales existentes después de compararlos.</label></div>`:''}
      <label class="review-check"><input id="fp-confirm" type="checkbox">He contrastado campos, fecha, período y ambas escalas con el informe original.</label>
      <button id="fp-save" type="button" onclick="fundPhotoSave()">Guardar informe revisado</button>
      <p id="fp-save-status" class="sm" role="status"></p>
    </div>`;
  }catch(e){ if($('#fp-status') && version===_fundPhotoVersion) $('#fp-status').textContent=reviewError(e,e.message||'No se pudo analizar el informe.'); }
  finally{ if($('#fp-analyze')) button.disabled=false; }
}
function fundCurrentSource(ticker){ return _fundPhotoContext?.ticker===ticker ? (_fundPhotoContext.source||'no indicada') : 'no indicada'; }
async function fundPhotoSave(){
  const ctx=_fundPhotoContext, status=$('#fp-save-status'), button=$('#fp-save');
  if(!ctx || !status) return;
  const source=$('#fp-source').value.trim(), asof=$('#fp-asof').value, period=$('#fp-period').value;
  const unit=$('#fp-unit').value, shares_unit=$('#fp-shares-unit').value;
  if(!source || !asof || !period || !unit || !shares_unit || !$('#fp-confirm').checked){
    status.textContent='Confirma fuente, fecha de cierre, período anual/TTM, las dos escalas y la revisión del informe.'; return;
  }
  if(ctx.existing && !$('#fp-replace').checked){ status.textContent='Para reemplazar los datos existentes marca el consentimiento expreso.'; return; }
  if(!$('#fp-asof').checkValidity()){ status.textContent='La fecha de cierre no es válida.'; return; }
  const data={};
  ctx.fields.forEach(([key])=>{ const value=$('#fp-'+key).value.trim(); data[key]=value===''?null:value; });
  if(!Object.values(data).some(x=>x!==null)){ status.textContent='No hay valores visibles para guardar.'; return; }
  button.disabled=true; status.textContent='Guardando solo los datos revisados…';
  try{
    const body={data,source,asof,period,unit,shares_unit};
    if(ctx.existing) body.replace_existing=true;
    await api('/fundamentals/'+encodeURIComponent(ctx.ticker)+'/photo/save',{method:'POST',body});
    if($('#fp-save-status')){
      status.textContent='Informe guardado. Reabre Fundamentales para importar otro informe o vuelve a analizar el activo.';
      button.disabled=true; $('#fp-analyze').disabled=true;
    }
  }catch(e){ if($('#fp-save-status')) status.textContent=reviewError(e,'No se pudo guardar el informe.'); }
  finally{ if($('#fp-save') && !status.textContent.startsWith('Informe guardado')) button.disabled=false; }
}
async function saveFund(tk, keys){
  if(_fundPhotoContext?.ticker===tk && _fundPhotoContext.period &&
     !confirm('El ingreso manual reemplazará los datos extraídos del informe, incluidas su fecha y sus unidades. ¿Ya verificaste las cifras y deseas reemplazarlas?')) return;
  const data = {};
  keys.forEach(k=>{ const v=$('#f-'+k).value.trim(); if(v!=='') data[k]=isNaN(+v)?v:+v; });
  try{
    await api('/fundamentals/'+tk,{method:'PUT',body:{data,source:$('#f-source').value,asof:$('#f-asof').value}});
    alert('Guardado. Vuelve a Analizar.'); analisis(tk);
  }catch(e){ alert(e.detail||'Error'); }
}

/* ---------- 4. Comparador ---------- */
async function comparador(){
  const pf = await api('/portfolio');
  $('#view').innerHTML = `
  <h2>Comparador de alternativas</h2>
  <p class="sub">Genera el análisis de cada posición y compara las decisiones propuestas lado a lado.</p>
  <div class="card"><button onclick="runCompare()">Comparar todas las posiciones</button></div>
  <div id="cmp-out"></div>${DISC}`;
}
async function runCompare(){
  const pf = await api('/portfolio');
  $('#cmp-out').innerHTML = '<p class="mut">Analizando todas las posiciones…</p>';
  const results = [];
  for(const p of pf.positions){
    try{ results.push(await api('/analysis/'+p.ticker,{method:'POST',body:{}})); }
    catch(e){ results.push({ticker:p.ticker, error:e.detail}); }
  }
  $('#cmp-out').innerHTML = `<div class="card"><table>
    <tr><th>Ticker</th><th>Peso</th><th>Resultado</th><th>Margen seg. (base)</th><th>Decisión propuesta</th><th>Confianza</th><th>Argumento principal</th></tr>
    ${results.map(r=> r.error? `<tr><td>${r.ticker}</td><td colspan="6" class="warn sm">${esc(r.error)}</td></tr>` : `<tr>
      <td><a href="#analisis/${r.ticker}"><b>${r.ticker}</b></a></td>
      <td>${fmt(r.peso_en_cartera_pct,1)} %</td>
      <td class="${cls(r.resultado)}">$ ${fmt(r.resultado)}</td>
      <td>${r.valoracion.calculable? fmt(r.valoracion.escenarios.base.margen_de_seguridad_pct,1)+' %':'<span class="pill warn">faltan datos</span>'}</td>
      <td><span class="pill">${esc(r.decision.decision_propuesta.replaceAll('_',' '))}</span></td>
      <td>${esc(r.decision.nivel_confianza)}</td>
      <td class="sm mut">${esc((r.decision.argumentos[0]||'').slice(0,120))}</td></tr>`).join('')}
  </table></div>`;
}

/* ---------- 5. Simulador ---------- */
async function simulador(){
  const pf = await api('/portfolio');
  $('#view').innerHTML = `
  <h2>Simulador de escenarios</h2>
  <p class="sub">Simulación aritmética sobre tus datos. No es una predicción; los supuestos siempre se muestran.</p>
  <div class="card"><h3>Variaciones de precio</h3>
    ${pf.positions.map(p=>`<div class="row"><span style="width:60px"><b>${p.ticker}</b></span>
      <input id="sim-${p.ticker}" type="number" style="width:110px" placeholder="%" value="0"> <span class="sm mut">% de variación</span></div>`).join('')}
    <h3 style="margin-top:12px">Operación simulada (opcional)</h3>
    <div class="row">
      <select id="sim-side" style="width:120px"><option value="">ninguna</option><option value="comprar">comprar</option><option value="vender">vender</option></select>
      <input id="sim-tk" placeholder="Ticker" style="width:100px">
      <input id="sim-amt" type="number" placeholder="USD" style="width:110px">
      <span class="sm mut">Efectivo disponible: $ ${fmt(pf.cash)}</span>
    </div>
    <div class="row" style="margin-top:10px">
      <button onclick="runSim()">Simular</button>
      <button class="mini sec" onclick="preset(-10)">Todos −10%</button>
      <button class="mini sec" onclick="preset(-20)">−20%</button>
      <button class="mini sec" onclick="preset(-30)">−30%</button>
      <button class="mini sec" onclick="preset(15)">Recuperación +15%</button>
    </div></div>
  <div id="sim-out"></div>${DISC}`;
  window._simTk = pf.positions.map(p=>p.ticker);
}
function preset(v){ window._simTk.forEach(t=>{ $('#sim-'+t).value=v; }); runSim(); }
async function runSim(){
  const changes = {}; window._simTk.forEach(t=>{ const v=+$('#sim-'+t).value; if(v) changes[t]=v; });
  const trades = [];
  if($('#sim-side').value && $('#sim-tk').value && +$('#sim-amt').value)
    trades.push({ticker:$('#sim-tk').value, side:$('#sim-side').value, amount_usd:+$('#sim-amt').value});
  let r;
  try{ r = await api('/simulate',{method:'POST',body:{changes,trades}}); }
  catch(e){ $('#sim-out').innerHTML=`<div class="alert riesgo_elevado">${esc(e.detail||'No se pudo simular. Revisa tus precios.')}</div>`; return; }
  $('#sim-out').innerHTML = `<div class="card"><h3>Resultado simulado</h3>
    <div class="grid g3">
      <div><div class="mut sm">Valor final estimado</div><div class="big">$ ${fmt(r.valor_final_estimado)}</div></div>
      <div><div class="mut sm">Efectivo final</div><div class="big">$ ${fmt(r.efectivo_final)}</div></div>
      <div><div class="mut sm">HHI resultante</div><div class="big">${r.hhi_resultante}</div></div>
    </div>
    <p class="sm"><b>Concentración resultante:</b> ${r.concentracion_resultante.map(w=>`${w.ticker} ${w.peso_pct}%`).join(' · ')||'—'}</p>
    <p class="sm"><b>Supuestos aplicados:</b></p><ul class="sm">${r.supuestos.map(s=>`<li>${esc(s)}</li>`).join('')}</ul>
    <p class="sm mut">${esc(r.nota)}</p></div>`;
}

/* ---------- 6. Oportunidades ---------- */
async function oportunidades(){
  const r = await api('/candidates');
  $('#view').innerHTML = `
  <h2>Buscador de oportunidades</h2>
  <p class="sub">${esc(r.nota)}</p>
  <div class="card"><h3>Agregar candidato (con tus datos y fuente)</h3>
    <div class="grid g3">
      <div><label>Ticker</label><input id="c-tk"></div>
      <div><label>Nombre</label><input id="c-name"></div>
      <div><label>Fuente de tus datos (obligatoria)</label><input id="c-src" placeholder="p. ej. 10-K + análisis propio"></div>
      ${['calidad','crecimiento','valoracion','margen_seguridad','solidez','riesgo'].map(k=>
        `<div><label>${k.replaceAll('_',' ')} (0–10)</label><input id="c-${k}" type="number" min="0" max="10"></div>`).join('')}
    </div>
    <label>Tesis</label><textarea id="c-tesis"></textarea>
    <div class="grid g3">
      <div><label>Catalizadores</label><input id="c-cat"></div>
      <div><label>Condición de entrada</label><input id="c-ent"></div>
      <div><label>Condición de invalidación</label><input id="c-inv"></div>
    </div>
    <button style="margin-top:10px" onclick="addCand()">Agregar al ranking</button></div>
  <div class="card"><h3>Ranking (${r.candidates.length})</h3>
    <table><tr><th>#</th><th>Ticker</th><th>Puntaje</th><th>Tesis</th><th>Condiciones</th><th>Fuente</th><th></th></tr>
    ${r.candidates.map((c,i)=>`<tr><td>${i+1}</td><td><b>${c.ticker}</b><br><span class="sm mut">${esc(c.name||'')}</span></td>
      <td><b>${c.ranking_score??'—'}</b></td>
      <td class="sm">${esc(c.data.tesis||'')}</td>
      <td class="sm">entrada: ${esc(c.data.condicion_entrada||'—')}<br>invalida: ${esc(c.data.condicion_invalidacion||'—')}</td>
      <td class="sm mut">${esc(c.source)}</td>
      <td><button class="mini danger" onclick="delCand(${c.id})">✕</button></td></tr>`).join('')}
    </table>
    <p class="sm mut">Compara contra tus posiciones actuales en el Comparador antes de sustituir.</p></div>${DISC}`;
}
async function delCand(id){ await api('/candidates/'+id,{method:'DELETE'}); oportunidades(); }
async function addCand(){
  const data = {tesis:$('#c-tesis').value, catalizadores:$('#c-cat').value,
    condicion_entrada:$('#c-ent').value, condicion_invalidacion:$('#c-inv').value};
  ['calidad','crecimiento','valoracion','margen_seguridad','solidez','riesgo'].forEach(k=>{
    const v=$('#c-'+k).value; if(v!=='') data[k]=+v; });
  try{
    await api('/candidates',{method:'POST',body:{ticker:$('#c-tk').value,name:$('#c-name').value,source:$('#c-src').value,data}});
    oportunidades();
  }catch(e){ alert(e.detail||'Error'); }
}

/* ---------- 7. Alertas ---------- */
async function alertasView(){
  const r = await api('/alerts');
  $('#view').innerHTML = `
  <h2>Alertas</h2><p class="sub">Clasificadas: informativa · revisión necesaria · riesgo elevado · acción pendiente · dato no verificado. Sin ruido por movimientos diarios irrelevantes (&lt;5%).</p>
  ${r.alerts.length? r.alerts.map(a=>`<div class="alert ${a.level}"><span class="pill mut">${esc(a.level.replaceAll('_',' '))}</span> ${esc(a.text)}</div>`).join('')
   :'<div class="card"><p class="mut">Sin alertas activas.</p></div>'}${DISC}`;
}

/* ---------- 8. Diario ---------- */
async function diario(){
  const r = await api('/journal');
  $('#view').innerHTML = `
  <h2>Diario de inversión</h2>
  <p class="sub">Registra la tesis ANTES de operar y evalúa DESPUÉS el proceso, no solo el resultado: una decisión puede ser correcta y perder dinero (y viceversa).</p>
  <div class="card"><h3>Nueva entrada</h3>
    <div class="grid g3">
      <div><label>Ticker</label><input id="j-tk"></div>
      <div><label>Acción</label><select id="j-act">${['revision','comprar','agregar','reducir','vender','esperar'].map(a=>`<option>${a}</option>`).join('')}</select></div>
      <div><label>Fecha de revisión de la tesis</label><input id="j-rev" type="date"></div>
    </div>
    <div class="grid g2">
      <div><label>Motivo *</label><textarea id="j-motivo"></textarea></div>
      <div><label>Tesis *</label><textarea id="j-tesis"></textarea></div>
      <div><label>Riesgos *</label><textarea id="j-riesgos"></textarea></div>
      <div><label>Condición de invalidación *</label><textarea id="j-inv"></textarea></div>
    </div>
    <div class="grid g3">
      <div><label>Precio</label><input id="j-precio" type="number" step="any"></div>
      <div><label>Horizonte</label><input id="j-hor"></div>
      <div><label>Catalizadores</label><input id="j-cat"></div>
      <div><label>Condiciones de salida</label><input id="j-sal"></div>
      <div><label>Pérdida tolerable</label><input id="j-perd"></div>
      <div><label>Tamaño de posición</label><input id="j-tam"></div>
      <div><label>Estado emocional</label><input id="j-emo" placeholder="tranquilo / FOMO / miedo…"></div>
      <div><label>Fuentes consultadas</label><input id="j-fue"></div>
    </div>
    <button style="margin-top:10px" onclick="addJournal()">Registrar</button>
    <p class="sm mut">* obligatorios si la acción es una operación (comprar/vender/agregar/reducir).</p></div>
  ${r.entries.map(e=>`<div class="card"><h3>${esc(e.ticker||'cartera')} · ${esc(e.action)} <span class="sm mut">${e.created_at.slice(0,10)}</span>
    ${e.evaluation?'<span class="pill ok">evaluada</span>':(e.review_date?`<span class="pill warn">revisar ${e.review_date}</span>`:'')}</h3>
    <p class="sm"><b>Tesis:</b> ${esc(e.data.tesis||'—')} · <b>Riesgos:</b> ${esc(e.data.riesgos||'—')} · <b>Invalidación:</b> ${esc(e.data.condicion_invalidacion||'—')}</p>
    <button class="mini sec" type="button" onclick="challengeJournal(${e.id})">Cuestionar tesis con Luna</button>
    <p class="sm mut">Luna propone preguntas, no órdenes. La consulta al proveedor de IA puede generar costo.</p>
    <div id="challenge-${e.id}" class="assistant-answer sm" role="status"></div>
    ${e.evaluation? `<p class="sm"><b>Evaluación:</b> ${esc(e.evaluation.que_ocurrio||'')} · proceso/suerte: ${esc(e.evaluation.suerte_o_proceso||'')} · lección: ${esc(e.evaluation.leccion||'')}</p>`
     : `<details><summary class="sm">Evaluar ahora</summary>
        <div class="grid g3">
        <div><label>¿Qué ocurrió?</label><input id="ev-que-${e.id}"></div>
        <div><label>¿Tesis correcta?</label><select id="ev-tesis-${e.id}"><option>sí</option><option>no</option><option>parcialmente</option></select></div>
        <div><label>¿Suerte o proceso?</label><select id="ev-sp-${e.id}"><option>proceso</option><option>suerte</option><option>mala suerte con buen proceso</option><option>mal proceso</option></select></div>
        <div><label>¿Hubo FOMO?</label><select id="ev-fomo-${e.id}"><option>no</option><option>sí</option></select></div>
        <div><label>¿Se vendió por miedo?</label><select id="ev-miedo-${e.id}"><option>no</option><option>sí</option></select></div>
        <div><label>Lección</label><input id="ev-lec-${e.id}"></div></div>
        <button class="mini" style="margin-top:8px" onclick="evalJournal(${e.id})">Guardar evaluación</button></details>`}
  </div>`).join('')}${DISC}`;
}
async function challengeJournal(id){
  const output=$('#challenge-'+id);
  if(!output) return;
  output.textContent='Consultando contraargumentos para la tesis guardada…';
  try{
    const result=await api(`/journal/${id}/challenge`,{method:'POST'});
    if($('#challenge-'+id)===output) output.textContent=result.counterarguments.map((item,i)=>
      `${i+1}. ${item.argumento}\n${item.verificar}`).join('\n\n')+`\n\nModelo: ${result.model}. Verifica las preguntas con tus fuentes.`;
  }catch(e){ if($('#challenge-'+id)) output.textContent=reviewError(e,'No se pudo cuestionar la tesis.'); }
}
async function addJournal(){
  try{
    await api('/journal',{method:'POST',body:{ticker:$('#j-tk').value,action:$('#j-act').value,
      motivo:$('#j-motivo').value,tesis:$('#j-tesis').value,riesgos:$('#j-riesgos').value,
      condicion_invalidacion:$('#j-inv').value,precio:$('#j-precio').value?+$('#j-precio').value:null,
      horizonte:$('#j-hor').value,catalizadores:$('#j-cat').value,condiciones_salida:$('#j-sal').value,
      perdida_tolerable:$('#j-perd').value,tamano_posicion:$('#j-tam').value,
      estado_emocional:$('#j-emo').value,fuentes:$('#j-fue').value,review_date:$('#j-rev').value}});
    diario();
  }catch(e){ alert(e.detail||'Error'); }
}
async function evalJournal(id){
  await api(`/journal/${id}/evaluate`,{method:'POST',body:{
    que_ocurrio:$('#ev-que-'+id).value, tesis_correcta:$('#ev-tesis-'+id).value,
    suerte_o_proceso:$('#ev-sp-'+id).value, hubo_fomo:$('#ev-fomo-'+id).value,
    vendio_por_miedo:$('#ev-miedo-'+id).value, leccion:$('#ev-lec-'+id).value}});
  diario();
}

/* ---------- 9. Historial ---------- */
async function historial(){
  const [d, a] = await Promise.all([api('/decisions'), api('/audit')]);
  $('#view').innerHTML = `
  <h2>Historial</h2><p class="sub">Decisiones propuestas vs. registradas, y registro de auditoría completo.</p>
  <div class="card"><h3>Decisiones (${d.decisions.length})</h3>
    <table><tr><th>Fecha</th><th>Ticker</th><th>Propuesta</th><th>Tu decisión</th><th>Contexto</th></tr>
    ${d.decisions.map(x=>`<tr><td class="sm">${x.created_at.slice(0,16).replace('T',' ')}</td><td><b>${x.ticker}</b></td>
      <td><span class="pill">${esc(x.proposal.decision)}</span> <span class="sm mut">conf. ${esc(x.proposal.confianza)}</span></td>
      <td>${x.user_choice?`<b>${esc(x.user_choice)}</b>`:'<span class="mut sm">sin registrar</span>'}</td>
      <td class="sm mut">peso ${fmt(x.proposal.peso,1)}% · margen ${x.proposal.margen_seguridad==null?'s/d':fmt(x.proposal.margen_seguridad,1)+'%'}
        ${x.proposal.argumentos?.length?`<br><button class="mini sec" type="button" onclick="explainDecision(${x.id})">Explicar con Luna</button>
          <div id="explain-${x.id}" class="assistant-answer sm" role="status"></div>`:
          '<br>Propuesta antigua: no se guardaron los argumentos para explicarla.'}</td></tr>`).join('')}</table></div>
  <div class="card"><h3>Auditoría</h3>
    <table>${a.log.slice(0,40).map(l=>`<tr><td class="sm">${l.at.slice(0,16).replace('T',' ')}</td>
      <td><span class="pill mut">${esc(l.action)}</span></td><td class="sm mut">${esc(l.detail||'')}</td></tr>`).join('')}</table></div>${DISC}`;
}

/* ---------- 10. Perfil de riesgo ---------- */
const PROFILE_LABELS = {capital_total:'Capital total (USD)',capital_disponible:'Capital disponible para invertir',
  aporte_mensual:'Aporte mensual',fondo_emergencia:'¿Tienes fondo de emergencia? (sí/no/meses)',moneda:'Moneda principal',
  horizonte_anios:'Horizonte de inversión (años)',objetivo:'Objetivo financiero',rentabilidad_esperada_pct:'Rentabilidad esperada %',
  perdida_maxima_pct:'Pérdida máxima tolerable %',necesita_retirar:'¿Necesitarás retirar el dinero? (cuándo)',
  experiencia:'Experiencia invirtiendo',nivel_riesgo:'Nivel de riesgo (conservador/moderado/agresivo)',
  ingresos_estables:'Ingresos y estabilidad financiera',max_por_empresa_pct:'Máximo % por empresa',
  max_por_sector_pct:'Máximo % por sector',prefiere_fondos:'¿Prefieres acciones o fondos diversificados?',
  restricciones:'Restricciones personales',comisiones_impuestos:'Comisiones e impuestos aplicables'};
async function perfil(){
  const r = await api('/profile');
  $('#view').innerHTML = `
  <h2>Perfil de riesgo del inversionista</h2>
  <p class="sub">${r.complete?'✅ Perfil completo: las recomendaciones pueden personalizarse.':'⚠️ Perfil incompleto: los análisis serán informativos, no recomendaciones personalizadas.'}</p>
  <div class="card"><div class="grid g3">
    ${r.fields.map(f=>`<div><label>${PROFILE_LABELS[f]||f}</label><input id="rp-${f}" value="${esc(r.profile[f]??'')}"></div>`).join('')}
  </div><button style="margin-top:12px" onclick="saveProfile()">Guardar perfil</button></div>${DISC}`;
  window._rpFields = r.fields;
}
async function saveProfile(){
  const body = {}; window._rpFields.forEach(f=>{ body[f]=$('#rp-'+f).value; });
  const r = await api('/profile',{method:'PUT',body});
  alert(r.complete?'Perfil completo ✅':'Guardado. Faltan: '+r.missing.join(', ')); perfil();
}

/* ---------- 11. Configuración (límites de riesgo) ---------- */
const LIMIT_LABELS = {max_position_pct:'Máximo % por empresa',max_sector_pct:'Máximo % por sector',
  max_trade_pct:'Máximo % por operación',max_tolerable_loss_pct:'Pérdida máxima tolerable %',
  min_cash_reserve:'Reserva mínima de efectivo (USD)',max_trades_per_month:'Máx. operaciones al mes'};
async function config(){
  const s = await api('/settings');
  $('#view').innerHTML = `
  <h2>Configuración</h2><p class="sub">Reglas de riesgo que alimentan alertas y el motor de decisiones.</p>
  <div class="card"><h3>Límites de riesgo</h3><div class="grid g3">
    ${Object.entries(s.limits).map(([k,v])=>`<div><label>${LIMIT_LABELS[k]||k}</label><input id="lm-${k}" type="number" step="any" value="${v}"></div>`).join('')}
  </div><button style="margin-top:12px" onclick="saveLimits(${JSON.stringify(Object.keys(s.limits)).replaceAll('"',"'")})">Guardar límites</button></div>
  <div class="card"><h3 style="color:var(--err)">Zona de peligro</h3>
    <p class="sm">Elimina posiciones, fundamentales, diario, decisiones, candidatos y auditoría.</p>
    <button class="danger" onclick="wipe()">Eliminar todos mis datos</button></div>${DISC}`;
}
async function saveLimits(keys){
  const body={}; keys.forEach(k=>{ body[k]=+$('#lm-'+k).value; });
  await api('/limits',{method:'PUT',body}); alert('Límites guardados'); config();
}
async function wipe(){
  if(prompt('Irreversible. Escribe ELIMINAR:')==='ELIMINAR'){
    await api('/settings/delete_all',{method:'POST',body:{confirm:'ELIMINAR'}}); alert('Datos eliminados'); route();
  }
}

api('/me').then(showApp).catch(showLogin);
