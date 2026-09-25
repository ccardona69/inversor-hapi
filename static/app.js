const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n,d=2) => n==null?'—':Number(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const cls = n => n==null?'':(n>=0?'pos':'neg');
async function api(path, opts={}){
  const r = await fetch('/api'+path,{headers:{'Content-Type':'application/json'},...opts,
    body: opts.body?JSON.stringify(opts.body):undefined});
  const data = await r.json().catch(()=>({}));
  if(!r.ok){ data._status=r.status; throw data; }
  return data;
}
window.addEventListener('hashchange', route);
async function route(){
  const [page, arg] = location.hash.replace('#','').split('/');
  const aliases = {asistente:'inicio',alertas:'inicio',historial:'diario',perfil:'ajustes',config:'ajustes',operar:'analisis'};
  const resolved = aliases[page]||page||'inicio';
  document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active', a.hash==='#'+resolved));
  const views = {inicio,cartera,analisis,diario,oportunidades,ajustes};
  try{ await (views[resolved]||inicio)(arg); }
  catch(e){ $('#view').innerHTML=`<div class="card">Error: ${esc(e.detail||e.message||JSON.stringify(e))}</div>`; }
}
const DISC = '<p class="disc">Herramienta de apoyo con datos aportados por el usuario y fuentes públicas citadas. No es asesoría financiera regulada, no garantiza rentabilidad y no ejecuta operaciones.</p>';

/* ---------- 1. Hoy (panel principal con Luna) ---------- */
let _lunaChat = [], _lunaSugs = [], _lunaConfigured = null;
let _lastPriceRefresh = 0, _currentTickers = [];

/* ---------- Mercado hoy y niveles por acción (regla técnica, no predicción) ---------- */
const SEMAFORO_MKT = {normal:'ok', cauteloso:'warn', miedo:'err', sin_datos:'mut'};
const SEMAFORO_ACC = {descuento:'ok', estirada:'warn', bajista:'err', neutral:'mut'};
const pctS = (v,d=1) => v==null?'—':(v>0?'+':'')+fmt(v,d)+' %';
const hora = iso => iso ? String(iso).replace('T',' ').slice(0,16) : '';
function marketPulseHtml(p){
  if(!p) return '<h3>Mercado hoy</h3><p class="sm mut">Sin datos de mercado ahora</p>';
  const ok = (p.instrumentos||[]).filter(i=>!i.error);
  return `<h3>Mercado hoy</h3>
    <p class="sm"><span class="pill ${SEMAFORO_MKT[p.semaforo]||'mut'}">${esc((p.semaforo||'—').replaceAll('_',' '))}</span>
      ${p.tipo_dia?`<b>Día ${esc(p.tipo_dia)}</b> · `:''}${esc(p.lectura||'')}</p>
    <div class="mkt-chips">${ok.map(i=>`<span class="mkt-chip"><span class="mut">${esc(i.nombre)}</span>
      <b>${fmt(i.price)}</b> <span class="${cls(i.day_change_pct)}">${pctS(i.day_change_pct)}</span></span>`).join('')}
      ${(p.instrumentos||[]).filter(i=>i.error).map(i=>`<span class="mkt-chip mut">${esc(i.nombre)}: sin dato</span>`).join('')}</div>
    <p class="sm mut">${esc(p.fuente||'')}${ok[0]?.asof?` · cotización ${esc(hora(ok[0].asof))}`:''} · leído ${esc(hora(p.fetched_at))}. ${esc(p.nota||'')}</p>`;
}
function nivelesHtml(n, posicion, extra=''){
  if(!n) return `<p class="sm mut">Histórico insuficiente para niveles.</p>${extra}`;
  const dc = posicion && posicion.avg_cost ? `<div>Desde tu costo ($ ${fmt(posicion.avg_cost)}): hoy <span class="${cls(posicion.desde_costo_pct)}">${pctS(posicion.desde_costo_pct)}</span>
      · stop <span class="${cls(posicion.stop_desde_costo_pct)}">${pctS(posicion.stop_desde_costo_pct)}</span> · toma <span class="${cls(posicion.toma_desde_costo_pct)}">${pctS(posicion.toma_desde_costo_pct)}</span></div>` : '';
  return `<p class="sm"><span class="pill ${SEMAFORO_ACC[n.semaforo]||'mut'}">${esc(n.semaforo)}</span>
      ${n.tipo_dia?`<span class="pill mut">día ${esc(n.tipo_dia)}</span> `:''}${esc(n.lectura)}</p>
    <div class="lv-grid sm">
      <div>${n.entrada_zona?`<b>Entrada escalonada</b> $ ${fmt(n.entrada_zona[0])} – $ ${fmt(n.entrada_zona[1])}<div class="mut">${esc(n.entrada_nota)}</div>`:`<b>Entrada</b> <span class="mut">${esc(n.entrada_nota)}</span>`}</div>
      <div><b>Stop loss</b> $ ${fmt(n.stop_loss)} <span class="neg">(${pctS(n.stop_loss_pct)})</span></div>
      <div><b>Toma parcial</b> $ ${fmt(n.toma_parcial)} <span class="pos">(${pctS(n.toma_parcial_pct)})</span></div>
      ${dc}
    </div>${extra}
    <p class="sm mut">${esc(n.regla)} Base $ ${fmt(n.precio_base)} · ATR14 ${fmt(n.atr14)}.</p>`;
}
async function loadLevels(tk){
  const box = document.getElementById('lv-'+tk);
  if(!box) return;
  box.innerHTML = '<p class="sm mut">Calculando niveles…</p>';
  try{
    const r = await api('/levels/'+encodeURIComponent(tk));
    const cur = document.getElementById('lv-'+tk); if(!cur) return;
    const src = `<p class="sm mut">Precio $ ${fmt(r.precio.valor)} · ${esc(r.precio.fuente||'')} · ${esc(hora(r.precio.asof))}${r.tecnica?.error?` · ${esc(r.tecnica.error)}`:''}</p>`;
    cur.innerHTML = `<b>Plan de niveles (regla ATR)</b>${nivelesHtml(r.niveles, r.posicion, src)}`;
  }catch(e){
    const cur = document.getElementById('lv-'+tk);
    if(cur) cur.innerHTML = `<p class="sm" style="color:var(--err)">${esc(e.detail||'No se pudieron calcular los niveles.')}</p>`;
  }
}

async function inicio(){
  const pulseP = api('/market/pulse').catch(()=>null);
  let [d, prof] = await Promise.all([api('/dashboard'), api('/profile')]);
  let refreshMsg = '';
  if(d.portfolio.positions.length && d.calidad_datos.some(q=>q.estado_precio!=='actual')
     && Date.now()-_lastPriceRefresh > 5*60*1000){
    _lastPriceRefresh = Date.now();
    try{
      const r = await api('/prices/refresh',{method:'POST'});
      if(r.errors.length) refreshMsg = 'No se pudieron actualizar los precios de '+r.errors.map(e=>e.ticker).join(', ')+'. Ingrésalos manualmente en Cartera.';
      else d = await api('/dashboard');
    }catch(e){ refreshMsg = 'No se pudieron actualizar los precios. Revisa tu conexión o ingrésalos manualmente en Cartera.'; }
  }
  const t = d.portfolio.totals, positions = d.portfolio.positions;
  const unverified = positions.filter(p=>!p.verified).length;
  const priced = positions.filter(p=>p.price_info && p.price_info.asof);
  const oldest = priced.length ? priced.reduce((a,b)=>b.price_info.asof<a.price_info.asof?b:a) : null;
  _lunaSugs = ['¿Cómo va mi cartera hoy?','¿Qué tan concentrado estoy y qué alternativas tengo?'];
  if(positions.length){
    const top = positions.reduce((a,b)=>(b.market_value||0)>(a.market_value||0)?b:a);
    _lunaSugs.push(`¿Qué debería vigilar de ${top.ticker}?`);
  }
  _lunaSugs.push((d.portfolio.cash||0)>=1 ? `¿Qué hago con mis $${fmt(d.portfolio.cash)} de efectivo?`
                                         : '¿Qué me falta completar para decidir mejor?');
  $('#view').innerHTML = `
  <h2>Hoy</h2><p class="sub">Tu cartera de un vistazo y Luna para lo que no se ve en las cifras.</p>
  ${refreshMsg?`<div class="alert">${esc(refreshMsg)}</div>`:''}
  ${t.sin_precio_vigente.length?`<div class="alert riesgo_elevado">Total y riesgo no calculables: faltan valores vigentes en USD para ${esc(t.sin_precio_vigente.join(', '))}. Revisa precios y monedas en <a href="#cartera">Cartera</a>.</div>`:''}
  ${d.portfolio.cash_currency!=='USD'?'<div class="alert riesgo_elevado">El efectivo no está en USD; el riesgo no se puede calcular sin un tipo de cambio verificable.</div>':''}
  ${t.sin_costo.length?`<div class="alert">Resultado no calculable: falta el costo invertido de ${esc(t.sin_costo.join(', '))}.</div>`:''}
  <div class="card" id="mkt-hoy" aria-live="polite"><h3>Mercado hoy</h3><p class="sm mut">Leyendo el mercado…</p></div>
  <div class="stat-strip" aria-label="Resumen numérico">
    <div><div class="mut sm">Valor actual</div><div class="big">${t.valor_actual==null?'—':'$ '+fmt(t.valor_actual)}</div></div>
    <div><div class="mut sm">Cambio de hoy</div><div class="big ${cls(t.cambio_dia)}">${t.cambio_dia==null?'—':`$ ${fmt(t.cambio_dia)} (${fmt(t.cambio_dia_pct,1)} %)`}</div></div>
    <div><div class="mut sm">Resultado total</div><div class="big ${cls(t.resultado)}">${t.resultado==null?'—':`$ ${fmt(t.resultado)} (${fmt(t.rendimiento_pct,1)} %)`}</div></div>
    <div><div class="mut sm">Efectivo</div><div class="big">${d.portfolio.cash==null?'—':'$ '+fmt(d.portfolio.cash)}</div></div>
  </div>
  ${oldest?`<p class="sm mut" style="margin-top:-8px">Precio más antiguo: ${esc(oldest.ticker)} · ${esc(oldest.price_info.fuente||'sin fuente')} · ${esc(oldest.price_info.asof)}</p>`:''}
  ${unverified?`<div class="alert">${unverified} posición(es) sin confirmar.
    <button class="mini" onclick="verifyAllPositions()">Confirmar todo</button> o revísalas una por una en <a href="#cartera">Cartera</a>.</div>`:''}
  <section class="luna-panel" aria-label="Conversación con Luna">
    <h3>Pregúntale a Luna</h3>
    <div class="luna-sugs">${_lunaSugs.map((s,i)=>`<button type="button" onclick="lunaSend(_lunaSugs[${i}])">${esc(s)}</button>`).join('')}</div>
    <div id="luna-log" class="luna-log" aria-live="polite"></div>
    <div class="luna-input-row">
      <textarea id="luna-input" maxlength="600" rows="2" placeholder="Escribe tu pregunta…"></textarea>
      <button id="luna-send" type="button" onclick="lunaSend()">Enviar</button>
      <button id="luna-new" class="sec" type="button" onclick="lunaNew()">Nueva conversación</button>
    </div>
    <p class="luna-note" id="luna-status" role="status"></p>
    <p class="luna-note">Luna usa tus datos guardados con su fuente y fecha. No opera ni cambia tu cartera. Cada mensaje es una consulta al proveedor de IA.</p>
  </section>
  ${positions.length?'':`<div class="card"><h3>Empezar</h3>
    <p class="sm">Sube una captura de tu cartera en Hapi o registra tus posiciones manualmente.</p>
    <a class="desk-action" href="#cartera">Ir a Cartera</a></div>`}
  <div class="grid g2">
  <div class="card"><h3>Distribución y concentración</h3>
    ${Object.entries(t.pesos_pct||{}).map(([k,v])=>{const dp=positions.find(p=>p.ticker===k)?.day_change_pct;
      return `<div class="row sm"><span style="width:60px"><b>${esc(k)}</b></span><span>${v} %</span>${dp==null?'':`<span class="${cls(dp)}">hoy ${pctS(dp)}</span>`}</div>`;}).join('')||`<p class="mut sm">${t.sin_precio_vigente.length?'Pendiente de valores vigentes en USD':'Sin posiciones valoradas'}</p>`}
    ${d.risk.error?`<p class="sm mut">${esc(d.risk.error)}</p>`:`<p class="sm" style="margin-top:8px">Concentración: <span class="pill ${d.risk.nivel_concentracion==='alta'?'err':'ok'}">${esc(d.risk.nivel_concentracion||'—')}</span>
     · HHI ${d.risk.hhi||'—'} · diversificación efectiva ≈ ${d.risk.diversificacion_efectiva||'—'} posiciones</p>`}
    ${(d.risk.correlacion||[]).map(c=>`<div class="alert">${esc(c)}</div>`).join('')}
  </div>
  <div class="card"><h3>Alertas (${d.alerts.length})</h3>
    ${d.alerts.slice(0,6).map(a=>`<div class="alert ${a.level}"><span class="pill mut">${esc(a.level.replaceAll('_',' '))}</span> ${esc(a.text)}</div>`).join('')||'<p class="mut sm">Sin alertas</p>'}
  </div></div>
  ${prof.complete?'':`<div class="card"><h3>Tu perfil de inversionista</h3>
    <p class="sm mut">Con el perfil completo las propuestas pueden personalizarse.</p>
    ${profileFormHtml(prof)}</div>`}
  ${DISC}`;
  window._rpFields = prof.fields;
  pulseP.then(p=>{ const box=$('#mkt-hoy'); if(box) box.innerHTML = marketPulseHtml(p); });
  renderLunaLog();
  const input = $('#luna-input');
  input.addEventListener('keydown', e=>{
    if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); lunaSend(); }
  });
  try{
    const s = await api('/assistant/status');
    if(!$('#luna-input')) return;
    _lunaConfigured = s.configured;
    $('#luna-send').disabled = !s.configured;
    $('#luna-input').disabled = !s.configured;
    $('#luna-status').textContent = s.configured ? `Modelo: ${s.model}` : s.hint;
  }catch(e){ if($('#luna-status')) $('#luna-status').textContent = e.detail||'No se pudo consultar el estado de Luna'; }
}
async function refreshPrices(){
  const r = await api('/prices/refresh',{method:'POST'});
  if(r.errors.length) alert('Algunos precios no se pudieron obtener:\n'+r.errors.map(e=>e.ticker+': '+e.error).join('\n')+'\nPuedes ingresarlos manualmente en Cartera.');
  return r;
}
async function verifyAllPositions(){
  const r = await api('/positions/verify_all',{method:'POST'});
  inicio();
  return r;
}

/* ---------- Chat de Luna (solo lectura; persiste al navegar, no al recargar) ---------- */
function renderLunaLog(){
  const log = $('#luna-log');
  if(!log) return;
  log.replaceChildren();
  _lunaChat.forEach(m=>{
    const wrap = document.createElement('div');
    wrap.className = 'luna-msg '+(m.role==='user'?'user':'assistant');
    const bubble = document.createElement('div');
    bubble.className = 'luna-bubble';
    bubble.textContent = m.content;
    wrap.appendChild(bubble);
    if(m.model){
      const meta = document.createElement('div');
      meta.className = 'luna-meta';
      meta.textContent = `Modelo: ${m.model} · consulta ${m.asof||''}`;
      wrap.appendChild(meta);
    }
    log.appendChild(wrap);
  });
  log.scrollTop = log.scrollHeight;
}
async function lunaSend(text){
  const input = $('#luna-input'), send = $('#luna-send'), log = $('#luna-log');
  const question = String(text ?? input?.value ?? '').trim();
  if(!question || (send && send.disabled)) return;
  if(input) input.value = '';
  if(send) send.disabled = true;
  const userMsg = {role:'user', content:question};
  _lunaChat.push(userMsg);
  renderLunaLog();
  const thinking = document.createElement('div');
  thinking.className = 'luna-msg assistant';
  thinking.id = 'luna-thinking';
  const tb = document.createElement('div');
  tb.className = 'luna-bubble luna-thinking';
  tb.textContent = 'Luna está pensando…';
  thinking.appendChild(tb);
  log.appendChild(thinking);
  log.scrollTop = log.scrollHeight;
  const history = _lunaChat.slice(0,-1).filter(m=>!m.error).slice(-8)
    .map(m=>({role:m.role, content:m.content.slice(0,4000)}));
  try{
    const r = await api('/assistant/ask',{method:'POST',body:{question, history}});
    thinking.remove();
    _lunaChat.push({role:'assistant', content:r.answer, model:r.model, asof:r.asof});
  }catch(e){
    thinking.remove();
    userMsg.error = true;
    _lunaChat.push({role:'assistant', error:true, content:'No se pudo consultar a Luna: '+(e.detail||'error de conexión')+'. Inténtalo de nuevo.'});
  }
  renderLunaLog();
  if(send) send.disabled = _lunaConfigured===false;
}
function lunaNew(){ _lunaChat = []; renderLunaLog(); }

/* ---------- 2. Cartera ---------- */
async function cartera(){
  const [pf, val] = await Promise.all([api('/portfolio'), api('/validate')]);
  const t = pf.totals, cash = pf.cash;
  const balance = t.valor_actual==null ? null : t.valor_actual + (cash||0);
  const pctOf = n => balance ? fmt(n/balance*100,1)+' % del balance' : '— %';
  const sgn = n => n>=0?'+':'-';
  const plFmt = p => p.unrealized_pl==null ? '—'
    : `${sgn(p.unrealized_pl)}$ ${fmt(Math.abs(p.unrealized_pl))}${p.return_pct==null?'':` (${sgn(p.return_pct)}${fmt(Math.abs(p.return_pct))} %)`}`;
  const DONUT = ['#0d6e5f','#3f9c86','#8fd0bf','#173430','#6f8f86','#b7d9cf'];
  const valued = pf.positions.filter(p=>p.market_value!=null);
  const donutTotal = valued.reduce((s,p)=>s+p.market_value,0);
  let _acc = 0;
  const donutBg = donutTotal>0
    ? 'conic-gradient('+valued.map((p,i)=>{const a=_acc;_acc+=p.market_value/donutTotal*100;
        return `${DONUT[i%DONUT.length]} ${a}% ${_acc}%`;}).join(', ')+')'
    : 'var(--acc2)';
  $('#view').innerHTML = `
  <h2>Cartera</h2><p class="sub">Lo que tienes hoy y cómo actualizarlo desde Hapi.</p>
  <div class="card"><h3>Tu cartera hoy</h3>
    ${t.sin_precio_vigente.length?`<div class="alert riesgo_elevado">El valor de algunas filas proviene de capturas, no está disponible o no está en USD. No hay un total actual fiable: ${esc(t.sin_precio_vigente.join(', '))}.</div>`:''}
    ${pf.cash_currency!=='USD'?`<div class="alert riesgo_elevado">Efectivo registrado en ${esc(pf.cash_currency)}: introduce el importe real en USD solo si lo verificaste; no se convierte automáticamente.</div>`:''}
    <div class="pf-top">
      <div>
        <div class="mut sm">Balance total</div>
        <div class="big pf-balance-num">${balance==null?'—':'$ '+fmt(balance)}</div>
        <div class="sm pf-line">En acciones <b>${t.valor_actual==null?'—':'$ '+fmt(t.valor_actual)}</b> <span class="mut">· ${pctOf(t.valor_actual||0)}</span></div>
        <div class="sm pf-line">Efectivo <b>${cash==null?'—':'$ '+fmt(cash)}</b> <span class="mut">· ${cash==null?'— %':pctOf(cash)}</span></div>
        <p class="sm mut pf-totals">Invertido $ ${fmt(t.invertido)} · Resultado <span class="${cls(t.resultado)}">${t.resultado==null?'—':`${sgn(t.resultado)}$ ${fmt(Math.abs(t.resultado))}${t.rendimiento_pct==null?'':` (${sgn(t.rendimiento_pct)}${fmt(Math.abs(t.rendimiento_pct))} %)`}`}</span></p>
      </div>
      <div class="pf-donut-zone">
        <div class="donut" style="background:${donutBg}" role="img" aria-label="Distribución de las posiciones"></div>
        <div class="donut-legend">${valued.map((p,i)=>`<span class="donut-chip"><i class="dot" style="background:${DONUT[i%DONUT.length]}"></i>${esc(p.ticker)} ${fmt(p.market_value/donutTotal*100,1)} %</span>`).join('')||'<span class="mut sm">Sin posiciones valoradas</span>'}</div>
      </div>
    </div>
  </div>
  <div class="card"><h3>Mis activos</h3>
    ${pf.positions.map(p=>`
    <details class="asset-row" data-tk="${esc(p.ticker)}">
      <summary>
        <span class="asset-ic">${esc((p.ticker||'?').charAt(0))}</span>
        <span class="asset-main"><b>${esc(p.ticker)}</b><span class="sm mut">${p.name?esc(p.name)+' · ':''}${p.qty} acciones</span></span>
        <span class="asset-val"><b>${p.market_value==null?`— ${esc(p.currency)}`:`${esc(p.currency)} ${fmt(p.market_value)}`}</b><span class="sm ${cls(p.unrealized_pl)}">${plFmt(p)}</span></span>
      </summary>
      <div class="asset-detail">
        <div><div class="mut sm">Costo prom.</div>$ ${fmt(p.avg_cost)}</div>
        <div><div class="mut sm">Invertido</div>$ ${fmt(p.invested)}</div>
        <div><div class="mut sm">Precio usado</div>${fmt(p.price_info.precio_usado)}
          <div class="sm mut">${esc(p.price_info.fuente||'')}</div>
          <div class="sm mut">${esc(p.price_info.asof||'fecha no registrada')}</div></div>
        <div class="asset-flags">
          <span class="pill ${p.price_status==='actual'?'ok':'warn'}">${esc(p.price_status.replaceAll('_',' '))}</span>
          ${p.verified?'<span class="pill ok">verificada</span>':`<button class="mini sec" onclick="api('/positions/${p.ticker}/verify',{method:'POST'}).then(cartera)">Confirmar datos</button>`}
          <button class="mini danger" onclick="if(confirm('¿Eliminar ${p.ticker}?'))api('/positions/${p.ticker}',{method:'DELETE'}).then(cartera)">✕</button>
        </div>
        <div class="asset-levels lv-box" id="lv-${esc(p.ticker)}"></div>
      </div>
    </details>`).join('')||'<p class="mut sm">Aún no tienes posiciones. Sincroniza con una foto de Hapi o agrégalas desde Herramientas avanzadas.</p>'}
  </div>
  <div class="card"><h3>Sincronizar con Hapi (foto)</h3>
    <p class="sm mut">Sube una captura de tus posiciones en la app de Hapi: el modelo de visión configurado
      extrae los datos, tú los revisas en una tabla editable y confirmas para sincronizar. Nada se guarda sin tu confirmación.</p>
    <div class="row">
      <input type="file" id="ph-file" accept="image/*" style="max-width:320px" onchange="photoPreviewName(this)">
      <button onclick="photoAnalyze()">Analizar captura</button>
      <span id="ph-status" class="sm mut"></span>
    </div>
    <div id="ph-map"></div>
  </div>
  <div class="card"><div class="row">
    <button class="sec" onclick="refreshPrices().then(cartera)">Actualizar precios (Yahoo Finance)</button>
    <span class="sm mut">Efectivo disponible (USD): $</span><input id="cash" style="width:110px" value="${pf.cash??''}">
    <button class="mini" onclick="if($('#cash').value===''){alert('Ingresa el efectivo en USD antes de guardarlo.');return}api('/cash',{method:'PUT',body:{amount:+$('#cash').value}}).then(cartera)">Guardar</button></div>
  </div>
  <details class="card"><summary>Herramientas avanzadas</summary>
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
  <div class="card"><h3>Validación de datos</h3>
  ${val.report.map(r=>`<details><summary>${r.ticker} ${r.inconsistencias.length?`<span class="pill err">${r.inconsistencias.length} inconsistencia(s)</span>`:'<span class="pill ok">coherente</span>'}</summary>
    ${r.inconsistencias.map(x=>`<div class="alert riesgo_elevado">⚠️ ${esc(x)}</div>`).join('')}
    <p class="sm"><b>Confirmados:</b></p><ul class="sm">${r.confirmados.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
    <p class="sm"><b>Calculados:</b></p><ul class="sm">${r.calculados.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
    <p class="sm"><b>Pendientes de verificación:</b></p><ul class="sm">${r.pendientes.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>
  </details>`).join('')||'<p class="mut sm">Sin posiciones que validar.</p>'}</div></details>${DISC}`;
  _currentTickers = pf.positions.map(p=>p.ticker);
  document.querySelectorAll('details.asset-row').forEach(d=>d.addEventListener('toggle', ()=>{
    if(d.open && !d.dataset.levelsLoaded){ d.dataset.levelsLoaded = '1'; loadLevels(d.dataset.tk); }
  }));
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
  const invCell=(x,i)=>{
    const empty = x.invested==null || x.invested==='';
    const derived = empty && x.hapi_value!=null && x.hapi_pl!=null
      ? Math.round((x.hapi_value - x.hapi_pl)*100)/100 : x.invested;
    return num(i+'-inv', derived) + (empty && derived!=null && derived!==''
      ? '<br><span class="sm mut">calculado: valor − P/L</span>' : '');
  };
  $('#ph-map').innerHTML = `
   <p class="sm" style="margin-top:10px">Detectado con <b>${esc(r.model)}</b>. Revisa cada dato contra tu app de Hapi y corrige lo que haga falta
     (los campos vacíos son datos que la IA no vio; no se inventan):</p>
   <table><tr><th>Ticker</th><th>Cantidad</th><th>Costo prom.</th><th>Invertido</th><th>Valor</th><th>P/L</th><th>P/L %</th></tr>
   ${r.rows.map((x,i)=>`<tr><td><b>${esc(x.ticker)}</b><br><span class="sm mut">${esc(x.name||'')}</span></td>
     <td>${num(i+'-qty',x.qty)}</td><td>${num(i+'-avg',x.avg_cost)}</td><td>${invCell(x,i)}</td>
     <td>${num(i+'-val',x.hapi_value)}</td><td>${num(i+'-pl',x.hapi_pl)}</td><td>${num(i+'-plp',x.hapi_return_pct)}</td></tr>`).join('')}
   </table>
   ${r.omitted.length?`<p class="sm mut">${r.omitted.length} fila(s) descartada(s) por datos incompletos: ${esc(JSON.stringify(r.omitted))}</p>`:''}
   <label class="review-check"><input id="ph-confirm" type="checkbox">Revisé cada dato contra Hapi.</label>
   <label class="review-check"><input id="ph-replace" type="checkbox">Esta captura muestra toda mi cartera: quitar las posiciones que no aparecen.</label>
   <div class="row" style="margin-top:8px">
     <label style="margin:0">Efectivo / poder de compra (USD)</label>
     <input id="ph-cash" type="number" step="any" style="width:120px" value="${r.cash??''}">
     <button onclick="photoSave(${r.rows.length})">Sincronizar ${r.rows.length} posición(es)</button>
     <span id="ph-save-status" class="sm mut" role="status"></span>
     <span class="sm mut">Con tu confirmación quedan verificadas; la captura queda como fuente.</span>
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
  if(!$('#ph-confirm')?.checked){
    $('#ph-save-status').textContent = 'Marca «Revisé cada dato contra Hapi» para guardar la sincronización.';
    return;
  }
  const replace = !!$('#ph-replace')?.checked;
  if(replace){
    const keep = new Set(rows.map(r2=>String(r2.ticker||'').toUpperCase()));
    const remove = _currentTickers.filter(t=>!keep.has(t));
    if(!confirm(remove.length
      ? `Se quitarán de tu cartera: ${remove.join(', ')}.\n¿Continuar con la sincronización?`
      : 'La captura cubre todas tus posiciones; no se quitará ninguna. ¿Continuar?')) return;
  }
  const cashEl = $('#ph-cash');
  const body = {rows, confirmed:true, replace_all:replace};
  if(cashEl && cashEl.value!=='') body.cash = +cashEl.value;
  try{
    const r = await api('/hapi/photo/save',{method:'POST',body});
    alert(r.detail + (r.omitidas.length?`\n\nOmitidas ${r.omitidas.length} fila(s).`:'')
      + (r.eliminadas && r.eliminadas.length?`\nQuitadas de tu cartera: ${r.eliminadas.join(', ')}`:''));
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

/* ---------- 3. ¿Compro o vendo? (evaluación de una operación concreta) ---------- */
let _tcCtx = null, _tcLast = null, _lunaOpinion = null;
async function analisis(arg){
  const [pf, cands] = await Promise.all([api('/portfolio'), api('/candidates')]);
  const tk = (arg||'').trim().toUpperCase();
  const tickers = [...new Set([...pf.positions.map(p=>p.ticker),
    ...(cands.candidates||[]).map(c=>c.ticker)])];
  _tcCtx = {positions: pf.positions, cash: pf.cash};
  _tcLast = null; _lunaOpinion = null;
  $('#view').innerHTML = `
  <h2>¿Compro o vendo?</h2>
  <p class="sub">Escribe la operación que estás pensando hacer en Hapi. Ves cómo queda tu cartera,
    qué dicen tus límites y el motor, y Luna te da una segunda opinión.</p>
  <div class="card"><div class="grid g3">
    <div><label for="tc-tk">Ticker</label>
      <input id="tc-tk" list="tc-tickers" value="${esc(tk)}" style="text-transform:uppercase">
      <datalist id="tc-tickers">${tickers.map(t=>`<option value="${esc(t)}">`).join('')}</datalist></div>
    <div><label>Operación</label><div class="row">
      <label class="review-check"><input type="radio" name="tc-side" value="comprar" checked>Comprar</label>
      <label class="review-check"><input type="radio" name="tc-side" value="vender">Vender</label></div></div>
    <div><label for="tc-amt">Monto USD</label><input id="tc-amt" type="number" step="any" min="0"></div>
  </div>
  <div class="row sm" id="tc-shortcuts" style="margin-top:6px"></div>
  <div class="row" style="margin-top:8px">
    <button id="tc-go" type="button" onclick="tradeCheck()">Evaluar operación</button>
    <span id="tc-status" class="sm mut" role="status"></span></div>
  </div>
  <div id="tc-out"></div>${DISC}`;
  tcShortcuts();
  $('#tc-tk').addEventListener('input', tcShortcuts);
  document.querySelectorAll('input[name=tc-side]').forEach(r=>r.addEventListener('change', tcShortcuts));
}
function tcSetAmt(v){ const el=$('#tc-amt'); if(el) el.value=v; }
function tcShortcuts(){
  if(!_tcCtx) return;
  const tk = $('#tc-tk')?.value.trim().toUpperCase()||'';
  const pos = _tcCtx.positions.find(p=>p.ticker===tk);
  const vr = document.querySelector('input[name=tc-side][value=vender]');
  if(vr){
    vr.disabled = !pos;
    if(!pos && vr.checked) document.querySelector('input[name=tc-side][value=comprar]').checked = true;
  }
  const side = document.querySelector('input[name=tc-side]:checked')?.value||'comprar';
  let html = [50,100,200].map(v=>`<button type="button" class="mini sec" onclick="tcSetAmt(${v})">$ ${v}</button>`).join('');
  if(side==='comprar' && _tcCtx.cash>=1)
    html += `<button type="button" class="mini sec" onclick="tcSetAmt(${_tcCtx.cash})">Todo mi efectivo ($ ${fmt(_tcCtx.cash)})</button>`;
  if(side==='vender' && pos && pos.market_value!=null)
    html += `<button type="button" class="mini sec" onclick="tcSetAmt(${pos.market_value})">Toda la posición ($ ${fmt(pos.market_value)})</button>`;
  const box = $('#tc-shortcuts'); if(box) box.innerHTML = html;
}
async function tradeCheck(assumptions){
  const tk = ($('#tc-tk').value||'').trim().toUpperCase();
  const side = document.querySelector('input[name=tc-side]:checked').value;
  const amount = +$('#tc-amt').value;
  const btn = $('#tc-go'), out = $('#tc-out');
  if(!tk || !(amount>0)){ $('#tc-status').textContent='Escribe el ticker y un monto mayor a cero.'; return; }
  btn.disabled = true; btn.textContent = 'Evaluando…'; $('#tc-status').textContent = '';
  _lunaOpinion = null;
  out.innerHTML = '<p class="mut">Evaluando la operación con precios de mercado…</p>';
  try{
    const r = await api('/trade_check',{method:'POST',body:{ticker:tk, side,
      amount_usd:amount, assumptions:assumptions||null}});
    _tcLast = r;
    renderTradeCheck(r);
  }catch(e){
    out.innerHTML = `<div class="alert riesgo_elevado">${esc(reviewError(e,'No se pudo evaluar la operación.'))}</div>`;
  }finally{ btn.disabled = false; btn.textContent = 'Evaluar operación'; }
}
function renderTradeCheck(r){
  const pct = v => v==null?'—':fmt(v,2)+' %';
  const limVal = l => l.valor==null?'—':(l.limite==='Reserva mínima de efectivo'?'$ '+fmt(l.valor):pct(l.valor));
  const limMax = l => l.limite==='Reserva mínima de efectivo'?'$ '+fmt(l.maximo):pct(l.maximo);
  $('#tc-out').innerHTML = `
  <div class="card"><h3>${r.operacion==='comprar'?'Comprar':'Vender'} $ ${fmt(r.monto_usd)} de ${esc(r.ticker)}</h3>
    <p class="sm">Precio: <b>$ ${fmt(r.precio.valor)}</b> <span class="mut">${esc(r.precio.fuente||'')} · ${esc(r.precio.asof||'')}</span>
      · ≈ ${fmt(r.acciones_aprox,6)} acciones (fraccionadas)</p>
    <div class="grid g2">
      <div class="qbox"><b>Peso de ${esc(r.ticker)}</b><br>${pct(r.peso_antes_pct)} → ${pct(r.peso_despues_pct)}</div>
      <div class="qbox"><b>Efectivo</b><br>$ ${fmt(r.efectivo_antes)} → $ ${fmt(r.efectivo_despues)}
        ${r.deposito_necesario>0?`<br><span class="sm mut">tras depositar $ ${fmt(r.deposito_necesario)}</span>`:''}</div>
    </div>
    ${r.deposito_necesario>0?`<div class="alert riesgo_elevado">Te faltan $ ${fmt(r.deposito_necesario)} de efectivo: deposita en Hapi o reduce el monto.</div>`:''}
    <table><tr><th>Límite</th><th>Quedaría en</th><th>Tu máximo</th><th></th></tr>
      ${r.limites.map(l=>`<tr><td>${esc(l.limite)}</td><td>${limVal(l)}</td><td>${limMax(l)}</td>
        <td class="${l.cumple?'pos':'neg'}">${l.cumple?'✓':'✗'}</td></tr>`).join('')}</table>
    <p class="sm" style="margin-top:8px">El motor propone:
      <span class="pill">${esc(r.motor.propuesta.replaceAll('_',' '))}</span>
      <span class="pill ${r.motor.confianza==='baja'?'warn':'ok'}">confianza ${esc(r.motor.confianza)}</span></p>
    <ul class="sm">${r.motor.argumentos.map(a=>`<li>${esc(a)}</li>`).join('')}</ul>
    ${r.fundamentales_nota?`<p class="sm mut">Fundamentales: ${esc(r.fundamentales_nota)}</p>`:''}
    <p class="sm mut">${esc(r.nota)}</p>
    <div class="row">
      <button class="sec" type="button" onclick="lunaOpinion(${r.decision_id})">Segunda opinión de Luna</button>
      <button class="sec" type="button" onclick="tradeJournalForm(${r.decision_id})">Guardar en mi diario</button>
    </div>
    <p class="sm mut">Luna opina sobre esta evaluación; no decide ni opera por ti. La consulta al proveedor de IA puede generar costo.</p>
    <div id="luna-op"></div>
    <div id="tc-journal"></div>
  </div>
  <div class="card"><h3>Niveles de referencia</h3>
    ${nivelesHtml(r.niveles, null)}
    <p class="sm">Mercado hoy: ${r.mercado_hoy?`<span class="pill ${SEMAFORO_MKT[r.mercado_hoy.semaforo]||'mut'}">${esc((r.mercado_hoy.semaforo||'—').replaceAll('_',' '))}</span>
      ${r.mercado_hoy.tipo_dia?` · día ${esc(r.mercado_hoy.tipo_dia)}`:''}<span class="mut"> — ${esc(r.mercado_hoy.lectura||'')}</span>`:'<span class="mut">sin datos de mercado ahora</span>'}</p>
  </div>
  <details class="card"><summary>Ver análisis completo</summary>
    <div class="row sm" style="margin:8px 0">
      <span class="sm mut">Supuestos DCF:</span>
      <label class="sm" style="margin:0">crec. 1-5a %</label><input id="as-g" style="width:70px" value="15">
      <label class="sm" style="margin:0">descuento %</label><input id="as-r" style="width:70px" value="10">
      <label class="sm" style="margin:0">terminal %</label><input id="as-t" style="width:70px" value="2.5">
      <button class="mini sec" type="button"
        onclick="tradeCheck({growth_1_5_pct:+$('#as-g').value,discount_rate_pct:+$('#as-r').value,terminal_growth_pct:+$('#as-t').value})">Recalcular</button>
      <button class="mini sec" type="button" onclick="fundForm('${esc(r.ticker)}')">Fundamentales…</button>
    </div>
    <div id="an-out"></div>
  </details>`;
  renderAnalysis(r.analisis);
}
async function lunaOpinion(did){
  const out = $('#luna-op');
  if(!out) return;
  out.textContent = 'Consultando a Luna…';
  try{
    const r = await api(`/trade_check/${did}/luna`,{method:'POST'});
    if($('#luna-op')!==out) return;
    _lunaOpinion = r;
    out.replaceChildren();
    const box = document.createElement('div'); box.className = 'review-step';
    const h = document.createElement('h4'); h.textContent = 'Segunda opinión de Luna'; box.appendChild(h);
    const p = document.createElement('p'); p.className = 'sm'; p.textContent = r.resumen; box.appendChild(p);
    const mk = (title,items)=>{
      const s = document.createElement('div'); s.className = 'sm';
      const b = document.createElement('b'); b.textContent = title; s.appendChild(b);
      const ul = document.createElement('ul');
      items.forEach(t=>{ const li = document.createElement('li'); li.textContent = t; ul.appendChild(li); });
      s.appendChild(ul); return s;
    };
    box.appendChild(mk('A favor', r.a_favor));
    box.appendChild(mk('En contra', r.en_contra));
    box.appendChild(mk('Qué vigilar', r.vigilar));
    const meta = document.createElement('p'); meta.className = 'sm mut';
    meta.textContent = `Modelo: ${r.model}. Opinión sobre los datos ya evaluados; no es una orden.`; box.appendChild(meta);
    out.appendChild(box);
  }catch(e){ if($('#luna-op')===out) out.textContent = reviewError(e,'No se pudo obtener la opinión de Luna.'); }
}
function tradeJournalForm(did){
  const r = _tcLast, j = $('#tc-journal');
  if(!r || !j) return;
  const pos = (_tcCtx?.positions||[]).find(p=>p.ticker===r.ticker);
  let action, choice;
  if(r.operacion==='comprar'){
    action = pos ? 'agregar' : 'comprar';
    choice = pos ? 'agregar_gradualmente' : 'comprar';
  }else{
    const full = pos && r.monto_usd >= (pos.market_value||0) - 0.01;
    action = full ? 'vender' : 'reducir';
    choice = full ? 'vender' : 'reducir';
  }
  const rev = new Date(Date.now()+90*864e5).toISOString().slice(0,10);
  // Textos prellenados solo con cifras del resultado (editables; nada se inventa).
  const n = r.niveles, mh = r.mercado_hoy;
  let tesis = `${r.operacion==='comprar'?'Comprar':'Vender'} $${fmt(r.monto_usd)} de ${r.ticker} a $${fmt(r.precio.valor)} (${(r.fecha||'').slice(0,10)}). `
    + `Motor: ${r.motor.propuesta.replaceAll('_',' ')} (confianza ${r.motor.confianza}).`;
  if(mh && mh.semaforo && mh.semaforo!=='sin_datos') tesis += ` Mercado: ${mh.semaforo.replaceAll('_',' ')}${mh.tipo_dia?`, día ${mh.tipo_dia}`:''}.`;
  if(n) tesis += ` Semáforo de la acción: ${n.semaforo}.`;
  const limVal = l => l.valor==null?'—':(l.limite==='Reserva mínima de efectivo'?'$'+fmt(l.valor):fmt(l.valor,1)+'%');
  const limMax = l => l.limite==='Reserva mínima de efectivo'?'$'+fmt(l.maximo):fmt(l.maximo,1)+'%';
  const fallan = (r.limites||[]).filter(l=>!l.cumple);
  let riesgos = (_lunaOpinion?.en_contra||[]).join('; ');
  if(!riesgos){
    const partes = [];
    if(fallan.length) partes.push('Incumple: '+fallan.map(l=>`${l.limite} (${limVal(l)} ${l.limite==='Reserva mínima de efectivo'?'<':'>'} ${limMax(l)})`).join('; '));
    if(r.tecnica?.volatilidad_anualizada_pct!=null) partes.push(`Volatilidad anual ${fmt(r.tecnica.volatilidad_anualizada_pct,1)}%`);
    riesgos = partes.join('. ');
  }
  const inval = n ? `Cierre diario por debajo de $${fmt(n.stop_loss)} (stop sugerido, ${pctS(n.stop_loss_pct).replace(' ','')}) o cambio en la tesis.`
                  : 'Cambio en la tesis o incumplimiento de mis límites.';
  j.innerHTML = `<div class="review-step"><h4>Guardar en mi diario</h4>
    <p class="sm mut">Textos prellenados con las cifras de esta evaluación; edítalos antes de registrar.</p>
    <div class="grid g2">
      <div><label for="tj-tesis">Tesis *</label><textarea id="tj-tesis" placeholder="¿Por qué haces esta operación?">${esc(tesis)}</textarea></div>
      <div><label for="tj-riesgos">Riesgos *</label><textarea id="tj-riesgos" placeholder="¿Qué puede salir mal?">${esc(riesgos)}</textarea></div>
      <div><label for="tj-inv">Condición de invalidación *</label><textarea id="tj-inv" placeholder="¿Qué tendría que pasar para que cambies de opinión?">${esc(inval)}</textarea></div>
      <div><label for="tj-rev">Revisar el</label><input id="tj-rev" type="date" value="${rev}">
        <label for="tj-precio">Precio</label><input id="tj-precio" type="number" step="any" value="${r.precio.valor}"></div>
    </div>
    <p class="sm mut">Se registrará como «${esc(action)}». La ejecución la haces tú en Hapi.</p>
    <button type="button" id="tj-save" onclick="saveTradeJournal(${did},'${action}','${choice}')">Registrar en el diario</button>
    <span id="tj-status" class="sm mut" role="status"></span></div>`;
}
async function saveTradeJournal(did, action, choice){
  const st = $('#tj-status'), btn = $('#tj-save');
  if(!st) return;
  if(btn) btn.disabled = true;
  const p = $('#tj-precio').value;
  try{
    await api('/journal',{method:'POST',body:{ticker:_tcLast.ticker, action,
      tesis:$('#tj-tesis').value, riesgos:$('#tj-riesgos').value,
      condicion_invalidacion:$('#tj-inv').value,
      precio:p===''?null:+p, review_date:$('#tj-rev').value}});
    await api(`/decisions/${did}/record`,{method:'POST',body:{choice, authorized:true}});
    st.textContent = 'Guardado en tu diario. Si decides operar, hazlo en Hapi y luego sincroniza tu cartera con una foto.';
  }catch(e){ st.textContent = reviewError(e,'No se pudo guardar.'); if(btn) btn.disabled = false; }
}
function renderAnalysis(r){
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
  <div class="row"><button class="sec" type="button" onclick="secFund('${esc(tk)}')">Cargar desde la SEC (10-K oficial)</button>
    <span id="sec-status" class="sm mut" role="status"></span></div>
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
async function secFund(tk){
  const st = $('#sec-status');
  if(st) st.textContent = 'Descargando el 10-K de la SEC…';
  let r;
  try{
    try{
      r = await api(`/fundamentals/${encodeURIComponent(tk)}/sec`,{method:'POST',body:{}});
    }catch(e){
      if(e._status===409 && confirm(e.detail+'\n\n¿Reemplazar los datos actuales por los del 10-K?'))
        r = await api(`/fundamentals/${encodeURIComponent(tk)}/sec`,{method:'POST',body:{replace_existing:true}});
      else throw e;
    }
  }catch(e){
    if(st) st.textContent = reviewError(e,'No se pudieron cargar los fundamentales de la SEC.');
    return;
  }
  await fundForm(tk);
  alert('Fundamentales cargados desde la SEC.\nFuente: '+r.source
    +'\nCampos faltantes: '+((r.missing||[]).join(', ')||'ninguno'));
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
    alert('Guardado.');
    if($('#tc-go')) tradeCheck(); else analisis(tk);
  }catch(e){ alert(e.detail||'Error'); }
}

/* ---------- 4. Oportunidades (radar) ---------- */
const RD_LABELS = {barata_y_buena:'Barata y buena',precio_justo:'Precio justo',
  buena_pero_cara:'Buena pero cara',cuidado:'Cuidado',faltan_datos:'Faltan datos'};
const RD_PILL = {barata_y_buena:'ok',precio_justo:'',buena_pero_cara:'warn',cuidado:'warn',faltan_datos:'mut'};
let _rdMsg = '', _rdErrs = [];

async function oportunidades(){
  const [r, cands] = await Promise.all([api('/radar'), api('/candidates')]);
  const notas = (cands.candidates||[]).filter(c=>Object.keys(c.data||{}).length||c.source!=='radar');
  $('#view').innerHTML = `
  <h2>Radar de oportunidades</h2>
  <p class="sub">El sistema puntúa ${r.universo} empresas grandes + las que agregues + tu cartera,
    con precio real y datos del 10-K de la SEC. Tú decides.</p>
  <div class="card"><div class="row">
    <div style="width:170px"><input id="rd-tk" placeholder="Ticker (p. ej. KO)" style="text-transform:uppercase"></div>
    <button type="button" onclick="rdAdd()">Agregar a mi radar</button>
    <button type="button" class="sec" onclick="rdRefresh()">Buscar oportunidades ahora</button>
    </div>
    <p id="rd-status" class="sm mut" role="status" style="margin-top:8px">${esc(_rdMsg)}</p>
    ${_rdErrs.map(e=>`<p class="sm mut" style="margin:2px 0">${esc(e.ticker)}: ${esc(e.error)}</p>`).join('')}
  </div>
  <div class="card"><table><tr><th>Ticker</th><th>Precio</th><th>Calidad</th><th>Margen seg.</th><th>P/E</th><th>Crec. ing.</th><th>Veredicto</th><th></th></tr>
    ${r.items.map(it=>{
      const falta = it.veredicto==='faltan_datos'
        ? [!it.fund&&'sin 10-K en la SEC', !it.price&&'sin precio'].filter(Boolean).join(' · ') : '';
      return `<tr style="cursor:pointer" onclick="location.hash='#analisis/${it.ticker}'">
      <td><b>${esc(it.ticker)}</b>
        ${it.en_cartera?'<span class="pill mut" style="font-size:11px;padding:1px 8px">en cartera</span>':''}
        ${it.en_watchlist?'<span class="pill mut" style="font-size:11px;padding:1px 8px">mi radar</span>':''}<br>
        <span class="sm mut">${esc(it.sector)}</span></td>
      <td>${it.price?`$ ${fmt(it.price.price)}<br><span class="sm mut">${esc(it.price.asof||'')} · ${esc(it.price.status)}</span>`:'—'}</td>
      <td>${it.calidad==null?'—':fmt(it.calidad,1)+'/10'}</td>
      <td>${it.mos==null?'—':fmt(it.mos,1)+' %'}</td>
      <td>${it.pe==null?'—':fmt(it.pe,1)}</td>
      <td>${it.crec==null?'—':fmt(it.crec,1)+' %'}</td>
      <td><span class="pill ${RD_PILL[it.veredicto]||''}" title="${esc((it.motivos||[]).join(' · '))}">${RD_LABELS[it.veredicto]||esc(it.veredicto)}</span>
        ${falta?`<br><span class="sm mut">${esc(falta)}</span>`:''}
        ${(it.motivos||[]).length?`<br><span class="sm mut">${esc(it.motivos.join(' · '))}</span>`:''}</td>
      <td>${it.en_watchlist?`<button class="mini danger" onclick="event.stopPropagation();rdQuitar(${it.candidate_id})">Quitar</button> `:''}
        <a class="mini" href="#analisis/${it.ticker}" onclick="event.stopPropagation()">Ver</a></td>
      </tr>`;}).join('')}
    </table>
    <p class="sm mut">${esc(r.nota)}</p></div>
  <details class="card"><summary>Mis candidatos con notas propias (${notas.length})</summary>
    <p class="sm mut">Candidatos que registraste con tus propias puntuaciones, tesis y fuente.</p>
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
    <button style="margin-top:10px" onclick="addCand()">Agregar candidato</button>
    ${notas.length?`<table style="margin-top:14px"><tr><th>#</th><th>Ticker</th><th>Puntaje</th><th>Tesis</th><th>Condiciones</th><th>Fuente</th><th></th></tr>
    ${notas.map((c,i)=>`<tr><td>${i+1}</td><td><b>${esc(c.ticker)}</b><br><span class="sm mut">${esc(c.name||'')}</span></td>
      <td><b>${c.ranking_score??'—'}</b></td>
      <td class="sm">${esc(c.data.tesis||'')}</td>
      <td class="sm">entrada: ${esc(c.data.condicion_entrada||'—')}<br>invalida: ${esc(c.data.condicion_invalidacion||'—')}</td>
      <td class="sm mut">${esc(c.source)}</td>
      <td><button class="mini danger" onclick="delCand(${c.id})">✕</button></td></tr>`).join('')}
    </table>`:'<p class="sm mut" style="margin-top:12px">Todavía no tienes candidatos con notas propias.</p>'}
  </details>${DISC}`;
  _rdMsg = ''; _rdErrs = [];
}
async function rdAdd(){
  const tk = ($('#rd-tk').value||'').trim().toUpperCase();
  const st = $('#rd-status');
  if(!tk){ st.textContent = 'Escribe un ticker.'; return; }
  st.textContent = `Agregando ${tk}: descargando su precio y su 10-K…`;
  try{
    const r = await api('/radar/'+encodeURIComponent(tk),{method:'POST'});
    _rdErrs = r.errores||[];
    _rdMsg = _rdErrs.length ? `${tk} agregado con avisos:` : `${tk} agregado a tu radar.`;
    oportunidades();
  }catch(e){ st.textContent = e.detail||'No se pudo agregar el ticker.'; }
}
async function rdRefresh(){
  const st = $('#rd-status');
  st.textContent = 'Descargando precios y 10-K… la primera vez puede tardar unos minutos';
  try{
    const r = await api('/radar/refresh',{method:'POST'});
    _rdErrs = r.errores||[];
    _rdMsg = `${r.precios} precios · ${r.fundamentales_nuevos} 10-K nuevos · ${r.errores.length} errores`;
    oportunidades();
  }catch(e){ st.textContent = e.detail||'No se pudo actualizar el radar.'; }
}
async function rdQuitar(id){ await api('/candidates/'+id,{method:'DELETE'}); oportunidades(); }
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

/* ---------- 8. Diario ---------- */
async function diario(){
  const [r, d] = await Promise.all([api('/journal'), api('/decisions')]);
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
      <div><label>Tesis *</label><textarea id="j-tesis"></textarea></div>
      <div><label>Riesgos *</label><textarea id="j-riesgos"></textarea></div>
      <div><label>Condición de invalidación *</label><textarea id="j-inv"></textarea></div>
      <div><label>Precio</label><input id="j-precio" type="number" step="any"></div>
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
  </div>`).join('')}
  <div class="card"><h3>Historial de decisiones (${d.decisions.length})</h3>
    <table><tr><th>Fecha</th><th>Ticker</th><th>Propuesta</th><th>Tu decisión</th><th>Contexto</th></tr>
    ${d.decisions.map(x=>`<tr><td class="sm">${x.created_at.slice(0,16).replace('T',' ')}</td><td><b>${x.ticker}</b></td>
      <td><span class="pill">${esc(x.proposal.decision)}</span> <span class="sm mut">conf. ${esc(x.proposal.confianza)}</span></td>
      <td>${x.user_choice?`<b>${esc(x.user_choice)}</b>`:'<span class="mut sm">sin registrar</span>'}</td>
      <td class="sm mut">peso ${fmt(x.proposal.peso,1)}% · margen ${x.proposal.margen_seguridad==null?'s/d':fmt(x.proposal.margen_seguridad,1)+'%'}
        ${x.proposal.argumentos?.length?`<br><button class="mini sec" type="button" onclick="explainDecision(${x.id})">Explicar con Luna</button>
          <div id="explain-${x.id}" class="assistant-answer sm" role="status"></div>`:
          '<br>Propuesta antigua: no se guardaron los argumentos para explicarla.'}</td></tr>`).join('')}</table></div>${DISC}`;
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
      tesis:$('#j-tesis').value,riesgos:$('#j-riesgos').value,
      condicion_invalidacion:$('#j-inv').value,precio:$('#j-precio').value?+$('#j-precio').value:null,
      review_date:$('#j-rev').value}});
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

/* ---------- 10. Ajustes (perfil, límites, datos) ---------- */
const PROFILE_LABELS = {horizonte_anios:'Horizonte de inversión (años)',objetivo:'Objetivo financiero',
  perdida_maxima_pct:'Pérdida máxima tolerable %',nivel_riesgo:'Nivel de riesgo'};
function profileFormHtml(r){
  return `<div class="grid g2">${r.fields.map(f=> f==='nivel_riesgo'
    ? `<div><label>${PROFILE_LABELS[f]}</label><select id="rp-${f}">${['','conservador','moderado','agresivo'].map(v=>`<option value="${v}" ${v===(r.profile[f]??'')?'selected':''}>${v||'Elige…'}</option>`).join('')}</select></div>`
    : `<div><label>${PROFILE_LABELS[f]||f}</label><input id="rp-${f}" value="${esc(r.profile[f]??'')}"></div>`).join('')}
  </div><button style="margin-top:12px" onclick="saveProfile()">Guardar perfil</button>`;
}
async function saveProfile(){
  const body = {}; (window._rpFields||[]).forEach(f=>{ const el=$('#rp-'+f); if(el) body[f]=el.value; });
  await api('/profile',{method:'PUT',body});
  route();
}

/* ---------- 11. Configuración (límites de riesgo) ---------- */
const LIMIT_LABELS = {max_position_pct:'Máximo % por empresa',max_sector_pct:'Máximo % por sector',
  max_trade_pct:'Máximo % por operación',max_tolerable_loss_pct:'Pérdida máxima tolerable %',
  min_cash_reserve:'Reserva mínima de efectivo (USD)',max_trades_per_month:'Máx. operaciones al mes'};
async function ajustes(){
  const [s, prof, pf] = await Promise.all([api('/settings'), api('/profile'), api('/portfolio')]);
  const n = pf.positions.length;
  const limitWarn = n && s.limits.max_position_pct < 100/n
    ? `<div class="alert">Con ${n} posiciones, cada una pesa en promedio ${fmt(100/n,0)} %. Si tu máximo por empresa es menor, verás alertas permanentes y el motor propondrá reducir.</div>` : '';
  $('#view').innerHTML = `
  <h2>Ajustes</h2><p class="sub">Tu perfil y las reglas de riesgo que alimentan alertas y el motor de decisiones.</p>
  <div class="card"><h3>Perfil de riesgo</h3>
    <p class="sm mut">${prof.complete?'Perfil completo: las recomendaciones pueden personalizarse.':'Perfil incompleto: los análisis serán informativos, no recomendaciones personalizadas.'}</p>
    ${profileFormHtml(prof)}</div>
  <div class="card"><h3>Límites de riesgo</h3>
    ${limitWarn}
    <div class="grid g3">
    ${Object.entries(s.limits).map(([k,v])=>`<div><label>${LIMIT_LABELS[k]||k}</label><input id="lm-${k}" type="number" step="any" value="${v}"></div>`).join('')}
  </div><button style="margin-top:12px" onclick="saveLimits(${JSON.stringify(Object.keys(s.limits)).replaceAll('"',"'")})">Guardar límites</button></div>
  <div class="card"><h3 style="color:var(--err)">Zona de peligro</h3>
    <p class="sm">Elimina posiciones, fundamentales, operaciones, diario, decisiones y candidatos.</p>
    <button class="danger" onclick="wipe()">Eliminar todos mis datos</button></div>${DISC}`;
  window._rpFields = prof.fields;
}
async function saveLimits(keys){
  const body={}; keys.forEach(k=>{ body[k]=+$('#lm-'+k).value; });
  await api('/limits',{method:'PUT',body}); alert('Límites guardados'); ajustes();
}
async function wipe(){
  if(prompt('Irreversible. Escribe ELIMINAR:')==='ELIMINAR'){
    await api('/settings/delete_all',{method:'POST',body:{confirm:'ELIMINAR'}}); alert('Datos eliminados'); route();
  }
}

route();
