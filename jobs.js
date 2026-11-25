"use strict";
(() => {
  // Use the same origin as the PayPal return URL to preserve session state.
  if (location.hostname === "www.zunpyai.com") {
    location.replace("https://zunpyai.com" + location.pathname + location.search + location.hash);
    return;
  }
  const API = "https://zunpy-jobs-api.onrender.com/v1";
  const STORAGE = "zunpy-job001-sandbox-v1";
  const MAX = 10485760;
  const $ = id => document.getElementById(id);
  const messages = {
    en: {
      start:"Start a test checkout with PayPal Sandbox.",
      creating:"Creating a PayPal Sandbox order…",
      pending:"Approve the payment in PayPal Sandbox, then return here.",
      cancelled:"Checkout was cancelled. No new payment has been requested.",
      capturing:"Verifying your PayPal payment…",
      paid:"Payment verified. Select a fictional invoice PDF.",
      file:"Choose a PDF file of up to 10 MiB.",
      ticket:"Preparing the secure upload…",
      uploading:"Uploading your PDF…",
      validating:"Validating the uploaded PDF…",
      validated:"PDF validated. Ready to process.",
      processing:"Processing your invoice. This can take some time.",
      ready:"Your CSV is ready to download.",
      review:"Your invoice requires review. No CSV is available yet. Contact ZUNPY with the order ID.",
      incomplete:"This order has a pending upload. Select the original PDF to retry, or continue if it has already been uploaded.",
      unknown:"Order status: ",
      expired:"The result is no longer available.",
      unavailable:"This test could not continue. ",
      recovery:"The request may have reached the server. Check the order status before trying again.",
      unsupported:"Session storage is unavailable. Enable it before starting a checkout.",
      returnMismatch:"PayPal returned an order that does not match this tab. No capture was attempted.",
      invalidLink:"The API returned an unexpected URL. The operation was stopped.",
      reset:"Clear this tab's test session? Existing orders are not cancelled or refunded.",
      saved:"Order status: ",
      warming:"The API may be waking up. Keep this tab open."
    },
    es: {
      start:"Inicia una compra de prueba con PayPal Sandbox.",
      creating:"Creando el pedido de PayPal Sandbox…",
      pending:"Aprueba el pago en PayPal Sandbox y vuelve aquí.",
      cancelled:"Compra cancelada. No se ha solicitado un nuevo pago.",
      capturing:"Verificando tu pago de PayPal…",
      paid:"Pago verificado. Selecciona una factura ficticia en PDF.",
      file:"Selecciona un PDF de hasta 10 MiB.",
      ticket:"Preparando la subida segura…",
      uploading:"Subiendo tu PDF…",
      validating:"Validando el PDF recibido…",
      validated:"PDF validado. Listo para procesar.",
      processing:"Procesando tu factura. Puede tardar un poco.",
      ready:"Tu CSV está listo para descargar.",
      review:"Tu factura requiere revisión. Todavía no hay CSV disponible. Contacta con ZUNPY indicando el ID de pedido.",
      incomplete:"Este pedido tiene una subida pendiente. Selecciona el PDF original para reintentar, o continúa si ya se ha subido.",
      unknown:"Estado del pedido: ",
      expired:"El resultado ya no está disponible.",
      unavailable:"No se ha podido continuar la prueba. ",
      recovery:"La petición puede haber llegado al servidor. Consulta el estado antes de reintentar.",
      unsupported:"El almacenamiento de sesión no está disponible. Actívalo antes de iniciar una compra.",
      returnMismatch:"El pedido devuelto por PayPal no coincide con esta pestaña. No se ha intentado capturar el pago.",
      invalidLink:"La API ha devuelto una URL inesperada. Se ha detenido la operación.",
      reset:"¿Borrar la sesión de prueba de esta pestaña? No se cancelan ni reembolsan pedidos existentes.",
      saved:"Estado del pedido: ",
      warming:"La API podría estar iniciándose. Mantén abierta esta pestaña."
    }
  };
  let lang = "en";
  try { lang = localStorage.getItem("zunpy-lang") === "es" ? "es" : "en"; } catch (_) {}
  let state = {};
  let busy = false;
  let storageOK = true;
  let downloadURL = "";
  let note = {key:"start", extra:"", kind:""};
  const t = key => messages[lang][key] || key;
  function setNote(key, kind="", extra="") {
    note = {key,kind,extra};
    const el = $("message");
    el.textContent = t(key) + extra;
    el.className = "message" + (kind ? " " + kind : "");
  }
  function setLang(value) {
    lang = value === "es" ? "es" : "en";
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-en]").forEach(el => {
      el.textContent = el.dataset[lang] || el.dataset.en;
    });
    document.querySelectorAll("[data-lang]").forEach(el => {
      const active = el.dataset.lang === lang;
      el.classList.toggle("active",active);
      el.setAttribute("aria-pressed",String(active));
    });
    try { localStorage.setItem("zunpy-lang",lang); } catch (_) {}
    setNote(note.key,note.kind,note.extra);
    render();
  }
  function load() {
    try {
      sessionStorage.setItem(STORAGE+"-check","1");
      sessionStorage.removeItem(STORAGE+"-check");
      const raw = sessionStorage.getItem(STORAGE);
      state = raw ? JSON.parse(raw) : {};
      if (!state || typeof state !== "object" || Array.isArray(state)) state = {};
    } catch (_) { storageOK=false; state={}; }
  }
  function save(patch) {
    const next = {...state,...patch};
    try { sessionStorage.setItem(STORAGE,JSON.stringify(next)); }
    catch (_) { storageOK=false; throw new Error(t("unsupported")); }
    state = next;
    render();
  }
  function paypalLink(value) {
    const u = new URL(value);
    if (u.protocol !== "https:" || !["www.sandbox.paypal.com","sandbox.paypal.com"].includes(u.hostname) || u.username || u.password) throw new Error(t("invalidLink"));
    return u.href;
  }
  function storageLink(value) {
    const u = new URL(value);
    if (u.protocol !== "https:" || !u.hostname.endsWith(".r2.cloudflarestorage.com") || u.username || u.password) throw new Error(t("invalidLink"));
    return u.href;
  }
  function visible(id,value) { $(id).hidden = !value; }
  function render() {
    const paid = Boolean(state.orderId && state.orderToken);
    const pending = !paid && Boolean(state.paypalId && state.claim);
    const status = state.status || "";
    const completed = paid && status === "COMPLETED";
    const review = paid && status === "REVIEW";
    const processing = paid && ["READY","PROCESSING"].includes(status);
    const resume = paid && !completed && !review && !processing && Boolean(state.uploadId && (state.uploaded || state.validated));
    const upload = paid && ["WAITING_UPLOAD","UPLOADING"].includes(status) && !resume;
    visible("pay-panel",!paid && !pending && storageOK);
    visible("pending-panel",pending);
    visible("file-panel",upload);
    visible("resume-panel",resume);
    visible("status-panel",paid);
    visible("result-panel",completed && Boolean(downloadURL));
    visible("reset-panel",paid || pending);
    visible("order",paid);
    $("order").textContent = paid ? state.orderId + " · " + status : "";
    if (pending) {
      try { $("approval").href = paypalLink(state.approval); }
      catch (_) { $("approval").removeAttribute("href"); }
    }
    if (completed && downloadURL) $("download").href=downloadURL;
    else $("download").removeAttribute("href");
    $("stage-pay").className=paid?"done":"active";
    $("stage-file").className=paid?(completed?"done":"active"):"";
    $("stage-result").className=completed?"done":review||processing?"active":"";
    document.querySelectorAll("button:not([data-lang])").forEach(b=>b.disabled=busy);
    $("pdf").disabled=busy;
    $("upload").disabled=busy || !$("pdf").files.length;
    document.querySelectorAll("#approval,#download").forEach(a=>a.setAttribute("aria-disabled",String(busy)));
  }
  async function request(path, options={}) {
    const headers = {"Accept":"application/json"};
    if (options.body !== undefined) headers["Content-Type"]="application/json";
    if (options.order) {
      if (!state.orderToken) throw new Error("Missing order token");
      headers["X-ZUNPY-Order-Token"]=state.orderToken;
    }
    const r=await fetch(API+path,{
      method:options.method||"GET",headers,
      body:options.body===undefined?undefined:JSON.stringify(options.body),
      credentials:"omit",cache:"no-store",redirect:"error",referrerPolicy:"no-referrer"
    });
    let data;
    try { data=await r.json(); } catch (_) { data={}; }
    if (!r.ok) {
      const detail=typeof data.detail==="string"?data.detail:
        (data.detail && typeof data.detail.message==="string"?data.detail.message:"");
      const err=new Error("HTTP "+r.status+(detail?" — "+detail.slice(0,240):""));
      err.status=r.status;
      throw err;
    }
    return data;
  }
  const orderPath = () => "/orders/"+encodeURIComponent(state.orderId);
  async function run(task) {
    if (busy) return;
    busy=true; render();
    try { await task(); }
    catch (err) {
      setNote("unavailable","error",String(err.message||err).slice(0,350)+(state.orderId?"\n"+t("recovery"):""));
    } finally { busy=false; render(); }
  }
  async function createCheckout() {
    if (!storageOK || state.paypalId || state.orderId) return;
    setNote("creating");
    const d=await request("/payments/paypal/order",{method:"POST"});
    const approval=paypalLink(d.approval_url);
    if (!d.paypal_order_id || !d.claim_secret || d.amount_cents!==2900 || d.currency!=="EUR") throw new Error("Unexpected checkout response");
    save({paypalId:d.paypal_order_id,claim:d.claim_secret,approval});
    setNote("pending");
    location.assign(approval);
  }
  async function capture() {
    if (!state.paypalId || !state.claim || state.orderId) return;
    setNote("capturing");
    const d=await request("/payments/paypal/order/"+encodeURIComponent(state.paypalId)+"/capture",{
      method:"POST",body:{claim_secret:state.claim}
    });
    if (!d.order_id || !d.order_token || d.paypal_order_id!==state.paypalId) throw new Error("Unexpected capture response");
    save({orderId:d.order_id,orderToken:d.order_token,status:d.order_status,claim:null,approval:null});
    if (d.order_status==="WAITING_UPLOAD") setNote("paid","ok");
    else await refresh();
  }
  async function result() {
    try {
      const d=await request(orderPath()+"/result",{order:true});
      if (d.result!=="job001_result_ready") throw new Error("Result is not ready");
      downloadURL=storageLink(d.download_url);
      setNote("ready","ok");
    } catch(e) {
      downloadURL="";
      if(e.status===410) setNote("expired","error");
      else throw e;
    }
    render();
  }
  async function refresh() {
    if (!state.orderId) return;
    const d=await request(orderPath()+"/status",{order:true});
    save({status:d.status});
    if(d.status==="COMPLETED") await result();
    else if(d.status==="REVIEW") setNote("review");
    else if(["READY","PROCESSING"].includes(d.status)) setNote("processing");
    else if(state.validated) setNote("validated","ok");
    else if(state.uploadId) setNote("incomplete");
    else if(d.status==="WAITING_UPLOAD") setNote("paid","ok");
    else setNote("unknown","",String(d.status||""));
  }
  async function submit() {
    setNote("processing");
    const d=await request(orderPath()+"/submit",{method:"POST",order:true});
    save({status:d.status});
    if(d.status==="COMPLETED") await result();
    else if(d.status==="REVIEW") setNote("review");
    else await refresh();
  }
  async function complete() {
    if (!state.uploadId) throw new Error("Missing upload ID");
    if (!state.validated) {
      setNote("validating");
      const d=await request(orderPath()+"/files/"+encodeURIComponent(state.uploadId)+"/complete",{method:"POST",order:true});
      if(d.status!=="VALIDATED") throw new Error("PDF validation status: "+String(d.status));
      save({validated:true,uploaded:true});
    }
    await submit();
  }
  async function upload() {
    const f=$("pdf").files[0];
    if(!f || f.size<=0 || f.size>MAX || !/\.pdf$/i.test(f.name) || (f.type && f.type!=="application/pdf")) {
      setNote("file","error"); return;
    }
    if(state.uploadId) {
      if(state.fileName!==f.name || state.fileSize!==f.size) throw new Error(lang==="es"?"Selecciona el mismo PDF de la subida pendiente.":"Select the same PDF as the pending upload.");
      if(!state.uploadURL || Date.parse(state.uploadExpires)<=Date.now()) throw new Error(lang==="es"?"La autorización de subida ha caducado. Contacta con soporte indicando el pedido.":"Upload authorization expired. Contact support with the order ID.");
    } else {
      setNote("ticket");
      const d=await request(orderPath()+"/files",{method:"POST",order:true,body:{filename:f.name,size_bytes:f.size,content_type:"application/pdf"}});
      if(d.method!=="PUT" || !d.upload_id || d.required_headers?.["Content-Type"]!=="application/pdf") throw new Error("Unexpected upload ticket");
      const url=storageLink(d.upload_url);
      save({uploadId:d.upload_id,uploadURL:url,uploadExpires:d.expires_at,fileName:f.name,fileSize:f.size,uploaded:false,validated:false});
    }
    setNote("uploading");
    const r=await fetch(storageLink(state.uploadURL),{
      method:"PUT",headers:{"Content-Type":"application/pdf"},body:f,credentials:"omit",redirect:"error",referrerPolicy:"no-referrer"
    });
    if(!r.ok) throw new Error("Upload HTTP "+r.status);
    save({uploaded:true,uploadURL:null});
    await complete();
  }
  document.querySelectorAll("[data-lang]").forEach(b=>b.addEventListener("click",()=>setLang(b.dataset.lang)));
  $("pay").addEventListener("click",()=>run(createCheckout));
  $("capture").addEventListener("click",()=>run(capture));
  $("pdf").addEventListener("change",render);
  $("upload").addEventListener("click",()=>run(upload));
  $("resume").addEventListener("click",()=>run(complete));
  $("refresh").addEventListener("click",()=>run(refresh));
  $("reset").addEventListener("click",()=>{
    if(busy || !confirm(t("reset"))) return;
    try { sessionStorage.removeItem(STORAGE); } catch (_) {return;}
    state={}; downloadURL=""; $("pdf").value=""; setNote("start"); render();
  });
  ["approval","download"].forEach(id=>$(id).addEventListener("click",e=>{if(busy || !$(id).hasAttribute("href")) e.preventDefault();}));
  load();
  setLang(lang);
  if (!storageOK) {setNote("unsupported","error");render();return;}
  const params=new URLSearchParams(location.search);
  const returned=params.get("paypal");
  const returnedOrder=params.get("token");
  if(returned) history.replaceState(null,"",location.pathname);
  if(state.orderId) run(refresh);
  else if(returned==="approved") {
    if(state.paypalId && returnedOrder===state.paypalId && state.claim) run(capture);
    else setNote("returnMismatch","error");
  } else if(returned==="cancelled") setNote("cancelled");
  else if(state.paypalId) setNote("pending");
  else setNote("start");
  render();
})();
