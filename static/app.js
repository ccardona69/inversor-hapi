// Hapi IA - Inversion con criterio (Frontend SPA)
// Diseno: portado de Hapi-IA-frontend (sidebar, temas, dialogos) sobre el backend real.

(() => {
  "use strict";

  const icons = {
    grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    wallet:'<path d="M20 7V5a2 2 0 0 0-2-2H6a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3h14a1 1 0 0 0 1-1v-5"/><path d="M3 6a2 2 0 0 0 2 2h15a1 1 0 0 1 1 1v6h-5a3 3 0 0 1 0-6h5"/><path d="M16.5 12h.01"/>',
    compass:'<circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z"/>',
    sparkles:'<path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z"/><path d="M20 2v4M18 4h4"/>',
    activity:'<path d="M4 4h16M4 12h16M4 20h10"/><path d="m17 17 3 3-3 3"/>',
    book:'<path d="M12 5v16M3 4c4-1 7 0 9 1 2-1 5-2 9-1v15c-4-1-7 0-9 2-2-2-5-3-9-2V4Z"/>',
    moon:'<path d="M20.5 14A9 9 0 0 1 10 3.5 9 9 0 1 0 20.5 14Z"/>',
    sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2m-17-7 1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
    help:'<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4.7 1.3c-.7 1-2.2 1.2-2.2 2.7M12 16h.01"/>',
    x:'<path d="m6 6 12 12M18 6 6 18"/>',
    menu:'<path d="M4 6h16M4 12h16M4 18h16"/>',
    search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    chevron:'<path d="m9 5 7 7-7 7"/>',
    chevdown:'<path d="m6 9 6 6-6-6"/>',
    arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
    arrowup:'<path d="M7 17 17 7M7 7h10v10"/>',
    arrowdown:'<path d="M17 7 7 17M7 17h10V7"/>',
    external:'<path d="M7 17 17 7M7 7h10v10"/>',
    download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    eye:'<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
    eyeoff:'<path d="m3 3 18 18M10.6 5.1 12 5c6.5 0 10 7 10 7a20 20 0 0 1-3.3 4.2M6.3 6.3A20 20 0 0 0 2 12s3.5 7 10 7c1.8 0 3.5-.6 5-1.4M10 10a3 3 0 0 0 4 4"/>',
    star:'<path d="m12 3 2.8 5.7 6.3.9-4.6 4.4 1.1 6.3-5.6 3-5.6 3 1.1-6.3L2.9 9.6l6.3-.9L12 3Z"/>',
    check:'<path d="m5 12 4 4L19 6"/>',
    shield:'<path d="m12 3 8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6l8-3Z"/><path d="m8 12 3 3 5-6"/>',
    send:'<path d="m21 3-6 18-4-8-8-4 18-6ZM11 13 21 3"/>',
    plus:'<path d="M12 5v14M5 12h14"/>',
    trend:'<path d="m3 17 6-6 4 4 8-10M15 5h6v6"/>',
    lock:'<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    sliders:'<path d="M10 5H3"/><path d="M12 19H3"/><path d="M14 3v4"/><path d="M16 17v4"/><path d="M21 12h-9"/><path d="M21 19h-5"/><path d="M21 5h-7"/><path d="M8 10v4"/>',
    settings:'<path d="M14 17H5"/><path d="M19 7h-9"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
    camera:'<path d="M14 5a2 2 0 0 1 1.76 1.05l.49.9A2 2 0 0 0 18 8h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h2a2 2 0 0 0 1.76-1.05l.49-.9A2 2 0 0 1 10 5z"/><circle cx="12" cy="13" r="3"/>',
    refresh:'<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    trash:'<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    alert:'<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
    clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'
  };
  const icon = (key, extra = "") => `<svg class="icon ${extra}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[key] || icons.info}</svg>`;
  const hydrateIcons = (root = document) => root.querySelectorAll("[data-icon]").forEach(el => { el.innerHTML = icon(el.dataset.icon); });
  const escapeHtml = value => String(value == null ? "" : value).replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
  const priceFormatter = new Intl.NumberFormat("en-US", {minimumFractionDigits:2, maximumFractionDigits:2});
  const money = value => `${value < 0 ? "−" : ""}$${priceFormatter.format(Math.abs(value))}`;
  const soles = value => `S/ ${priceFormatter.format(Math.abs(value))}`;
  const pct = value => `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)}%`;
  const round = value => Math.round(value * 100) / 100;

  // ---- Datos de demostracion (solo si no hay backend) ----
  const initialAssets = [
    {ticker:"VOO", name:"Vanguard S&P 500 ETF", shares:1.24, price:562.48, cost:584.20, color:"#276d5f", change:2.84, type:"ETF"},
    {ticker:"NVDA", name:"NVIDIA Corporation", shares:1.55, price:138.42, cost:186.12, color:"#70a67c", change:15.31, type:"Acción"},
    {ticker:"AAPL", name:"Apple Inc.", shares:0.46, price:240.75, cost:102.14, color:"#b7c5a9", change:7.81, type:"Acción"},
  ];
  const initialEntries = [
    {id:1, ticker:"VOO", action:"Comprar", amount:100, thesis:"Seguir construyendo una base diversificada a largo plazo.", risk:"Caída general del mercado.", invalidation:"Cambio en mi horizonte de inversión.", date:"18 jun 2025"},
    {id:2, ticker:"NVDA", action:"Mantener", amount:0, thesis:"La demanda de infraestructura de IA sostiene mi tesis.", risk:"Valuación exigente y concentración.", invalidation:"Desaceleración persistente de ingresos.", date:"12 jun 2025"},
  ];
  const radarUniverse = [
    {ticker:"VOO", name:"Vanguard S&P 500 ETF", sector:"ETF · Mercado amplio", verdict:"Precio justo", verdictKey:"precio_justo", tone:"green", note:"Una base diversificada para mirar a largo plazo.", price:"$562.48"},
    {ticker:"MSFT", name:"Microsoft Corporation", sector:"Tecnología · Software", verdict:"Buena pero cara", verdictKey:"buena_pero_cara", tone:"orange", note:"Negocio sólido; el precio merece una pausa.", price:"$478.04"},
    {ticker:"AAPL", name:"Apple Inc.", sector:"Tecnología · Consumo", verdict:"Precio justo", verdictKey:"precio_justo", tone:"green", note:"Calidad reconocida, con crecimiento por vigilar.", price:"$239.37"},
    {ticker:"NVDA", name:"NVIDIA Corporation", sector:"Tecnología · Chips", verdict:"Faltan datos", verdictKey:"faltan_datos", tone:"gray", note:"La tesis necesita actualizar supuestos.", price:"$138.42"},
  ];
  const PALETTE = ["#276d5f","#70a67c","#b7c5a9","#4d9062","#82bc90","#37674d","#5c8a6f","#a2b997"];
  const ETF_TICKERS = new Set(["VOO","SPY","QQQ","IVV","VTI","VT","DIA","IWM","GLD","TLT","USO","BND","SCHD","VIG","VXUS","VEA","VWO","AGG","LQD","ARKK"]);
  const VERDICT_LABELS = {barata_y_buena:"Barata y buena", precio_justo:"Precio justo", buena_pero_cara:"Buena pero cara", cuidado:"Cuidado", faltan_datos:"Faltan datos"};
  const VERDICT_TONES = {barata_y_buena:"green", precio_justo:"green", buena_pero_cara:"orange", cuidado:"orange", faltan_datos:"gray"};
  const FLOW_META = {
    deposito:{label:"Depósito", icon:"plus", sign:1},
    retiro:{label:"Retiro", icon:"arrowup", sign:-1},
    dividendo:{label:"Dividendo", icon:"star", sign:1},
    ahorro_soles:{label:"Ahorro en soles", icon:"wallet", sign:1},
    actividad:{label:"Actividad en Hapi", icon:"check", sign:0},
    w8ben:{label:"Formulario W-8BEN", icon:"shield", sign:0},
  };
  const FLOW_SOURCE = {texto:"contado por ti", captura:"desde captura", historial:"historial pegado"};

  // ---- Preferencias locales ----
  const storageKey = "inversor-hapi-prefs-v1";
  const readPreferences = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(storageKey) || "{}");
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch { return {}; }
  };
  const prefs = readPreferences();

  // ---- Estado ----
  const state = {
    theme: ["light","dark"].includes(prefs.theme) ? prefs.theme : (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
    private: prefs.private === true,
    watched: new Set(Array.isArray(prefs.watched) ? prefs.watched.filter(t => typeof t === "string") : []),
    route: "resumen",
    menuOpen: false,
    loading: true,
    connected: false,
    demoOverride: false,

    filter: "todos", query: "", sort: "name",
    walletTab: "posiciones",
    pendingPrompt: "",
    messages: [{role:"luna", text:"Hola, soy Luna. Estoy aquí para ayudarte a pensar con claridad sobre tu dinero.\n\nPuedo revisar tu cartera, tus números y tus decisiones. Nunca ejecuto operaciones ni invento cifras.\n\n¿Qué te gustaría revisar hoy?"}],
    lunaTyping: false,

    // Datos
    assets: JSON.parse(JSON.stringify(initialAssets)),
    entries: JSON.parse(JSON.stringify(initialEntries)),
    radar: JSON.parse(JSON.stringify(radarUniverse)),
    flows: [],
    savings: 1240,
    cash: 0,

    // Datos del servidor
    serverDashboard: null,
    serverMarcador: null,
    serverPulse: null,
    serverRisk: null,
    lastRef: "",

    // Resumen
    homeSavingText: "",
    homeDraft: null,
    homeReviewed: false,

    // Cartera
    portfolioSync: false,
    portfolioFileName: "",
    portfolioTicker: "",
    portfolioShares: "",
    portfolioPrice: "",
    portfolioChecked: false,
    portfolioReplace: false,
    portfolioConfirmReplace: false,

    // Análisis
    analysisTicker: "VOO",
    analysisSide: "Comprar",
    analysisAmount: "100",
    analysisShow: false,
    analysisThesis: "",
    analysisRisk: "",
    analysisInvalidation: "",

    // Movimientos
    flowText: "",
    flowDraft: null,
    flowReviewed: false,
    flowAllowDup: false,
    flowBusy: false,

    // Diario
    journalTicker: "",
    journalAction: "Comprar",
    journalThesis: "",
    journalRisk: "",
    journalInvalidation: "",
    journalReviewId: null,
    journalLesson: "",

    // Ajustes
    settingsRisk: "moderado",
    settingsLimit: "40",
    settingsPositions: "3",
    settingsSaved: false,
  };

  const savePreferences = () => {
    try { localStorage.setItem(storageKey, JSON.stringify({theme:state.theme, private:state.private, watched:[...state.watched]})); return true; } catch { return false; }
  };

  const main = document.getElementById("main-content");
  const dialog = document.getElementById("app-dialog");
  const dialogBody = document.getElementById("dialog-body");
  const sidebar = document.getElementById("sidebar");
  const mobileQuery = matchMedia("(max-width: 1000px)");
  let menuOpen = false;
  let toastTimer;

  function isDemoMode() {
    const params = new URLSearchParams(location.search);
    return state.demoOverride || params.get("mock") === "1" || params.get("demo") === "1" || location.protocol === "file:" || !state.connected;
  }

  // ---- Helpers de marcado ----
  const privateText = (text, classes = "") => `<span class="num ${classes}" data-private data-value="${escapeHtml(text)}">${escapeHtml(state.private ? "••••" : text)}</span>`;
  const badge = (text, tone = "") => `<span class="badge ${tone ? "badge-" + tone : "badge-muted"}">${text}</span>`;
  const routeLabels = {resumen:"Resumen", cartera:"Mi cartera", analisis:"¿Compro o vendo?", explorar:"Explorar", asistente:"Hapi IA", movimientos:"Movimientos", diario:"Mi diario", ajustes:"Ajustes"};
  const portfolio = () => state.assets.reduce((s,a) => s + a.shares * a.price, 0);
  const investedTotal = portfolio;
  const costBasis = () => state.assets.reduce((s,a) => s + a.cost, 0);
  const assetType = (ticker, sector = "") => (sector.startsWith("ETF") || ETF_TICKERS.has(ticker)) ? "ETF" : "Acción";
  const monoTone = (ticker, type) => type === "ETF" ? "purple" : (ticker.charCodeAt(0) % 3 === 1 ? "blue" : "");
  const monogram = (letter, tone = "") => `<span class="asset-monogram ${tone}" aria-hidden="true">${escapeHtml(letter)}</span>`;
  const assetLabel = (ticker, name, tone = "") => `<span class="asset">${monogram(ticker[0] || "?", tone)}<span><span class="asset-name">${escapeHtml(ticker)}</span><span class="asset-sub" style="display:block">${escapeHtml(name)}</span></span></span>`;
  const watchButton = ticker => `<button class="icon-btn watch-btn" data-action="watch" data-ticker="${escapeHtml(ticker)}" aria-pressed="${state.watched.has(ticker)}" aria-label="${state.watched.has(ticker) ? "Quitar" : "Añadir"} ${escapeHtml(ticker)} ${state.watched.has(ticker) ? "de" : "a"} seguimiento" title="Seguimiento">${icon("star")}</button>`;
  const footer = () => `<footer class="footer"><p>Hapi IA ayuda a pensar mejor; no decide por ti ni ejecuta operaciones. No es asesoría financiera.${state.serverVersion ? ` <span class="muted">· build ${escapeHtml(state.serverVersion.version || "sin dato")}</span>` : ""}</p><button data-action="about">Alcance y origen de datos ${icon("external","icon-sm")}</button></footer>`;
  const intro = (eyebrow, title, description, actions = "") => `<section class="page-intro"><div><p class="eyebrow">${eyebrow}</p><h1 id="page-title">${title}</h1><p class="description">${description}</p></div>${actions ? `<div class="intro-actions">${actions}</div>` : ""}</section>`;
  const advanced = (title, childrenHtml) => `<details class="advanced"><summary>${title} ${icon("chevdown")}</summary><div class="advanced-body">${childrenHtml}</div></details>`;

  // ---- Comunicación con FastAPI ----
  async function loadServerData() {
    try {
      const [dashRes, marcRes, pulseRes, radarRes, jourRes, setRes, profRes, flowsRes, verRes] = await Promise.all([
        fetch("/api/dashboard").catch(() => null),
        fetch("/api/marcador").catch(() => null),
        fetch("/api/market/pulse").catch(() => null),
        fetch("/api/radar").catch(() => null),
        fetch("/api/journal").catch(() => null),
        fetch("/api/settings").catch(() => null),
        fetch("/api/profile").catch(() => null),
        fetch("/api/flows").catch(() => null),
        fetch("/api/system/version").catch(() => null),
      ]);

      if (dashRes && dashRes.ok) {
        state.serverDashboard = await dashRes.json();
        state.connected = true;
      }
      if (marcRes && marcRes.ok) state.serverMarcador = await marcRes.json();
      if (pulseRes && pulseRes.ok) state.serverPulse = await pulseRes.json();
      if (radarRes && radarRes.ok) {
        const rData = await radarRes.json();
        if (rData && Array.isArray(rData.items) && rData.items.length) {
          state.radar = rData.items.map(it => ({
            ticker: it.ticker,
            name: (it.fund && it.fund.data && it.fund.data.company_name) || it.ticker,
            sector: it.sector || "Sin clasificar",
            verdict: VERDICT_LABELS[it.veredicto] || "Analizar",
            verdictKey: it.veredicto || "faltan_datos",
            tone: VERDICT_TONES[it.veredicto] || "gray",
            note: (it.motivos || []).join(" · ") || "En seguimiento.",
            price: it.price && it.price.price != null ? "$" + Number(it.price.price).toFixed(2) : "Sin dato",
          }));
        }
      }
      if (verRes && verRes.ok) state.serverVersion = await verRes.json();
      if (jourRes && jourRes.ok) {
        const jData = await jourRes.json();
        if (jData && Array.isArray(jData.entries)) {
          state.entries = jData.entries.map(e => ({
            id: e.id,
            ticker: e.ticker,
            action: e.action ? e.action[0].toUpperCase() + e.action.slice(1) : "Comprar",
            amount: (e.data && e.data.precio) || 0,
            thesis: (e.data && e.data.tesis) || "",
            risk: (e.data && e.data.riesgos) || "",
            invalidation: (e.data && e.data.condicion_invalidacion) || "",
            date: e.created_at ? e.created_at.slice(0, 10) : "Hoy",
            lesson: (e.evaluation && e.evaluation.leccion) || "",
          }));
        }
      }
      if (setRes && setRes.ok) {
        const sData = await setRes.json();
        if (sData && sData.limits && sData.limits.max_position_pct != null) {
          state.settingsLimit = String(sData.limits.max_position_pct);
        }
      }
      if (profRes && profRes.ok) {
        const pData = await profRes.json();
        if (pData && pData.profile && pData.profile.nivel_riesgo) {
          state.settingsRisk = pData.profile.nivel_riesgo;
        }
      }
      if (flowsRes && flowsRes.ok) {
        const fData = await flowsRes.json();
        if (fData && Array.isArray(fData.rows)) state.flows = fData.rows;
      }

      // Mapear cartera real si existe
      if (state.serverDashboard && state.serverDashboard.portfolio) {
        const pf = state.serverDashboard.portfolio;
        state.serverRisk = state.serverDashboard.risk || null;
        state.cash = typeof pf.cash === "number" ? pf.cash : 0;
        if (Array.isArray(pf.positions)) {
          state.assets = pf.positions.map((p, i) => {
            const basis = p.price_info || {};
            const price = Number(basis.precio_usado)
              || (p.market_value != null && p.qty ? p.market_value / p.qty : 0)
              || 0;
            return {
              ticker: p.ticker,
              name: p.name || p.ticker,
              shares: Number(p.qty) || 0,
              price,
              cost: Number(p.invested) || 0,
              color: PALETTE[i % PALETTE.length],
              change: Number(p.return_pct) || 0,
              priceStatus: p.price_status || "",
              priceFuente: basis.fuente || "",
              priceAsof: basis.asof || "",
              verified: !!p.verified,
              type: assetType(p.ticker),
            };
          });
        }
      }

      // Mapear alcancia real
      if (state.serverMarcador && state.serverMarcador.alcancia) {
        const alc = state.serverMarcador.alcancia;
        if (typeof alc.progreso === "number") state.savings = alc.progreso;
      }
      const fuentes = state.serverMarcador && state.serverMarcador.fuentes;
      if (fuentes && fuentes.valor_actual && fuentes.valor_actual.fecha) {
        state.lastRef = fuentes.valor_actual.fecha
          + (fuentes.valor_actual.fuente ? " · " + fuentes.valor_actual.fuente : "");
      }
    } catch (err) {
      console.warn("Conexión local a FastAPI:", err);
    } finally {
      state.loading = false;
      applyModeBadge();
      renderRoute();
    }
  }

  function applyModeBadge() {
    const demo = isDemoMode();
    const btn = document.querySelector(".top-demo");
    const long = document.getElementById("mode-label");
    const short = document.getElementById("mode-label-short");
    if (long) long.textContent = demo ? "Modo demostración" : "Datos locales";
    if (short) short.textContent = demo ? "Demo" : "Local";
    if (btn) btn.classList.toggle("connected", !demo);
  }

  // ======================= VISTAS =======================

  // ---- Resumen ----
  function renderResumen() {
    const invested = investedTotal();
    const isDemo = isDemoMode();
    const hoy = new Date().toLocaleDateString("es-PE", {weekday:"long", day:"numeric", month:"long", year:"numeric"}).toUpperCase();

    let netDeposits = null, fxCost = null, fxLabel = "ESTIMACIÓN", pocketOut = null, result = null, spyDiff = null;
    const m = state.serverMarcador && state.serverMarcador.marcador;
    if (m) {
      netDeposits = m.depositado_neto;
      fxCost = m.costos_deposito;
      if (m.costos_etiqueta) fxLabel = m.costos_etiqueta;
      pocketOut = m.puesto_bolsillo;
      if (typeof m.resultado_real === "number") result = m.resultado_real;
    }
    const fant = state.serverMarcador && state.serverMarcador.fantasma;
    if (fant && typeof fant.diferencia === "number" && fant.valor_fantasma) {
      spyDiff = (fant.diferencia / fant.valor_fantasma) * 100;
    }
    if (isDemo) {
      if (netDeposits == null) netDeposits = 1000;
      if (fxCost == null) fxCost = 13.60;
      if (pocketOut == null) pocketOut = 986.40;
      if (result == null) result = invested - pocketOut;
      if (spyDiff == null) spyDiff = 3.8;
    } else if (result == null && pocketOut != null) {
      result = invested - pocketOut;
    }

    const alc = (state.serverMarcador && state.serverMarcador.alcancia) || {};
    const goalPractical = alc.meta_soles || (isDemo ? 2000 : 0);
    const goalOptimal = alc.optimo_soles || (isDemo ? 3000 : 0);

    const spyInst = state.serverPulse && Array.isArray(state.serverPulse.instrumentos)
      ? state.serverPulse.instrumentos.find(i => i.ticker === "SPY") : null;
    const rk = state.serverRisk || (state.serverDashboard && state.serverDashboard.risk) || null;
    const spyVal = spyInst && spyInst.price != null
      ? Number(spyInst.price).toLocaleString("en-US", {minimumFractionDigits:2})
      : (isDemo ? "5,983.32" : "Sin dato");
    const spyChg = spyInst && spyInst.day_change_pct != null
      ? `${spyInst.day_change_pct >= 0 ? "+" : ""}${Number(spyInst.day_change_pct).toFixed(2)}%`
      : (isDemo ? "+0.48%" : "—");
    const hhiVal = rk && rk.hhi != null ? String(rk.hhi) : (isDemo ? "0.51" : "Sin dato");
    const divVal = rk && rk.diversificacion_efectiva != null
      ? `${rk.diversificacion_efectiva} activos` : (isDemo ? "2.0 activos" : "Sin dato");
    const moneyOrNA = v => (v == null ? "Sin dato" : privateText(money(v)));

    const snapshotRows = state.assets.map(a => {
      const value = round(a.shares * a.price);
      return `<li><button class="snapshot-row" data-action="asset" data-ticker="${escapeHtml(a.ticker)}"><span class="sr-only">Ver detalle de </span>${assetLabel(a.ticker, a.name, monoTone(a.ticker, a.type || assetType(a.ticker)))}<span class="snapshot-value">${privateText(money(value))}<span class="cell-sub">${(value / (invested || 1) * 100).toFixed(1)}% de lo invertido</span></span>${icon("chevron","snapshot-chevron")}</button></li>`;
    }).join("");

    main.innerHTML = intro(
      `HOY · ${hoy}`,
      "Buenos días.",
      "Una mirada clara a tu dinero. Sin ruido, sin prisa.",
      `<button class="btn" data-action="export">${icon("download")}Exportar</button><a class="btn btn-primary" href="#analisis">Analizar una decisión ${icon("arrow")}</a>`
    ) + `
      <div class="overview-grid">
        <section class="card balance-card" aria-label="Resumen de la cartera">
          <div class="balance-top"><p class="balance-label">Tu cartera vale hoy</p><button class="icon-btn" data-action="privacy" id="privacy-button" aria-pressed="${state.private}" aria-label="${state.private ? "Mostrar" : "Ocultar"} importes">${icon(state.private ? "eyeoff" : "eye")}</button></div>
          <div class="balance-amount">${privateText(money(invested))}</div>
          <div class="balance-return">${result != null ? `<span class="badge ${result >= 0 ? "badge-green" : "badge-red"}">${icon("trend","icon-sm")}${privateText((result >= 0 ? "+" : "−") + money(Math.abs(result)), result >= 0 ? "positive" : "negative")}</span><span class="small muted">${result >= 0 ? "por encima" : "por debajo"} de lo que salió de tu bolsillo</span>` : `<span class="badge badge-muted">Sin dato aún</span><span class="small muted">falta el valor actual o tu marcador</span>`}</div>
          <dl class="balance-stats"><div><dt>Cartera + efectivo</dt><dd>${privateText(money(invested + state.cash))}</dd></div><div><dt>Disponible</dt><dd>${privateText(money(state.cash))}</dd></div></dl>
          <section class="snapshot" aria-labelledby="snapshot-heading"><div class="snapshot-head"><h2 id="snapshot-heading">Tus posiciones</h2><a class="btn btn-plain" href="#cartera">Ver cartera ${icon("external","icon-sm")}</a></div><ul class="snapshot-list">${snapshotRows || `<li class="small muted" style="padding:16px 0">Aún no hay posiciones registradas.</li>`}</ul></section>
          <div class="snapshot-foot"><p>${isDemo ? "Escenario ilustrativo · datos de ejemplo" : `Última referencia: ${escapeHtml(state.lastRef || "Sin dato")}`}</p><button class="btn btn-plain" data-action="about">Origen de datos ${icon("external","icon-sm")}</button></div>
        </section>
        <aside class="insight-stack" aria-label="Aprender con contexto">
          <section class="ai-card"><div><p class="ai-kicker">${icon("sparkles")}LUNA · TU COMPAÑERA</p><h2>Detrás de cada número,<br>una buena pregunta.</h2><p>Entiende tu exposición y los conceptos antes de pensar en tu próxima decisión.</p></div><div><button class="btn" data-action="goto" data-route="asistente">Conversar con Luna ${icon("arrow")}</button><p class="ai-disclaimer">${isDemo ? "Respuestas ilustrativas de demostración." : "Conectada al asistente de esta app."}<br>Nunca ejecuta operaciones ni predice precios.</p></div></section>
          <section class="card learning-card" aria-label="Tu alcancía"><p class="eyebrow">TU ALCANCÍA</p><h3 class="learning-title">${icon("target")}Un paso a la vez</h3><p>Tu colchón para invertir con tranquilidad.</p>
            <div class="savings-value">S/ ${state.savings.toLocaleString("en-US")} <small>${goalPractical > 0 ? "de S/ " + goalPractical.toLocaleString("en-US") : "sin meta aún"}</small></div>
            <div class="progress" role="progressbar" aria-label="Progreso de la alcancía" aria-valuemin="0" aria-valuemax="${goalPractical || 1}" aria-valuenow="${Math.min(state.savings, goalPractical)}"><span style="width:${goalPractical > 0 ? Math.min(state.savings / goalPractical * 100, 100) : 0}%"></span></div>
            <div class="progress-captions"><span>${goalPractical > 0 ? Math.round(Math.min(state.savings / goalPractical, 1) * 100) + "% de tu meta práctica" : "Aún no hay meta calculable"}</span><span>${goalOptimal > 0 ? "Meta óptima S/ " + goalOptimal.toLocaleString("en-US") : ""}</span></div>
            <form class="inline-form" id="form-savings"><label class="sr-only" for="input-savings">Registrar ahorro en soles</label><input class="field" id="input-savings" value="${escapeHtml(state.homeSavingText)}" placeholder="Ej. guardé 80 soles" autocomplete="off"/><button class="btn" aria-label="Preparar aporte">${icon("arrow")}</button></form>
            ${state.homeDraft !== null ? `
              <div class="draft-card"><strong>Revisa antes de guardar</strong><p class="muted">Aporte: S/ ${state.homeDraft.toFixed(2)}</p>
                <label class="check-line"><input type="checkbox" id="check-savings-reviewed" ${state.homeReviewed ? "checked" : ""}/> Confirmo que el importe es correcto</label>
                <div class="dialog-actions"><button type="button" class="btn" data-action="cancel-savings-draft">Cancelar</button><button type="button" class="btn btn-primary" data-action="save-savings-draft" ${!state.homeReviewed ? "disabled" : ""}>Guardar aporte</button></div>
              </div>` : ""}
          </section>
        </aside>
      </div>

      <section class="card mt-24" aria-label="Tu marcador">
        <div class="section-header"><div class="section-title"><h2>Tu marcador</h2><p class="small muted">Lo que pusiste, lo que tienes y la diferencia real.</p></div><span class="badge badge-muted">SIN LETRA PEQUEÑA</span></div>
        <ul class="kv-list">
          <li class="kv-row"><span>Depósitos netos</span><strong>${moneyOrNA(netDeposits)}</strong></li>
          <li class="kv-row"><span>Costo de cambiar soles a dólares <span class="badge badge-muted">${escapeHtml(fxLabel)}</span></span><strong>${fxCost == null ? "Sin dato" : privateText("−" + money(fxCost))}</strong></li>
          <li class="kv-row kv-highlight"><span>Salió de tu bolsillo</span><strong>${moneyOrNA(pocketOut)}</strong></li>
          <li class="kv-row"><span>Tu cartera hoy <span class="badge ${isDemo ? "badge-demo" : "badge-green"}">${isDemo ? "HECHO · DEMO" : "HECHO"}</span></span><strong>${privateText(money(invested))}</strong></li>
          <li class="kv-row kv-result"><span>Resultado de bolsillo</span><strong class="${result != null && result < 0 ? "negative" : "positive"}">${result == null ? "Sin dato" : privateText((result >= 0 ? "+" : "−") + money(Math.abs(result)))}</strong></li>
        </ul>
        <div class="card-foot"><span>Comparación con S&amp;P 500</span><strong>${spyDiff == null ? "Sin dato" : `${spyDiff >= 0 ? "+" : ""}${spyDiff.toFixed(1)}% ${icon("arrowup","icon-sm")}`}</strong></div>
      </section>

      ${advanced("Pulso de mercado y métricas de riesgo", `
        <div class="advanced-grid">
          <div>
            <span class="eyebrow">PULSO DE MERCADO</span>
            <h3>Una foto más amplia</h3>
            <p>${isDemo ? "Datos de referencia ilustrativos. Verifica precios y fechas antes de decidir." : escapeHtml((state.serverPulse && state.serverPulse.lectura) || "Fuente: Yahoo Finance y tus datos guardados. Regla técnica, no predicción.")}</p>
          </div>
          <div class="advanced-metrics">
            <div><span>S&amp;P 500 (SPY)</span><strong>${spyVal}</strong><small>${spyChg}</small></div>
            <div><span>Concentración (HHI)</span><strong>${hhiVal}</strong><small>CÁLCULO</small></div>
            <div><span>Diversificación efectiva</span><strong>${divVal}</strong><small>CÁLCULO</small></div>
          </div>
        </div>
      `)}
    ` + footer();
  }

  // ---- Mi cartera ----
  function positionsTable() {
    const invested = investedTotal();
    return `<table class="positions-table"><caption class="sr-only">Posiciones de la cartera. Los importes están en dólares estadounidenses.</caption><thead><tr><th scope="col">Activo</th><th scope="col">Precio utilizado</th><th scope="col">Valor en cartera</th><th scope="col">Resultado</th><th scope="col"><span class="sr-only">Detalles</span></th></tr></thead><tbody>${state.assets.map(a => {
      const value = round(a.shares * a.price), gain = round(value - a.cost);
      return `<tr><td>${assetLabel(a.ticker, a.name, monoTone(a.ticker, a.type || assetType(a.ticker)))}</td><td data-label="Precio utilizado">${privateText(money(a.price))}<span class="cell-sub">${a.shares} ${a.type === "ETF" ? "participaciones" : "acciones"}</span></td><td data-label="Valor en cartera">${privateText(money(value))}<span class="cell-sub">${(value / (invested || 1) * 100).toFixed(1)}% de lo invertido</span></td><td data-label="Resultado">${privateText((gain >= 0 ? "+" : "−") + money(Math.abs(gain)), gain >= 0 ? "positive" : "negative")}<span class="cell-sub ${a.change >= 0 ? "positive" : "negative"}">${privateText(pct(a.change))} vs. costo</span></td><td><button class="icon-btn" data-action="asset" data-ticker="${escapeHtml(a.ticker)}" aria-label="Ver detalle de ${escapeHtml(a.ticker)}">${icon("chevron")}</button></td></tr>`;
    }).join("")}</tbody></table>`;
  }

  function walletMetricCards() {
    const invested = investedTotal();
    const gain = round(invested - costBasis());
    const cost = costBasis();
    return `<dl class="wallet-metrics">
      <div class="card wallet-metric"><dt>Invertido en posiciones</dt><dd>${privateText(money(invested))}</dd><p>${state.assets.length} ${state.assets.length === 1 ? "activo" : "activos"} en tu cartera</p></div>
      <div class="card wallet-metric"><dt>Resultado no realizado</dt><dd>${privateText((gain >= 0 ? "+" : "−") + money(Math.abs(gain)), gain >= 0 ? "positive" : "negative")}</dd><p>${cost > 0 ? privateText(pct(gain / cost * 100)) + " sobre el coste de las posiciones" : "Sin coste registrado aún"}</p></div>
      <div class="card wallet-metric"><dt>Saldo disponible</dt><dd>${privateText(money(state.cash))}</dd><p>${isDemoMode() ? "Saldo ilustrativo de demostración" : "Efectivo registrado en tu cartera"}</p></div>
    </dl>`;
  }

  const watchPool = () => {
    const map = new Map();
    state.radar.forEach(r => map.set(r.ticker, {ticker:r.ticker, name:r.name, price:r.price, type:assetType(r.ticker, r.sector || ""), sector:r.sector, note:r.note, verdict:r.verdict, tone:r.tone, src:"radar"}));
    state.assets.forEach(a => { const existing = map.get(a.ticker) || {}; map.set(a.ticker, {ticker:a.ticker, name:existing.name || a.name, price:existing.price || money(a.price), type:existing.type || assetType(a.ticker), sector:existing.sector || "", note:existing.note || "", verdict:existing.verdict || "", tone:existing.tone || "gray", src:"posicion"}); });
    return [...map.values()];
  };

  function assetCard(item) {
    const inWallet = state.assets.some(a => a.ticker === item.ticker);
    const type = item.type || assetType(item.ticker);
    const tone = monoTone(item.ticker, type);
    return `<article class="card asset-card"><div class="asset-card-top">${monogram(item.ticker[0] || "?", tone)}${watchButton(item.ticker)}</div><span class="badge ${type === "ETF" ? "badge-purple" : "badge-blue"}">${type}</span>${item.verdict ? ` <span class="badge ${item.tone === "green" ? "badge-green" : item.tone === "orange" ? "badge-demo" : "badge-muted"}">${escapeHtml(item.verdict)}</span>` : ""}<h2 style="margin-top:12px">${escapeHtml(item.ticker)}</h2><p class="asset-company">${escapeHtml(item.name)}</p><p class="asset-card-price">${privateText(item.price)}</p><p class="small muted" style="margin-top:4px">${inWallet ? "Ya está en tu cartera" : escapeHtml(item.sector || "Precio de referencia")}</p><div class="asset-card-bottom"><span class="small muted">${item.src === "posicion" ? "Tu posición" : "Del radar"}</span><button class="btn btn-plain" data-action="${item.src === "posicion" ? "asset" : "radar-asset"}" data-ticker="${escapeHtml(item.ticker)}">Detalles ${icon("arrow","icon-sm")}</button></div></article>`;
  }

  function renderWalletContent() {
    const host = document.getElementById("wallet-content");
    if (!host) return;
    if (state.walletTab === "posiciones") {
      host.innerHTML = state.assets.length
        ? `<section class="card"><div class="section-header"><h2>Tus ${state.assets.length} ${state.assets.length === 1 ? "posición" : "posiciones"}</h2><span class="small muted">Resultados sobre el costo de compra</span></div>${positionsTable()}</section>`
        : `<section class="empty-state">${icon("wallet")}<h2>Aún no hay posiciones.</h2><p>Registra tu primera posición desde Sincronización.</p><button class="btn btn-primary" data-action="start-import">Registrar posición ${icon("arrow")}</button></section>`;
    } else {
      const watched = watchPool().filter(a => state.watched.has(a.ticker));
      host.innerHTML = watched.length
        ? `<div class="explore-grid">${watched.map(assetCard).join("")}</div>`
        : `<section class="empty-state">${icon("star")}<h2>Aún no sigues ningún activo.</h2><p>Guarda activos desde Explorar para encontrarlos aquí.</p><a class="btn btn-primary" href="#explorar">Explorar activos ${icon("arrow")}</a></section>`;
    }
    document.querySelectorAll("[data-wallet-tab]").forEach(el => el.setAttribute("aria-pressed", String(el.dataset.walletTab === state.walletTab)));
    applyPrivacy();
  }

  function renderCartera() {
    const isDemo = isDemoMode();
    main.innerHTML = intro(
      "TU DINERO EN MOVIMIENTO",
      "Mi cartera.",
      "Cada posición en su lugar. Cada número con su fuente y su fecha.",
      `<button class="btn" data-action="privacy" aria-pressed="${state.private}" aria-label="${state.private ? "Mostrar" : "Ocultar"} importes">${icon(state.private ? "eyeoff" : "eye")}<span>${state.private ? "Mostrar" : "Ocultar"} importes</span></button><button class="btn" data-action="export">${icon("download")}Exportar CSV</button><button class="btn btn-primary" data-action="start-sync">${icon("camera")}Sincronizar</button>`
    ) + walletMetricCards() +
    `<div class="notice">${icon("info")}<p>El resultado no realizado es el valor actual menos el costo de compra. No incluye comisiones ni impuestos y no garantiza resultados futuros.</p></div>
     <div class="toolbar"><div class="tab-group" aria-label="Vista de la cartera"><button class="tab-btn" data-action="wallet-tab" data-wallet-tab="posiciones" aria-pressed="${state.walletTab === "posiciones"}">Posiciones</button><button class="tab-btn" data-action="wallet-tab" data-wallet-tab="seguimiento" aria-pressed="${state.walletTab === "seguimiento"}">Seguimiento <span id="watch-count">(${state.watched.size})</span></button></div><span class="small muted">${isDemo ? "Escenario ilustrativo" : escapeHtml(state.lastRef || "Precios guardados")}</span></div>
     <div id="wallet-content"></div>

     <section class="card mt-24" id="sync" aria-label="Sincronización">
       <div class="section-header"><div class="section-title"><h2>Sincronización</h2><p class="small muted">Mantén todo al día, con tu revisión.</p></div><div class="tab-group"><button class="tab-btn" data-action="sync-tab" data-tab="resumen" aria-pressed="${!state.portfolioSync}">Resumen</button><button class="tab-btn" data-action="sync-tab" data-tab="importar" aria-pressed="${state.portfolioSync}">Importar posición</button></div></div>
       ${!state.portfolioSync ? `
         <div class="tool-note">${icon("shield","icon-lg")}<div><strong>Tú tienes la última palabra</strong><p>Ninguna foto ni dato externo modifica tu cartera hasta que revises y confirmes cada importe.</p></div><button class="btn" data-action="start-import">Empezar ${icon("arrow","icon-sm")}</button></div>
       ` : `
         <div class="sync-grid">
           <div><h3>Trae tu cartera a este espacio</h3><p>Puedes adjuntar una captura de Hapi como referencia y transcribir los datos. La lectura es tuya: confirma cada número antes de guardar.</p>
             <input type="file" id="file-capture" accept="image/*" hidden/>
             <button type="button" class="upload" data-action="trigger-upload">${icon("camera","icon-lg")}<strong>${escapeHtml(state.portfolioFileName) || "Elegir una captura"}</strong><small>PNG o JPG · solo referencia visual</small></button>
           </div>
           <div class="sync-fields">
             <span class="eyebrow">BORRADOR EDITABLE</span>
             <div class="field-pair">
               <label class="field-label">Ticker<input class="field" id="sync-ticker" value="${escapeHtml(state.portfolioTicker)}" maxlength="10" placeholder="Ej. VOO"/></label>
               <label class="field-label">Participaciones<input class="field" type="number" min="0" step="any" id="sync-shares" value="${escapeHtml(state.portfolioShares)}" placeholder="0.00"/></label>
             </div>
             <label class="field-label">Precio por participación · USD<input class="field" type="number" min="0" step="any" id="sync-price" value="${escapeHtml(state.portfolioPrice)}" placeholder="0.00"/></label>
             <label class="check-line"><input type="checkbox" id="sync-check" ${state.portfolioChecked ? "checked" : ""}/> Revisé cada dato contra Hapi</label>
             <label class="check-line"><input type="checkbox" id="sync-replace" ${state.portfolioReplace ? "checked" : ""}/> Reemplazar toda mi cartera</label>
             ${state.portfolioReplace ? `<label class="check-line warning"><input type="checkbox" id="sync-confirm-replace" ${state.portfolioConfirmReplace ? "checked" : ""}/> Entiendo que se quitarán ${state.assets.map(a => a.ticker).join(", ")}</label>` : ""}
             <button type="button" class="btn btn-primary" data-action="save-sync" ${(!/^[A-Z][A-Z0-9.]{0,9}$/.test(state.portfolioTicker) || Number(state.portfolioShares) <= 0 || Number(state.portfolioPrice) <= 0 || !state.portfolioChecked || (state.portfolioReplace && !state.portfolioConfirmReplace)) ? "disabled" : ""}>Confirmar importación ${icon("arrow")}</button>
           </div>
         </div>`}
     </section>

     ${advanced("Herramientas avanzadas de cartera", `
       <div class="advanced-grid">
         <div><h3>Órdenes y conciliación de costo</h3><p>Esta app no envía operaciones a tu bróker. Las órdenes se anotan aquí solo como registro para conciliar tu costo.</p></div>
         ${isDemo ? `<button class="btn" data-action="add-cash">Añadir $50 de efectivo demo</button>` : ""}
       </div>
     `)}` + footer();
    renderWalletContent();
  }

  // ---- ¿Compro o vendo? ----
  function renderAnalisis() {
    const ticker = state.analysisTicker.toUpperCase();
    const asset = state.assets.find(a => a.ticker === ticker);
    const value = asset ? asset.shares * asset.price : 0;
    const total = investedTotal() + state.cash;
    const amountNum = Number(state.analysisAmount) || 0;
    const before = total ? (value / total) * 100 : 0;
    const after = total ? ((value + (state.analysisSide === "Comprar" ? amountNum : -amountNum)) / total) * 100 : 0;
    const limitPct = Number(state.settingsLimit) || 40;
    const valid = /^[A-Z][A-Z0-9.]{0,9}$/.test(ticker) && amountNum > 0 && (state.analysisSide !== "Vender" || (!!asset && amountNum <= value));
    const datalist = [...new Set([...state.assets.map(a => a.ticker), ...state.radar.map(r => r.ticker)])].slice(0, 60);

    main.innerHTML = intro(
      "UN PASO ANTES DE ACTUAR",
      "¿Compro o vendo?",
      "Una buena decisión empieza con una mejor pregunta."
    ) + `
      <div class="analysis-layout">
        <section class="card analysis-form" aria-label="Simulador de decisión">
          <span class="eyebrow">SIMULA TU DECISIÓN</span>
          <h2 style="margin-top:8px">Pongamos los números sobre la mesa</h2>
          <form id="form-analysis">
            <label class="field-label">¿Qué activo estás considerando?
              <div class="search-field" style="width:100%">${icon("search")}<input class="field" list="tickers" id="analysis-ticker" value="${escapeHtml(state.analysisTicker)}" placeholder="Busca un ticker" maxlength="10" autocomplete="off"/></div>
              <datalist id="tickers">${datalist.map(t => `<option value="${escapeHtml(t)}"></option>`).join("")}</datalist>
            </label>
            <div>
              <span class="field-label" style="margin-bottom:8px">¿Qué quieres hacer?</span>
              <div class="tab-group" role="group" aria-label="Lado de la operación">
                <button type="button" class="tab-btn" data-action="side" data-side="Comprar" aria-pressed="${state.analysisSide === "Comprar"}">${icon("arrowdown","icon-sm")} Comprar</button>
                <button type="button" class="tab-btn" data-action="side" data-side="Vender" aria-pressed="${state.analysisSide === "Vender"}" ${!asset ? "disabled" : ""}>${icon("arrowup","icon-sm")} Vender</button>
              </div>
              ${!asset ? '<p class="hint" style="margin-top:8px">Solo puedes simular ventas de posiciones que ya tienes.</p>' : ""}
            </div>
            <label class="field-label">Monto en dólares
              <div class="amount-field"><span>$</span><input type="number" min="0.01" step="0.01" id="analysis-amount" value="${escapeHtml(state.analysisAmount)}"/><span>USD</span></div>
            </label>
            <div class="chips">
              ${[50, 100, 200].map(n => `<button type="button" class="tab-btn" data-action="amount" data-amt="${n}">$${n}</button>`).join("")}
              ${state.analysisSide === "Vender" && asset ? `<button type="button" class="tab-btn" data-action="amount" data-amt="${value.toFixed(2)}">Toda la posición</button>` : ""}
              ${state.analysisSide === "Comprar" && state.cash > 0 ? `<button type="button" class="tab-btn" data-action="amount" data-amt="${state.cash.toFixed(2)}">Todo mi efectivo</button>` : ""}
            </div>
            <button class="btn btn-primary" id="btn-run-analysis" ${!valid ? "disabled" : ""}>Analizar decisión ${icon("arrow")}</button>
          </form>
        </section>
        <aside class="analysis-aside">
          <div class="aside-compass">${icon("compass","icon-lg")}</div>
          <div><span class="eyebrow">DECIDIR CON INTENCIÓN</span><h2>Menos impulso.<br/>Más perspectiva.</h2><p>No buscamos adivinar el mercado. Buscamos que entiendas qué cambia para ti con cada decisión.</p></div>
          <small>${icon("shield")} Esto es una simulación, no una orden de compra o venta.</small>
        </aside>
      </div>

      ${state.analysisShow ? `
        <section class="card mt-24" aria-label="Resultado de la simulación">
          <div class="section-header"><div class="section-title"><h2>Así se vería tu decisión</h2><p class="small muted">Simulación ilustrativa basada en los datos actuales.</p></div><span class="badge ${after > limitPct ? "badge-demo" : "badge-green"}">${after > limitPct ? "REVISAR CONCENTRACIÓN" : "DENTRO DEL LÍMITE"}</span></div>
          <div class="result-grid">
            <div><span>Peso de ${escapeHtml(ticker)}</span><strong>${before.toFixed(1)}% ${icon("arrow","icon-sm")} ${after.toFixed(1)}%</strong><small>Antes y después</small></div>
            <div><span>Efectivo disponible</span><strong>${privateText(money(state.cash))} ${icon("arrow","icon-sm")} ${privateText(money(Math.max(0, state.cash + (state.analysisSide === "Vender" ? amountNum : -amountNum))))}</strong><small>Una compra puede requerir depositar fondos</small></div>
            <div><span>Límite por empresa</span><strong class="${after > limitPct ? "negative" : "positive"}">${after > limitPct ? `Supera el ${limitPct}%` : `Dentro del ${limitPct}%`}</strong><small>Según tu perfil actual</small></div>
          </div>
          <div class="opinion">${icon("sparkles")}<div><strong>La segunda mirada de Luna ${isDemoMode() ? '<span class="badge badge-muted">DEMO</span>' : ""}</strong><p>${after > limitPct ? "Esta operación aumentaría tu concentración. Revisa si el tamaño de la posición refleja tu convicción y tu tolerancia al riesgo." : "La simulación no supera tu límite de concentración. Antes de decidir, comprueba el precio, tu tesis y cuánto efectivo necesitas conservar."}</p></div></div>
          <div class="result-journal">
            <div><h3>Deja constancia de tu decisión</h3><p>Escribe tu razonamiento ahora; podrás evaluarlo más adelante.</p></div>
            <div class="form-stack">
              <label class="field-label">Mi tesis<textarea class="field" id="result-thesis" placeholder="¿Por qué tiene sentido para mí?">${escapeHtml(state.analysisThesis)}</textarea></label>
              <label class="field-label">Riesgo principal<textarea class="field" id="result-risk" placeholder="¿Qué podría salir mal?">${escapeHtml(state.analysisRisk)}</textarea></label>
              <label class="field-label">Qué invalidaría mi idea<textarea class="field" id="result-invalidation" placeholder="¿Qué me haría cambiar de opinión?">${escapeHtml(state.analysisInvalidation)}</textarea></label>
              <button type="button" class="btn btn-primary" data-action="save-analysis-journal" id="btn-save-analysis-journal" ${(!state.analysisThesis.trim() || !state.analysisRisk.trim() || !state.analysisInvalidation.trim()) ? "disabled" : ""}>Guardar en mi diario ${icon("arrow")}</button>
            </div>
          </div>
        </section>` : ""}

      ${advanced("Fundamentos, valuación y análisis técnico", `
        <div class="advanced-grid">
          <div><h3>Más profundidad, cuando la necesites</h3><p>DCF, múltiplos, niveles ATR y métricas técnicas requieren datos verificados. Si falta un dato, lo verás marcado como «Sin dato».</p></div>
          <div class="advanced-metrics">
            <div><span>DCF</span><strong>Sin dato</strong><small>NO CALCULABLE</small></div>
            <div><span>RSI 14</span><strong>Sin dato</strong><small>NO VERIFICADO</small></div>
          </div>
        </div>
      `)}` + footer();
  }

  // ---- Explorar ----
  function filteredExplore() {
    const query = state.query.trim().toLocaleLowerCase("es");
    return watchPool()
      .filter(a => (`${a.ticker} ${a.name}`.toLocaleLowerCase("es").includes(query))
        && (state.filter === "todos"
          || (state.filter === "acciones" && a.type === "Acción")
          || (state.filter === "etf" && a.type === "ETF")
          || (state.filter === "seguimiento" && state.watched.has(a.ticker))))
      .sort(state.sort === "price"
        ? (a,b) => (parseFloat(String(b.price).replace(/[^0-9.]/g,"")) || 0) - (parseFloat(String(a.price).replace(/[^0-9.]/g,"")) || 0)
        : (a,b) => a.name.localeCompare(b.name, "es"));
  }

  function renderExploreResults() {
    const host = document.getElementById("explore-results");
    if (!host) return;
    const result = filteredExplore();
    host.innerHTML = result.length ? result.map(assetCard).join("") : `<section class="empty-state">${icon("search")}<h2>${state.filter === "seguimiento" && !state.query ? "Tu lista está esperando un comienzo." : "No encontramos coincidencias."}</h2><p>${state.filter === "seguimiento" && !state.query ? "Marca la estrella de un activo para seguirlo en este navegador." : "Prueba con otro nombre o ticker, o elimina los filtros."}</p><button class="btn" data-action="clear-filters">Ver todos los activos</button></section>`;
    const status = document.getElementById("filter-status");
    if (status) status.textContent = `${result.length} ${result.length === 1 ? "activo" : "activos"}${state.query ? ` para «${state.query}»` : ""}.`;
    document.querySelectorAll("[data-filter]").forEach(el => el.setAttribute("aria-pressed", String(el.dataset.filter === state.filter)));
    applyPrivacy();
  }

  function renderExplorar() {
    main.innerHTML = intro(
      "IDEAS PARA MIRAR, NO PARA PERSEGUIR",
      "Explorar.",
      "Un punto de partida para investigar; nunca una señal para actuar."
    ) + `
      <label class="sr-only" for="explore-search">Buscar por ticker o nombre</label><div class="search-field">${icon("search")}<input class="field" id="explore-search" type="search" maxlength="80" placeholder="Busca por ticker o nombre…" autocomplete="off" value="${escapeHtml(state.query)}"></div>
      <div class="filters-row"><div class="tab-group" aria-label="Filtrar activos"><button class="tab-btn" data-action="filter" data-filter="todos" aria-pressed="true">Todos</button><button class="tab-btn" data-action="filter" data-filter="acciones" aria-pressed="false">Acciones</button><button class="tab-btn" data-action="filter" data-filter="etf" aria-pressed="false">ETF</button><button class="tab-btn" data-action="filter" data-filter="seguimiento" aria-pressed="false">Seguimiento</button></div><label class="sort-label" for="explore-sort">Ordenar<select class="sort-select" id="explore-sort"><option value="name" ${state.sort === "name" ? "selected" : ""}>Por nombre</option><option value="price" ${state.sort === "price" ? "selected" : ""}>Mayor precio</option></select></label></div>
      <p class="filter-status" id="filter-status" role="status" aria-live="polite"></p>
      <div class="explore-grid" id="explore-results"></div>` + footer();
    renderExploreResults();
  }

  // ---- Hapi IA (Luna) ----
  function renderMessages(scroll = false) {
    const host = document.getElementById("chat-messages");
    if (!host) return;
    if (scroll) {
      host.querySelectorAll("[data-typing]").forEach(n => n.remove());
    } else host.replaceChildren();
    const firstNew = scroll ? host.querySelectorAll("article.message").length : 0;
    state.messages.slice(firstNew).forEach(message => {
      const article = document.createElement("article");
      article.className = `message ${message.role === "user" ? "user" : "assistant"}`;
      const label = document.createElement("p");
      label.className = "message-label";
      label.textContent = message.role === "user" ? "Tú" : (isDemoMode() ? "Luna · Respuesta ilustrativa" : "Luna");
      const body = document.createElement("p");
      body.className = "message-body";
      body.textContent = state.private ? message.text.replace(/(?:[+−])?(?:US)?\$[\d,.]+/g, "••••").replace(/[+−]?\d+(?:\.\d+)?%/g, "••••") : message.text;
      article.append(label, body);
      host.append(article);
    });
    if (state.lunaTyping) {
      const article = document.createElement("article");
      article.className = "message assistant";
      article.dataset.typing = "1";
      article.innerHTML = `<p class="message-label">Luna está pensando…</p><p class="message-body"><span class="typing"><i></i><i></i><i></i></span></p>`;
      host.append(article);
    }
    if (scroll) host.scrollTo({top: host.scrollHeight, behavior: "auto"});
  }

  function renderAsistente() {
    const isDemo = isDemoMode();
    main.innerHTML = intro(
      "HAPI IA",
      "Buenas preguntas. Mejores fundamentos.",
      "Una conversación para entender, no para predecir."
    ) + `
      <div class="conversation-layout">
        <section class="card conversation" aria-labelledby="chat-heading">
          <div class="chat-header"><span class="ai-avatar">${icon("sparkles")}</span><div><h2 id="chat-heading" style="font-size:18px">Luna, tu compañera de criterio</h2><p class="asset-sub">${isDemo ? "Modo demostración · respuestas ilustrativas" : "Asistente conectado · no opera ni predice"}</p></div></div>
          <div class="chat-messages" id="chat-messages" role="log" aria-label="Conversación con Luna" aria-live="polite" aria-relevant="additions"></div>
          <div class="chat-prompts" aria-label="Preguntas sugeridas"><button class="btn" data-action="chat-prompt" data-prompt="¿Qué riesgos tiene mi cartera?">¿Qué riesgos tiene mi cartera?</button><button class="btn" data-action="chat-prompt" data-prompt="Ayúdame antes de comprar">Ayúdame antes de comprar</button><button class="btn" data-action="chat-prompt" data-prompt="¿Qué significa diversificar?">¿Qué significa diversificar?</button></div>
          <form class="chat-form" id="form-luna"><label class="sr-only" for="chat-input">Escribe tu pregunta para Luna</label><div class="composer"><textarea id="chat-input" rows="1" maxlength="500" placeholder="Escribe tu pregunta…"></textarea><button class="btn btn-primary" id="chat-send" type="submit" aria-label="Enviar pregunta" disabled>${icon("send")}</button></div><p class="chat-note">Luna propone preguntas y contexto; tú decides y operas en tu bróker.<br>Enter para enviar · Mayús + Enter para una nueva línea</p></form>
        </section>
        <aside class="card guide-card"><h2>Antes de decidir</h2><p>El contexto vale más que una respuesta rápida.</p>
          <div class="guide-step"><span class="guide-step-number">1</span><div><strong>Entiende el activo</strong><p>Qué representa y de dónde viene su valor.</p></div></div>
          <div class="guide-step"><span class="guide-step-number">2</span><div><strong>Reconoce el riesgo</strong><p>Qué podrías perder y qué exposición se repite.</p></div></div>
          <div class="guide-step"><span class="guide-step-number">3</span><div><strong>Define tu horizonte</strong><p>Cuándo necesitarás el dinero y qué tolerancia tienes.</p></div></div>
        </aside>
      </div>` + footer();
    renderMessages();
    if (state.pendingPrompt) {
      const text = state.pendingPrompt; state.pendingPrompt = ""; sendQuestion(text);
    }
  }

  async function sendQuestion(text) {
    const query = String(text || "").trim().slice(0, 500);
    if (!query) return;
    state.messages.push({role:"user", text:query});
    state.lunaTyping = true;
    renderMessages(true);
    const input = document.getElementById("chat-input");
    if (input) { input.value = ""; input.style.height = "44px"; input.focus(); }
    const send = document.getElementById("chat-send");
    if (send) send.disabled = true;

    let reply = "";
    if (state.connected) {
      try {
        const history = state.messages.slice(0, -1).slice(-8)
          .map(m => ({role: m.role === "user" ? "user" : "assistant", content: m.text}));
        const res = await fetch("/api/assistant/ask", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({question: query, history}),
        });
        if (res.ok) {
          const data = await res.json();
          reply = data.answer || "";
        }
      } catch (err) {
        console.warn("Luna fetch failed:", err);
      }
    }
    if (!reply) {
      if (query.toLowerCase().includes("riesgo")) {
        reply = "Tu mayor exposición está en VOO y tecnología. Antes de cambiar algo, revisa si esa distribución sigue alineada con tu horizonte. Respuesta ilustrativa de demostración.";
      } else {
        reply = "Empecemos por tu objetivo, tu plazo y qué dato necesitarías para decidir. Esta respuesta es ilustrativa; conecta el asistente para un análisis personalizado.";
      }
    }
    state.lunaTyping = false;
    state.messages.push({role:"luna", text:reply});
    renderMessages(true);
  }

  // ---- Movimientos ----
  function flowRowAmount(row) {
    const meta = FLOW_META[row.kind] || {label: row.kind, icon: "activity", sign: 0};
    if (row.kind === "ahorro_soles") return {main: `+${soles(row.soles_amount || 0)}`, sub: "alcancía"};
    const usd = row.amount_usd;
    const sol = row.soles_amount;
    if (usd != null) {
      let sub = "";
      if (sol != null) sub = soles(sol) + (row.fx_rate ? ` · tc ${Number(row.fx_rate).toFixed(2)}` : "");
      return {main: `${meta.sign >= 0 ? "+" : "−"}${money(usd)}`, sub};
    }
    if (sol != null) return {main: `${meta.sign >= 0 ? "+" : "−"}${soles(sol)}`, sub: "sin dato en USD"};
    return {main: "Sin dato", sub: ""};
  }

  function flowsListHtml() {
    const rows = state.flows;
    if (!rows.length) {
      return `<section class="empty-state">${icon("activity")}<h2>Sin movimientos todavía.</h2><p>Cuenta un depósito, un retiro, un dividendo o un ahorro, o pega tu historial de Hapi.</p></section>`;
    }
    return `<section class="card activity-card" aria-label="Historial de movimientos">${rows.map(row => {
      const meta = FLOW_META[row.kind] || {label: row.kind, icon: "activity", sign: 0};
      const amt = flowRowAmount(row);
      const detail = `${row.at || ""}${row.source ? " · " + (FLOW_SOURCE[row.source] || row.source) : ""}`;
      return `<article class="activity-row"><span class="activity-icon">${icon(meta.icon)}</span><div class="activity-info"><strong>${escapeHtml(meta.label)}</strong><p>${escapeHtml(detail)}</p></div><div class="activity-amount ${meta.sign > 0 ? "positive" : ""}">${privateText(amt.main)}<span>${escapeHtml(amt.sub)}</span></div><button class="icon-btn" data-action="delete-flow" data-id="${row.id}" aria-label="Eliminar movimiento">${icon("trash","icon-sm")}</button></article>`;
    }).join("")}</section>`;
  }

  function flowDraftHtml() {
    if (!state.flowDraft) return "";
    const d = state.flowDraft;
    const dupCount = d.rows.filter(r => r.posible_duplicado).length;
    return `<div class="draft-card" style="margin:0 24px 20px">
      <strong>Revisa cada fila antes de guardar</strong>
      <table class="data-table"><thead><tr><th>Movimiento</th><th>Fecha</th><th style="text-align:right">Importe</th></tr></thead><tbody>
        ${d.rows.map(r => { const meta = FLOW_META[r.kind] || {label: r.kind}; const amt = flowRowAmount(r); return `<tr><td>${escapeHtml(meta.label)}${r.posible_duplicado ? ' <span class="badge badge-demo">posible duplicado</span>' : ""}</td><td>${escapeHtml(r.at || "")}</td><td>${privateText(amt.main)}</td></tr>`; }).join("")}
      </tbody></table>
      ${d.omitted && d.omitted.length ? `<p class="hint" style="margin-top:10px">Se omitieron ${d.omitted.length} líneas que no parecen movimientos de dinero.</p>` : ""}
      ${dupCount ? `<p class="settings-warning">Hay ${dupCount} ${dupCount === 1 ? "movimiento" : "movimientos"} que parecen ya registrados.<label class="check-line" style="margin-top:8px"><input type="checkbox" id="check-flow-dup" ${state.flowAllowDup ? "checked" : ""}/> Confirmar también los duplicados</label></p>` : ""}
      <label class="check-line" style="margin-top:12px"><input type="checkbox" id="check-flow-reviewed" ${state.flowReviewed ? "checked" : ""}/> Revisé cada importe</label>
      <div class="dialog-actions"><button type="button" class="btn" data-action="cancel-flow-draft">Cancelar</button><button type="button" class="btn btn-primary" data-action="confirm-flow-draft" ${!state.flowReviewed || state.flowBusy ? "disabled" : ""}>Guardar ${d.rows.length} ${d.rows.length === 1 ? "movimiento" : "movimientos"}</button></div>
    </div>`;
  }

  function renderMovimientos() {
    const isDemo = isDemoMode();
    main.innerHTML = intro(
      "MOVIMIENTOS",
      "La historia detrás del saldo.",
      "Registra lo que ya ocurrió en tu bróker o tu alcancía. Aquí nada se ejecuta."
    ) + `
      <div class="notice" style="margin-bottom:24px">${icon("shield")}<p>Registrar no es operar: anotas depósitos, retiros, dividendos y ahorros para que tu marcador sea real. Las compras y ventas se registran como posiciones en Mi cartera.</p></div>
      <section class="card" style="margin-bottom:24px" aria-label="Registrar un movimiento">
        <div class="section-header"><div class="section-title"><h2>Registrar un movimiento</h2><p class="small muted">Cuéntalo en una frase o pega tu historial de Hapi.</p></div></div>
        <form class="section-pad" id="form-flow" style="padding-top:0">
          <label class="sr-only" for="flow-text">Movimiento o historial</label>
          <textarea class="field" id="flow-text" rows="2" maxlength="4000" placeholder="Ej. guardé 80 soles · deposité 480 soles y llegaron 132.50 · entré a Hapi">${escapeHtml(state.flowText)}</textarea>
          <div class="dialog-actions"><button class="btn btn-primary" type="submit" ${state.flowBusy ? "disabled" : ""}>${icon("plus")}Preparar movimiento</button><span class="small muted">${isDemo ? "En demo se interpreta localmente." : "Nada se guarda sin tu revisión."}</span></div>
        </form>
        ${flowDraftHtml()}
      </section>
      <section aria-label="Movimientos registrados">
        <div class="section-header" style="padding-left:0;padding-right:0"><div class="section-title"><h2>Tus movimientos</h2><p class="small muted">${isDemo ? "Historial ilustrativo" : "Ordenados del más reciente al más antiguo"}</p></div><span class="badge badge-muted">${state.flows.length}</span></div>
        ${flowsListHtml()}
      </section>` + footer();
  }

  // ---- Mi diario ----
  function renderDiario() {
    main.innerHTML = intro(
      "TU PROCESO TAMBIÉN CUENTA",
      "Mi diario.",
      "El resultado cuenta una parte. Tus razones cuentan el resto."
    ) + `
      <div class="journal-layout">
        <section class="card journal-form">
          <span class="eyebrow">UNA DECISIÓN CONSCIENTE</span>
          <h2 style="margin-top:8px">Escribe antes de actuar</h2>
          <p class="subtext" style="margin-top:8px">Tu yo del futuro agradecerá saber por qué decidiste esto.</p>
          <form class="form-stack" id="form-journal">
            <div class="field-pair">
              <label class="field-label">Activo<input class="field" id="journal-ticker" value="${escapeHtml(state.journalTicker)}" placeholder="Ticker" maxlength="10"/></label>
              <label class="field-label">Decisión
                <select class="field" id="journal-action">
                  <option ${state.journalAction === "Comprar" ? "selected" : ""}>Comprar</option>
                  <option ${state.journalAction === "Vender" ? "selected" : ""}>Vender</option>
                  <option ${state.journalAction === "Mantener" ? "selected" : ""}>Mantener</option>
                  <option ${state.journalAction === "Observar" ? "selected" : ""}>Observar</option>
                </select>
              </label>
            </div>
            <label class="field-label">¿Cuál es tu tesis?<textarea class="field" id="journal-thesis" placeholder="Creo que… porque…">${escapeHtml(state.journalThesis)}</textarea></label>
            <label class="field-label">¿Cuál es el riesgo principal?<textarea class="field" id="journal-risk" placeholder="Podría estar equivocado si…">${escapeHtml(state.journalRisk)}</textarea></label>
            <label class="field-label">¿Qué invalidaría tu idea?<textarea class="field" id="journal-invalidation" placeholder="Cambiaría de opinión cuando…">${escapeHtml(state.journalInvalidation)}</textarea></label>
            <button class="btn btn-primary" type="submit">Guardar reflexión ${icon("arrow")}</button>
          </form>
        </section>
        <aside class="quote-card"><div class="quote-mark">“</div><blockquote>Una buena decisión no siempre lleva a un buen resultado. Y un buen resultado no siempre significa que decidiste bien.</blockquote><span>SEPARA EL PROCESO DE LA SUERTE</span></aside>
      </div>

      <section class="card mt-24" aria-label="Decisiones anteriores">
        <div class="section-header"><div class="section-title"><h2>Decisiones anteriores</h2><p class="small muted">Mira hacia atrás para avanzar.</p></div><span class="badge badge-muted">${state.entries.length} ${state.entries.length === 1 ? "ENTRADA" : "ENTRADAS"}</span></div>
        <div class="entry-list">
          ${state.entries.length ? state.entries.map(e => `
            <article class="entry-row">
              <span class="entry-date">${escapeHtml(e.date)}</span>
              <div>
                <div class="entry-title"><strong>${escapeHtml(e.ticker)}</strong>${badge(e.action.toUpperCase(), e.action === "Comprar" ? "green" : e.action === "Vender" ? "red" : "muted")}${e.amount > 0 ? `<span class="small muted">${privateText(money(e.amount))}</span>` : ""}</div>
                <p>${escapeHtml(e.thesis)}</p>
                <small class="entry-meta"><b>Riesgo:</b> ${escapeHtml(e.risk)}</small>
                <small class="entry-meta"><b>Invalidación:</b> ${escapeHtml(e.invalidation)}</small>
                ${e.lesson ? `<small class="entry-meta"><b>Aprendizaje:</b> ${escapeHtml(e.lesson)}</small>` : ""}
                ${state.journalReviewId === e.id ? `
                  <div class="review-box">
                    <label>¿Qué aprendiste? ¿Fue proceso o suerte?<textarea class="field" id="review-lesson" placeholder="Mi aprendizaje…">${escapeHtml(state.journalLesson)}</textarea></label>
                    <button type="button" class="btn btn-primary" data-action="save-review" id="btn-save-review" ${!state.journalLesson.trim() ? "disabled" : ""}>Guardar evaluación</button>
                  </div>` : `
                  <button type="button" class="btn btn-plain" data-action="eval-entry" data-eval-id="${e.id}">Evaluar esta decisión ${icon("arrow","icon-sm")}</button>`}
              </div>
            </article>`).join("") : `<div class="empty-state" style="border:0">${icon("book")}<h2>Todavía no hay decisiones escritas.</h2><p>Tu primera reflexión puede empezar arriba, o desde un análisis guardado.</p></div>`}
        </div>
      </section>` + footer();
  }

  // ---- Ajustes ----
  function renderAjustes() {
    const conflict = Number(state.settingsLimit) < 100 / (Number(state.settingsPositions) || 1);
    const isDemo = isDemoMode();
    main.innerHTML = intro(
      "TU PLAN, TUS REGLAS",
      "Ajustes.",
      "Define los límites que te ayudan a decidir a tu manera."
    ) + `
      <section class="card section-pad" aria-label="Perfil de inversión">
        <span class="eyebrow">TU PUNTO DE PARTIDA</span>
        <h2 style="margin:8px 0 20px">Perfil de inversión</h2>
        <div class="settings-row"><div><h3>Tolerancia al riesgo</h3><p>Elige lo que mejor describe cómo te sientes ante las fluctuaciones.</p></div>
          <select class="sort-select" id="settings-risk" aria-label="Tolerancia al riesgo">
            <option value="conservador" ${state.settingsRisk === "conservador" ? "selected" : ""}>Conservador</option>
            <option value="moderado" ${state.settingsRisk === "moderado" ? "selected" : ""}>Moderado</option>
            <option value="agresivo" ${state.settingsRisk === "agresivo" ? "selected" : ""}>Agresivo</option>
          </select></div>
        <div class="settings-row"><div><h3>Máximo por empresa</h3><p>Evita que una sola posición domine tu cartera.</p></div>
          <div class="settings-number"><input type="number" min="1" max="100" id="settings-limit" value="${escapeHtml(state.settingsLimit)}" aria-label="Máximo por empresa en porcentaje"/>%</div></div>
        <div class="settings-row"><div><h3>Posiciones objetivo</h3><p>El número de activos que quieres mantener aproximadamente.</p></div>
          <div class="settings-number"><input type="number" min="1" max="100" id="settings-positions" value="${escapeHtml(state.settingsPositions)}" aria-label="Número de posiciones objetivo"/></div></div>
        ${conflict ? `<div class="settings-warning">Con ${escapeHtml(state.settingsPositions)} posiciones, un límite de ${escapeHtml(state.settingsLimit)}% no permite distribuir el 100% de la cartera. Considera ajustar uno de los valores.</div>` : ""}
        <div class="settings-save"><button type="button" class="btn btn-primary" data-action="save-settings">Guardar preferencias ${icon("arrow")}</button>${state.settingsSaved ? `<span>${icon("check","icon-sm")} Guardado</span>` : ""}</div>
      </section>

      <section class="card section-pad mt-24" aria-label="Sobre tus datos">
        <span class="eyebrow">TRANSPARENCIA PRIMERO</span>
        <h2 style="margin:8px 0 20px">Sobre tus datos</h2>
        <div class="settings-row"><div><h3>${isDemo ? "Datos ilustrativos, siempre identificados" : "Datos guardados, siempre con fuente"}</h3><p>${isDemo ? "En modo demo, las cifras no pertenecen a una cuenta real. Un error de servidor nunca se reemplaza silenciosamente por datos ficticios." : "Las cifras provienen de tus datos guardados y de Yahoo/SEC con fecha. Si un dato falta, se marca «Sin dato»."}</p></div>${badge(isDemo ? "MODO DEMO" : "DATOS REALES", isDemo ? "demo" : "green")}</div>
        <div class="settings-row"><div><h3>Conexión con el backend</h3><p>${isDemo ? "Las acciones de esta demo se mantienen solo en esta sesión." : "Conectado al backend local: los cambios se guardan en tu base de datos."}</p></div>${badge(state.connected ? "CONECTADO" : "MODO LOCAL", state.connected ? "green" : "muted")}</div>
      </section>

      ${isDemo ? `
        <section class="danger-zone"><div><span class="eyebrow">ZONA DE CONTROL</span><h2>Volver a empezar</h2><p>Restablece todos los datos de demostración a su estado inicial.</p></div><button type="button" class="btn btn-danger" data-action="open-reset">Restablecer demo</button></section>
      ` : `
        <section class="danger-zone" style="border-color:var(--border)"><div><span class="eyebrow" style="color:var(--muted)">ZONA DE CONTROL</span><h2>Actualizar tus datos</h2><p>Vuelve a leer la cartera, el marcador y el diario desde el backend local.</p></div><button type="button" class="btn" data-action="refresh-data">${icon("refresh")}Actualizar datos</button></section>
      `}` + footer();
  }

  // ---- Diálogos ----
  const openDialog = (title, content) => {
    document.getElementById("dialog-title").textContent = title;
    dialogBody.innerHTML = content;
    hydrateIcons(dialogBody);
    applyPrivacy();
    if (!dialog.open) dialog.showModal();
  };

  function openPosition(ticker) {
    const a = state.assets.find(item => item.ticker === ticker);
    if (!a) return;
    const value = round(a.shares * a.price), gain = round(value - a.cost);
    const isDemo = isDemoMode();
    const statusTag = isDemo ? badge("HECHO · DEMO", "demo") : (a.priceStatus === "actual" || a.priceStatus === "reciente" ? badge("HECHO", "green") : badge("POR VERIFICAR", "demo"));
    openDialog("Detalle del activo", `
      ${assetLabel(a.ticker, a.name, monoTone(a.ticker, a.type || assetType(a.ticker)))}
      <span class="badge ${a.type === "ETF" ? "badge-purple" : "badge-blue"}">${a.type || assetType(a.ticker)}</span>
      <dl class="detail-metrics">
        <div class="detail-metric"><dt>Precio utilizado</dt><dd>${privateText(money(a.price))}</dd></div>
        <div class="detail-metric"><dt>Resultado de la posición</dt><dd class="${gain >= 0 ? "positive" : "negative"}">${privateText((gain >= 0 ? "+" : "−") + money(Math.abs(gain)))}</dd></div>
        <div class="detail-metric"><dt>En la cartera</dt><dd>${a.shares} unidades</dd></div>
        <div class="detail-metric"><dt>Valor de la posición</dt><dd>${privateText(money(value))}</dd></div>
      </dl>
      <table class="data-table"><tbody>
        <tr><th>Costo registrado</th><td>${a.cost ? privateText(money(a.cost)) : "Sin dato"}</td></tr>
        <tr><th>Origen y fecha</th><td>${a.priceFuente ? escapeHtml(a.priceFuente) + (a.priceAsof ? " · " + String(a.priceAsof).slice(0,10) : "") : "Referencia ilustrativa"}</td></tr>
        <tr><th>Estado</th><td>${isDemo ? "Sincronización por verificar" : (a.verified ? "Verificado por ti" : "Pendiente de verificación")}</td></tr>
      </tbody></table>
      <p class="detail-flag">${icon("info")} Los niveles ATR requieren precios de mercado verificados. ${statusTag}</p>
      <div class="dialog-actions"><button class="btn" data-action="watch" data-ticker="${escapeHtml(a.ticker)}" aria-pressed="${state.watched.has(a.ticker)}">${icon(state.watched.has(a.ticker) ? "check" : "star")}${state.watched.has(a.ticker) ? "En seguimiento" : "Añadir a seguimiento"}</button><button class="btn btn-primary" data-action="analyze" data-ticker="${escapeHtml(a.ticker)}">${icon("sliders")}Simular decisión</button><button class="btn" data-action="prompt" data-prompt="¿Qué me puedes decir de ${escapeHtml(a.ticker)} en mi cartera?">${icon("sparkles")}Preguntar a Luna</button></div>`);
  }

  function openRadarAsset(ticker) {
    const r = state.radar.find(item => item.ticker === ticker) || watchPool().find(item => item.ticker === ticker);
    if (!r) return;
    const type = assetType(ticker, r.sector || "");
    openDialog("Detalle del activo", `
      ${assetLabel(ticker, r.name, monoTone(ticker, type))}
      <span class="badge ${type === "ETF" ? "badge-purple" : "badge-blue"}">${type}</span>
      ${r.verdict ? ` <span class="badge ${r.tone === "green" ? "badge-green" : r.tone === "orange" ? "badge-demo" : "badge-muted"}">${escapeHtml(r.verdict)}</span>` : ""}
      <dl class="detail-metrics">
        <div class="detail-metric"><dt>Precio de referencia</dt><dd>${privateText(r.price || "Sin dato")}</dd></div>
        <div class="detail-metric"><dt>Sector</dt><dd style="font-size:16px">${escapeHtml(r.sector || "Sin clasificar")}</dd></div>
      </dl>
      ${r.note ? `<p class="detail-note">${escapeHtml(r.note)}</p>` : ""}
      <p class="detail-note">El veredicto es una invitación a hacer mejores preguntas, no una recomendación de compra o venta.</p>
      <div class="dialog-actions"><button class="btn" data-action="watch" data-ticker="${escapeHtml(ticker)}" aria-pressed="${state.watched.has(ticker)}">${icon(state.watched.has(ticker) ? "check" : "star")}${state.watched.has(ticker) ? "En seguimiento" : "Añadir a seguimiento"}</button><button class="btn btn-primary" data-action="analyze" data-ticker="${escapeHtml(ticker)}">${icon("sliders")}Simular decisión</button><button class="btn" data-action="prompt" data-prompt="¿Qué me puedes decir de ${escapeHtml(ticker)}?">${icon("sparkles")}Preguntar a Luna</button></div>`);
  }

  function searchResults(query) {
    const normalized = String(query || "").trim().toLocaleLowerCase("es");
    const list = watchPool().filter(a => `${a.ticker} ${a.name}`.toLocaleLowerCase("es").includes(normalized)).slice(0, 6);
    const host = document.getElementById("quick-results");
    if (!host) return;
    host.innerHTML = list.length ? list.map(a => `<button class="quick-result" data-action="${a.src === "posicion" ? "asset" : "radar-asset"}" data-ticker="${escapeHtml(a.ticker)}" aria-label="Ver detalle de ${escapeHtml(a.ticker)}, ${escapeHtml(a.name)}">${assetLabel(a.ticker, a.name, monoTone(a.ticker, a.type || assetType(a.ticker)))}<span class="quick-result-price">${privateText(a.price)}</span></button>`).join("") : `<p class="muted small" role="status" style="padding:16px 0">No hay coincidencias entre tus posiciones y el radar.</p>`;
    applyPrivacy();
  }

  const openSearch = () => {
    openDialog("Buscar un activo", `<label class="search-dialog-label" for="global-search">Nombre o ticker del activo</label><input class="field" id="global-search" type="search" placeholder="Por ejemplo, VOO o Microsoft…" maxlength="80" autocomplete="off"><div class="quick-results" id="quick-results"></div><p class="detail-note">Busca entre tus posiciones y los activos del radar.</p>`);
    searchResults("");
    document.getElementById("global-search").focus();
  };

  const about = () => openDialog("Criterio con datos, no adivinanzas", `
    <span class="badge ${isDemoMode() ? "badge-demo" : "badge-green"}">${isDemoMode() ? "Modo demostración" : "Conectado al backend local"}</span>
    <p>Hapi IA te ayuda a pensar mejor tus decisiones de inversión. Propone y registra; nunca ejecuta operaciones en tu bróker.</p>
    <ul class="about-list">
      <li><strong>Cifras:</strong> todo dato lleva fuente y fecha. Si falta, se marca «Sin dato»; nunca se inventa.</li>
      <li><strong>Precios:</strong> Yahoo Finance o ingreso manual con tu verificación. Si Yahoo falla, se te avisa.</li>
      <li><strong>Fundamentales:</strong> reportes 10-K desde SEC EDGAR, sin mezclar presentaciones.</li>
      <li><strong>Luna:</strong> la asistente explica y cuestiona; no recomienda comprar ni vender ni predice precios.</li>
      <li><strong>Privacidad:</strong> tema, seguimiento y ocultación se guardan solo en este navegador. La conversación no se guarda.</li>
    </ul>
    <div class="notice">${icon("shield")}<p>Nada de lo que ves es asesoría financiera ni una orden. Tú decides y operas en tu bróker.</p></div>`);

  const openReset = () => openDialog("¿Restablecer la demostración?", `
    <div class="detail-flag"><span class="ai-avatar">${icon("refresh")}</span><p style="margin:0">Se restaurarán la cartera, el diario, los movimientos y la alcancía a sus valores iniciales. Esto no afecta ninguna cuenta real.</p></div>
    <div class="dialog-actions"><button class="btn" data-action="close-dialog">Cancelar</button><button class="btn btn-danger" data-action="confirm-reset">Restablecer datos</button></div>`);

  // ---- Utilidades de vista ----
  const toast = text => {
    clearTimeout(toastTimer);
    document.getElementById("toast-text").textContent = text;
    document.getElementById("toast").classList.add("show");
    toastTimer = setTimeout(() => document.getElementById("toast").classList.remove("show"), 5500);
  };

  const applyTheme = () => {
    document.documentElement.dataset.theme = state.theme;
    document.querySelector('meta[name="theme-color"]').content = state.theme === "dark" ? "#171c19" : "#102c26";
    document.getElementById("theme-label").textContent = state.theme === "dark" ? "Tema claro" : "Tema oscuro";
    document.getElementById("theme-button").querySelector("[data-icon]").dataset.icon = state.theme === "dark" ? "sun" : "moon";
    hydrateIcons(document.getElementById("theme-button"));
  };

  function applyPrivacy() {
    document.querySelectorAll("[data-private]").forEach(el => {
      el.textContent = state.private ? "••••" : el.dataset.value;
      if (state.private) el.setAttribute("aria-label", "Importe oculto"); else el.removeAttribute("aria-label");
    });
    document.querySelectorAll('[data-action="privacy"]').forEach(el => {
      el.setAttribute("aria-pressed", String(state.private));
      el.setAttribute("aria-label", `${state.private ? "Mostrar" : "Ocultar"} importes`);
      if (el.id === "privacy-button") el.innerHTML = icon(state.private ? "eyeoff" : "eye");
      else if (el.closest(".intro-actions")) el.innerHTML = `${icon(state.private ? "eyeoff" : "eye")}<span>${state.private ? "Mostrar" : "Ocultar"} importes</span>`;
    });
  }

  const refreshWatchButtons = () => {
    document.querySelectorAll('[data-action="watch"]').forEach(btn => {
      const watched = state.watched.has(btn.dataset.ticker);
      btn.setAttribute("aria-pressed", String(watched));
      btn.setAttribute("aria-label", `${watched ? "Quitar" : "Añadir"} ${btn.dataset.ticker} ${watched ? "de" : "a"} seguimiento`);
      if (btn.classList.contains("btn")) btn.innerHTML = `${icon(watched ? "check" : "star")}${watched ? "En seguimiento" : "Añadir a seguimiento"}`;
    });
    const count = document.getElementById("watch-count");
    if (count) count.textContent = `(${state.watched.size})`;
  };

  const toggleWatch = ticker => {
    if (!ticker) return;
    const wasWatched = state.watched.has(ticker);
    wasWatched ? state.watched.delete(ticker) : state.watched.add(ticker);
    const saved = savePreferences();
    refreshWatchButtons();
    if (state.route === "explorar") renderExploreResults();
    if (state.route === "cartera" && state.walletTab === "seguimiento") renderWalletContent();
    toast(`${ticker} ${wasWatched ? "se quitó de" : "se añadió a"} seguimiento.${saved ? " Guardado en este navegador." : " Disponible durante esta sesión."}`);
  };

  const exportCsv = () => {
    const isDemo = isDemoMode();
    const rows = [["Activo","Nombre","Tipo","Unidades","Precio_utilizado_USD","Valor_USD","Costo_USD","Resultado_no_realizado_USD","Origen","Fecha"],
      ...state.assets.map(a => [a.ticker, a.name, a.type || assetType(a.ticker), a.shares, a.price.toFixed(2), (a.shares*a.price).toFixed(2), a.cost.toFixed(2), (a.shares*a.price - a.cost).toFixed(2), a.priceFuente || (isDemo ? "EJEMPLO" : ""), a.priceAsof || ""]),
      ["CASH","Saldo disponible","Efectivo","","", state.cash.toFixed(2),"","", "", ""]];
    const content = "\uFEFF" + rows.map(row => row.map(cell => `"${String(cell).replaceAll('"','""')}"`).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([content], {type:"text/csv;charset=utf-8"}));
    const link = document.createElement("a"); link.href = url; link.download = "hapi-cartera.csv"; link.hidden = true; document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast("CSV de tu cartera preparado. Incluye los importes aunque estén ocultos.");
  };

  // ---- Menú móvil ----
  const setMenuState = () => {
    sidebar.inert = mobileQuery.matches && !menuOpen;
    if (mobileQuery.matches && !menuOpen) sidebar.setAttribute("aria-hidden","true"); else sidebar.removeAttribute("aria-hidden");
    document.getElementById("menu-button").setAttribute("aria-expanded", String(menuOpen));
  };
  const openMenu = () => {
    if (!mobileQuery.matches) return;
    menuOpen = true; document.body.classList.add("sidebar-open"); document.body.style.overflow = "hidden"; setMenuState();
    sidebar.querySelector(".sidebar-close").focus();
  };
  function closeMenu(returnFocus = true) {
    const wasOpen = menuOpen;
    menuOpen = false; document.body.classList.remove("sidebar-open"); document.body.style.overflow = ""; setMenuState();
    if (returnFocus && wasOpen) document.getElementById("menu-button").focus();
  }

  // ---- Enrutado ----
  const aliases = {inicio:"resumen", hoy:"resumen", cartera:"cartera", portfolio:"cartera", oportunidades:"explorar", radar:"explorar", asistente:"asistente", luna:"asistente", analisis:"analisis", operar:"analisis", diario:"diario", historial:"diario", ajustes:"ajustes", perfil:"ajustes", config:"ajustes", movimientos:"movimientos", flows:"movimientos"};
  function routeFromHash() {
    const rawHash = (location.hash || "").replace(/^#/, "").split("?")[0];
    const [raw, arg = ""] = rawHash.split("/");
    const page = Object.hasOwn(routeLabels, raw) ? raw : (aliases[raw] || "resumen");
    return {page, arg};
  }

  const views = {resumen:renderResumen, cartera:renderCartera, analisis:renderAnalisis, explorar:renderExplorar, asistente:renderAsistente, movimientos:renderMovimientos, diario:renderDiario, ajustes:renderAjustes};

  let lastRouteKey = "";
  const renderRoute = (focus = false) => {
    const r = routeFromHash();
    state.route = r.page;
    const routeKey = `${r.page}/${r.arg}`;
    if (routeKey !== lastRouteKey) {
      lastRouteKey = routeKey;
      if (r.arg) { state.analysisTicker = r.arg.toUpperCase(); state.analysisShow = false; }
    }
    if (state.loading) {
      main.innerHTML = `<div class="connection"><div class="connection-icon"><span class="spin" style="display:grid">${icon("refresh","icon-lg")}</span></div><h1>Cargando tu espacio…</h1><p>Conectando con tus datos locales.</p></div>`;
      return;
    }
    // Conservar foco y caret entre repintados para que escribir no se sienta inestable.
    const prev = document.activeElement;
    const focusId = prev && prev.id && main.contains(prev) ? prev.id : "";
    const sel = focusId && typeof prev.selectionStart === "number" ? [prev.selectionStart, prev.selectionEnd] : null;

    views[state.route]();
    hydrateIcons(main);
    document.getElementById("crumb-current").textContent = routeLabels[state.route];
    document.querySelectorAll(".nav-link,[data-route].side-action").forEach(a => {
      if (a.dataset.route === state.route) a.setAttribute("aria-current","page"); else a.removeAttribute("aria-current");
    });
    document.title = `${routeLabels[state.route]} · Hapi IA`;
    applyPrivacy();
    closeMenu(false);
    if (focus) { window.scrollTo({top:0, behavior:"auto"}); main.focus({preventScroll:true}); }
    else if (focusId) {
      const el = document.getElementById(focusId);
      if (el) {
        el.focus({preventScroll:true});
        if (sel && typeof el.setSelectionRange === "function") {
          try { el.setSelectionRange(Math.min(sel[0], el.value.length), Math.min(sel[1], el.value.length)); } catch (e) { /* inputs numéricos sin caret */ }
        }
      }
    }
  };

  const navigate = (route, arg = "") => {
    const hash = `#${route}${arg ? "/" + arg : ""}`;
    if (location.hash === hash) renderRoute(true); else location.hash = route + (arg ? "/" + arg : "");
  };

  // ---- Acciones con persistencia ----
  async function saveJournalEntry(entry) {
    if (!state.connected) return;
    try {
      const res = await fetch("/api/journal", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ticker: entry.ticker, action: String(entry.action || "revision").toLowerCase(), tesis: entry.thesis, riesgos: entry.risk, condicion_invalidacion: entry.invalidation}),
      });
      if (res.ok) {
        const data = await res.json();
        if (data && data.id) entry.id = data.id;
      }
    } catch (err) {
      console.warn("No se pudo guardar la entrada del diario:", err);
    }
  }

  async function saveSavingsDraft() {
    const n = state.homeDraft;
    state.savings += n;
    state.homeDraft = null;
    state.homeSavingText = "";
    toast("Aporte registrado en tu alcancía.");
    if (state.connected) {
      try {
        const dRes = await fetch("/api/flows/draft", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({text:`guarde ${n} soles`})});
        if (dRes.ok) {
          const draftData = await dRes.json();
          if (Array.isArray(draftData.rows) && draftData.rows.length) {
            await fetch("/api/flows/confirm", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({rows: draftData.rows, reviewed: true})});
            const fRes = await fetch("/api/flows").catch(() => null);
            if (fRes && fRes.ok) { const fd = await fRes.json(); if (fd && Array.isArray(fd.rows)) state.flows = fd.rows; }
            const mRes = await fetch("/api/marcador").catch(() => null);
            if (mRes && mRes.ok) state.serverMarcador = await mRes.json();
          }
        }
      } catch (err) {
        console.warn("Error guardando flujo en backend:", err);
      }
    }
    renderRoute();
  }

  function demoFlowDraft(text) {
    const t = text.toLowerCase();
    const m = text.replace(",", ".").match(/\d+(?:\.\d{1,2})?/);
    const today = new Date().toISOString().slice(0, 10);
    const rows = [];
    if (!m || Number(m[0]) <= 0) return null;
    if (/ahorr|guard/.test(t)) rows.push({kind:"ahorro_soles", soles_amount:Number(m[0]), amount_usd:null, at:today, source:"texto"});
    else if (/deposit|abon|ingres/.test(t)) rows.push({kind:"deposito", amount_usd:Number(m[0]), soles_amount:null, at:today, source:"texto"});
    else if (/retir/.test(t)) rows.push({kind:"retiro", amount_usd:Number(m[0]), soles_amount:null, at:today, source:"texto"});
    else if (/dividend/.test(t)) rows.push({kind:"dividendo", amount_usd:Number(m[0]), soles_amount:null, at:today, source:"texto"});
    else return null;
    return {rows, omitted: []};
  }

  async function requestFlowDraft() {
    const text = state.flowText.trim();
    if (!text) return;
    state.flowBusy = true;
    if (isDemoMode()) {
      const d = demoFlowDraft(text);
      state.flowBusy = false;
      if (d) { state.flowDraft = d; state.flowReviewed = false; state.flowAllowDup = false; }
      else toast("No entendí el movimiento. Prueba con «guardé 80 soles» o «deposité 100».");
      renderRoute();
      return;
    }
    try {
      const res = await fetch("/api/flows/draft", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({text})});
      const data = await res.json().catch(() => ({}));
      if (res.ok && Array.isArray(data.rows) && data.rows.length) {
        state.flowDraft = {rows: data.rows, omitted: data.omitted || []};
        state.flowReviewed = false;
        state.flowAllowDup = false;
      } else {
        const msg = data && data.detail && typeof data.detail === "object" ? (data.detail.message || "") : (typeof data.detail === "string" ? data.detail : "");
        toast(msg || "No entendí el mensaje. Cuéntalo en una frase o pega tu historial.");
      }
    } catch (err) {
      console.warn("Error pidiendo borrador:", err);
      toast("No se pudo preparar el borrador. Inténtalo de nuevo.");
    }
    state.flowBusy = false;
    renderRoute();
  }

  async function confirmFlowDraft() {
    if (!state.flowDraft) return;
    state.flowBusy = true;
    if (isDemoMode()) {
      const nextId = Math.max(0, ...state.flows.map(f => f.id || 0)) + 1;
      const rows = state.flowDraft.rows.map((r, i) => ({...r, id: nextId + i}));
      state.flows = [...rows, ...state.flows];
      const saved = rows.reduce((s, r) => s + (r.kind === "ahorro_soles" ? (r.soles_amount || 0) : 0), 0);
      if (saved) state.savings += saved;
      state.flowDraft = null; state.flowText = ""; state.flowBusy = false;
      toast("Movimiento registrado en esta sesión de demostración.");
      renderRoute();
      return;
    }
    try {
      const res = await fetch("/api/flows/confirm", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({rows: state.flowDraft.rows, reviewed: true, allow_duplicates: state.flowAllowDup})});
      const data = await res.json().catch(() => ({}));
      if (res.ok) {
        state.flowDraft = null; state.flowText = ""; state.flowBusy = false;
        toast(`Se ${data.imported === 1 ? "guardó 1 movimiento" : `guardaron ${data.imported} movimientos`}.`);
        const [fRes, mRes] = await Promise.all([fetch("/api/flows").catch(() => null), fetch("/api/marcador").catch(() => null)]);
        if (fRes && fRes.ok) { const fd = await fRes.json(); if (fd && Array.isArray(fd.rows)) state.flows = fd.rows; }
        if (mRes && mRes.ok) state.serverMarcador = await mRes.json();
        if (state.serverMarcador && state.serverMarcador.alcancia && typeof state.serverMarcador.alcancia.progreso === "number") state.savings = state.serverMarcador.alcancia.progreso;
        renderRoute();
        return;
      }
      if (res.status === 400 && data && data.detail && Array.isArray(data.detail.duplicates)) {
        state.flowAllowDup = true;
        toast("Hay duplicados: confirma la casilla para guardarlos igualmente.");
      } else {
        toast("No se pudo guardar. Revisa el mensaje e inténtalo de nuevo.");
      }
    } catch (err) {
      console.warn("Error confirmando flujo:", err);
      toast("No se pudo guardar el movimiento.");
    }
    state.flowBusy = false;
    renderRoute();
  }

  async function deleteFlow(id) {
    if (isDemoMode()) {
      state.flows = state.flows.filter(f => f.id !== id);
      toast("Movimiento eliminado de esta sesión.");
      renderRoute();
      return;
    }
    try {
      const res = await fetch(`/api/flows/${id}`, {method:"DELETE"});
      if (res.ok) {
        state.flows = state.flows.filter(f => f.id !== id);
        const mRes = await fetch("/api/marcador").catch(() => null);
        if (mRes && mRes.ok) state.serverMarcador = await mRes.json();
        toast("Movimiento eliminado.");
      } else {
        toast("No se pudo eliminar el movimiento.");
      }
    } catch (err) {
      console.warn("Error eliminando flujo:", err);
      toast("No se pudo eliminar el movimiento.");
    }
    renderRoute();
  }

  async function saveSync() {
    const ticker = state.portfolioTicker;
    const shares = Number(state.portfolioShares);
    const price = Number(state.portfolioPrice);
    let persisted = false;
    if (state.connected) {
      try {
        const res = await fetch("/api/positions", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ticker, qty: shares, avg_cost: price, invested: shares * price, source: "manual"})});
        if (!res.ok) throw new Error("HTTP " + res.status);
        if (state.portfolioReplace) {
          await Promise.all(state.assets.filter(a => a.ticker !== ticker).map(a => fetch("/api/positions/" + encodeURIComponent(a.ticker), {method:"DELETE"})));
        }
        persisted = true;
      } catch (err) {
        console.warn("No se pudo guardar la posición:", err);
      }
    }
    const asset = {ticker, name: ticker + " · posición importada", shares, price, cost: shares * price, color:"#b7c5a9", change:0, priceStatus:"sin_precio", priceFuente: persisted ? "manual" : "", priceAsof:"", verified: persisted, type: assetType(ticker)};
    if (state.portfolioReplace) state.assets = [asset];
    else state.assets = [...state.assets.filter(a => a.ticker !== ticker), asset];
    Object.assign(state, {portfolioSync:false, portfolioTicker:"", portfolioShares:"", portfolioPrice:"", portfolioChecked:false, portfolioReplace:false, portfolioConfirmReplace:false, portfolioFileName:""});
    toast(persisted ? "Cartera guardada en tu base de datos." : "Cartera actualizada solo en esta sesión.");
    renderRoute();
  }

  async function saveAnalysisJournal() {
    const entry = {id: Date.now(), ticker: state.analysisTicker.toUpperCase(), action: state.analysisSide, amount: Number(state.analysisAmount) || 0, thesis: state.analysisThesis, risk: state.analysisRisk, invalidation: state.analysisInvalidation, date: "Hoy"};
    state.entries = [entry, ...state.entries];
    await saveJournalEntry(entry);
    toast("Decisión guardada en tu diario.");
    navigate("diario");
  }

  async function saveReview() {
    const id = state.journalReviewId;
    const leccion = state.journalLesson;
    const entry = state.entries.find(e2 => e2.id === id);
    if (entry) entry.lesson = leccion;
    state.journalReviewId = null;
    state.journalLesson = "";
    if (state.connected && typeof id === "number") {
      try {
        await fetch("/api/journal/" + id + "/evaluate", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({leccion})});
      } catch (err) {
        console.warn("No se pudo guardar la evaluación:", err);
      }
    }
    toast(state.connected ? "Evaluación guardada en tu diario." : "Evaluación registrada para esta sesión.");
    renderRoute();
  }

  async function saveSettings() {
    state.settingsSaved = true;
    if (state.connected) {
      try {
        const lim = Number(state.settingsLimit);
        const calls = [fetch("/api/profile", {method:"PUT", headers:{"Content-Type":"application/json"}, body: JSON.stringify({nivel_riesgo: state.settingsRisk})})];
        if (lim > 0) calls.push(fetch("/api/limits", {method:"PUT", headers:{"Content-Type":"application/json"}, body: JSON.stringify({max_position_pct: lim})}));
        await Promise.all(calls);
        toast("Preferencias guardadas en tu base de datos.");
        renderRoute();
        return;
      } catch (err) {
        console.warn("No se pudieron guardar los ajustes:", err);
      }
    }
    toast("Preferencias guardadas para esta sesión de demostración.");
    renderRoute();
  }

  function confirmReset() {
    state.assets = JSON.parse(JSON.stringify(initialAssets));
    state.entries = JSON.parse(JSON.stringify(initialEntries));
    state.radar = JSON.parse(JSON.stringify(radarUniverse));
    state.flows = [];
    state.savings = 1240;
    state.cash = 0;
    if (dialog.open) dialog.close();
    toast("Datos de demostración restablecidos.");
    renderRoute();
  }

  // ---- Delegación de eventos ----
  document.querySelector(".skip-link").addEventListener("click", event => {
    event.preventDefault();
    main.focus({preventScroll:true});
    main.scrollIntoView({block:"start", behavior:"auto"});
  });

  document.addEventListener("click", event => {
    const currentLink = event.target.closest(".nav-link");
    if (currentLink && currentLink.dataset.route === state.route) { closeMenu(false); main.focus({preventScroll:true}); }
    const el = event.target.closest("[data-action]");
    if (!el || el.disabled) return;
    switch (el.dataset.action) {
      case "menu": openMenu(); break;
      case "close-menu": closeMenu(); break;
      case "theme": state.theme = state.theme === "light" ? "dark" : "light"; savePreferences(); applyTheme(); break;
      case "about": closeMenu(false); about(); break;
      case "search": openSearch(); break;
      case "privacy": state.private = !state.private; savePreferences(); applyPrivacy(); if (state.route === "asistente") renderMessages(); break;
      case "export": exportCsv(); break;
      case "asset": if (dialog.open) dialog.close(); openPosition(el.dataset.ticker); break;
      case "radar-asset": if (dialog.open) dialog.close(); openRadarAsset(el.dataset.ticker); break;
      case "watch": toggleWatch(el.dataset.ticker); break;
      case "analyze": if (dialog.open) dialog.close(); navigate("analisis", el.dataset.ticker); break;
      case "prompt": if (dialog.open) dialog.close(); state.pendingPrompt = el.dataset.prompt; navigate("asistente"); break;
      case "goto": navigate(el.dataset.route); break;
      case "close-dialog": dialog.close(); break;
      case "close-toast": document.getElementById("toast").classList.remove("show"); clearTimeout(toastTimer); break;

      case "filter": state.filter = el.dataset.filter; renderExploreResults(); break;
      case "clear-filters": { state.filter = "todos"; state.query = ""; const s = document.getElementById("explore-search"); if (s) s.value = ""; renderExploreResults(); break; }
      case "wallet-tab": state.walletTab = el.dataset.walletTab; renderWalletContent(); break;
      case "chat-prompt": sendQuestion(el.dataset.prompt); break;

      case "start-sync": state.portfolioSync = true; renderRoute(); setTimeout(() => { const s = document.getElementById("sync"); if (s) s.scrollIntoView({behavior:"smooth"}); }, 40); break;
      case "start-import": state.portfolioSync = true; state.walletTab = "posiciones"; renderRoute(); setTimeout(() => { const s = document.getElementById("sync"); if (s) s.scrollIntoView({behavior:"smooth"}); }, 40); break;
      case "sync-tab": state.portfolioSync = el.dataset.tab === "importar"; renderRoute(); break;
      case "trigger-upload": { const f = document.getElementById("file-capture"); if (f) f.click(); break; }
      case "save-sync": saveSync(); break;
      case "add-cash": state.cash += 50; toast("Se agregaron $50.00 de efectivo de demostración."); renderRoute(); break;

      case "side": state.analysisSide = el.dataset.side; state.analysisShow = false; renderRoute(); break;
      case "amount": state.analysisAmount = el.dataset.amt; state.analysisShow = false; renderRoute(); break;
      case "save-analysis-journal": saveAnalysisJournal(); break;

      case "cancel-savings-draft": state.homeDraft = null; renderRoute(); break;
      case "save-savings-draft": saveSavingsDraft(); break;

      case "cancel-flow-draft": state.flowDraft = null; state.flowReviewed = false; state.flowAllowDup = false; renderRoute(); break;
      case "confirm-flow-draft": confirmFlowDraft(); break;
      case "delete-flow": deleteFlow(Number(el.dataset.id)); break;

      case "eval-entry": state.journalReviewId = Number(el.dataset.evalId); state.journalLesson = ""; renderRoute(); break;
      case "save-review": saveReview(); break;

      case "save-settings": saveSettings(); break;
      case "refresh-data": state.loading = true; renderRoute(); loadServerData(); break;
      case "open-reset": openReset(); break;
      case "confirm-reset": confirmReset(); break;
    }
  });

  document.addEventListener("input", event => {
    const t = event.target;
    if (t.id === "explore-search") { state.query = t.value; renderExploreResults(); }
    else if (t.id === "global-search") searchResults(t.value);
    else if (t.id === "chat-input") {
      document.getElementById("chat-send").disabled = !t.value.trim();
      t.style.height = "44px"; t.style.height = `${Math.min(t.scrollHeight, 144)}px`;
    }
    else if (t.id === "input-savings") state.homeSavingText = t.value;
    else if (t.id === "flow-text") state.flowText = t.value;
    else if (t.id === "sync-ticker") { state.portfolioTicker = t.value.toUpperCase(); renderRoute(); }
    else if (t.id === "sync-shares") { state.portfolioShares = t.value; renderRoute(); }
    else if (t.id === "sync-price") { state.portfolioPrice = t.value; renderRoute(); }
    else if (t.id === "analysis-ticker") { state.analysisTicker = t.value.toUpperCase(); state.analysisShow = false; renderRoute(); }
    else if (t.id === "analysis-amount") { state.analysisAmount = t.value; state.analysisShow = false; renderRoute(); }
    else if (t.id === "journal-ticker") state.journalTicker = t.value.toUpperCase();
    else if (t.id === "journal-thesis") state.journalThesis = t.value;
    else if (t.id === "journal-risk") state.journalRisk = t.value;
    else if (t.id === "journal-invalidation") state.journalInvalidation = t.value;
    else if (t.id === "result-thesis") { state.analysisThesis = t.value; const b = document.getElementById("btn-save-analysis-journal"); if (b) b.disabled = !(state.analysisThesis.trim() && state.analysisRisk.trim() && state.analysisInvalidation.trim()); }
    else if (t.id === "result-risk") { state.analysisRisk = t.value; const b = document.getElementById("btn-save-analysis-journal"); if (b) b.disabled = !(state.analysisThesis.trim() && state.analysisRisk.trim() && state.analysisInvalidation.trim()); }
    else if (t.id === "result-invalidation") { state.analysisInvalidation = t.value; const b = document.getElementById("btn-save-analysis-journal"); if (b) b.disabled = !(state.analysisThesis.trim() && state.analysisRisk.trim() && state.analysisInvalidation.trim()); }
    else if (t.id === "review-lesson") { state.journalLesson = t.value; const b = document.getElementById("btn-save-review"); if (b) b.disabled = !state.journalLesson.trim(); }
    else if (t.id === "settings-limit") { state.settingsLimit = t.value; state.settingsSaved = false; renderRoute(); }
    else if (t.id === "settings-positions") { state.settingsPositions = t.value; state.settingsSaved = false; renderRoute(); }
  });

  document.addEventListener("change", event => {
    const t = event.target;
    if (t.id === "explore-sort") { state.sort = t.value; renderExploreResults(); }
    else if (t.id === "file-capture") { state.portfolioFileName = t.files && t.files[0] ? t.files[0].name : ""; renderRoute(); }
    else if (t.id === "sync-check") { state.portfolioChecked = t.checked; renderRoute(); }
    else if (t.id === "sync-replace") { state.portfolioReplace = t.checked; state.portfolioConfirmReplace = false; renderRoute(); }
    else if (t.id === "sync-confirm-replace") { state.portfolioConfirmReplace = t.checked; renderRoute(); }
    else if (t.id === "check-savings-reviewed") { state.homeReviewed = t.checked; renderRoute(); }
    else if (t.id === "check-flow-reviewed") { state.flowReviewed = t.checked; renderRoute(); }
    else if (t.id === "check-flow-dup") { state.flowAllowDup = t.checked; renderRoute(); }
    else if (t.id === "journal-action") state.journalAction = t.value;
    else if (t.id === "settings-risk") { state.settingsRisk = t.value; state.settingsSaved = false; renderRoute(); }
  });

  document.addEventListener("submit", event => {
    if (event.target.id === "form-luna") { event.preventDefault(); sendQuestion(document.getElementById("chat-input").value); }
    else if (event.target.id === "form-savings") {
      event.preventDefault();
      const m = state.homeSavingText.replace(",", ".").match(/\d+(?:\.\d{1,2})?/);
      if (m && Number(m[0]) > 0) { state.homeDraft = Number(m[0]); state.homeReviewed = false; renderRoute(); }
    }
    else if (event.target.id === "form-analysis") { event.preventDefault(); state.analysisShow = true; renderRoute(); }
    else if (event.target.id === "form-flow") { event.preventDefault(); requestFlowDraft(); }
    else if (event.target.id === "form-journal") {
      event.preventDefault();
      const ticker = state.journalTicker.toUpperCase();
      if (!/^[A-Z][A-Z0-9.]{0,9}$/.test(ticker)) { toast("Escribe un ticker válido para tu reflexión."); return; }
      if (!state.journalThesis.trim() || !state.journalRisk.trim() || !state.journalInvalidation.trim()) { toast("Completa tesis, riesgo e invalidación."); return; }
      const entry = {id: Date.now(), ticker, action: state.journalAction, amount: 0, thesis: state.journalThesis, risk: state.journalRisk, invalidation: state.journalInvalidation, date: "Hoy"};
      state.entries = [entry, ...state.entries];
      state.journalTicker = ""; state.journalThesis = ""; state.journalRisk = ""; state.journalInvalidation = "";
      saveJournalEntry(entry);
      toast("Reflexión guardada en tu diario.");
      renderRoute();
    }
  });

  document.addEventListener("keydown", event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault(); if (!dialog.open) { closeMenu(false); openSearch(); } return;
    }
    if (event.key === "Enter" && !event.shiftKey && event.target.id === "chat-input" && !event.isComposing) { event.preventDefault(); sendQuestion(event.target.value); return; }
    if (menuOpen && event.key === "Escape") { event.preventDefault(); closeMenu(); return; }
    if (menuOpen && event.key === "Tab") {
      const focusable = [...sidebar.querySelectorAll("a[href],button:not([disabled])")].filter(item => item.getClientRects().length);
      const first = focusable[0], last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });

  dialog.addEventListener("click", event => {
    if (event.target === dialog) {
      const bounds = dialog.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
    }
  });

  window.addEventListener("hashchange", () => renderRoute(true));
  mobileQuery.addEventListener("change", () => closeMenu(false));
  window.addEventListener("storage", event => {
    if (event.key !== storageKey) return;
    const newPrefs = readPreferences();
    if (["light","dark"].includes(newPrefs.theme)) state.theme = newPrefs.theme;
    state.private = newPrefs.private === true;
    if (Array.isArray(newPrefs.watched)) state.watched = new Set(newPrefs.watched.filter(t => typeof t === "string"));
    applyTheme(); applyPrivacy(); refreshWatchButtons();
    if (state.route === "explorar") renderExploreResults();
    if (state.route === "cartera" && state.walletTab === "seguimiento") renderWalletContent();
    if (state.route === "asistente") renderMessages();
  });

  // ---- Arranque ----
  hydrateIcons();
  applyTheme();
  setMenuState();
  renderRoute();
  loadServerData();
})();
