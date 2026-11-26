/* Offline browser-contract test, using a minimal simulated DOM and fetch. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "..", "jobs.js"), "utf8");
const ORDER = "ZJ-TEST123456";
const TOKEN = "a".repeat(43);
const ACCESS = "b".repeat(43);
const STORE = "zunpy-job001-sandbox-v1";

function setup({initial = {}, hash = "", search = "", respond} = {}) {
  const elements = new Map(), calls = [], saved = new Map([[STORE,JSON.stringify(initial)]]);
  const location = {hostname:"zunpyai.com",pathname:"/jobs.html",search,hash,
    assign(){throw new Error("Unexpected navigation");},replace(){throw new Error("Unexpected redirect");}};
  const element = id => {
    if(!elements.has(id)) elements.set(id,{
      hidden:false,disabled:false,value:"",textContent:"",className:"",
      dataset:{},files:[],listeners:{},attrs:{},
      addEventListener(name,fn){this.listeners[name]=fn;},
      setAttribute(k,v){this.attrs[k]=v;},
      removeAttribute(k){delete this.attrs[k];delete this[k];},
      hasAttribute(k){return k in this.attrs || k in this;},
    });
    return elements.get(id);
  };
  const storage = {
    setItem(k,v){saved.set(k,v);},getItem(k){return saved.get(k)??null;},
    removeItem(k){saved.delete(k);}
  };
  const context = {
    document:{getElementById:element,querySelectorAll:()=>[],documentElement:{}},
    sessionStorage:storage,localStorage:{getItem:()=>null,setItem(){}},
    location,history:{replaceState(_a,_b,url){
      const u=new URL(url,"https://zunpyai.com");
      location.hash=u.hash;location.search=u.search;
    }},
    URL,URLSearchParams,confirm:()=>true,
    fetch:async (url,options)=>{
      const p=new URL(url).pathname;
      const body=options.body===undefined?undefined:JSON.parse(options.body);
      calls.push({p,body,method:options.method,headers:options.headers});
      const result=respond(p,body);
      return {ok:result.code>=200&&result.code<300,status:result.code,json:async()=>result.data};
    },
  };
  vm.runInNewContext(source,context);
  return {calls,location,element,saved,settle:()=>new Promise(resolve=>setImmediate(resolve))};
}

(async()=>{
  const a=setup({
    initial:{paypalId:"PAYPALTEST",claim:TOKEN,approval:"https://www.sandbox.paypal.com/checkoutnow"},
    respond(p){
      assert.equal(p,"/v1/payments/paypal/order/PAYPALTEST/capture");
      return {code:200,data:{result:"paypal_order_recovery_required",order_id:ORDER,order_status:"WAITING_UPLOAD",paypal_order_id:"PAYPALTEST"}};
    }
  });
  await a.element("capture").listeners.click();
  assert.equal(a.calls.length,1);
  assert.equal(a.element("pay-panel").hidden,true);
  assert.equal(a.element("pending-panel").hidden,true);
  assert.equal(a.element("recovery-order").value,ORDER);
  assert.deepEqual(JSON.parse(a.saved.get(STORE)),{orderId:ORDER,status:"WAITING_UPLOAD"});

  const b=setup({hash:"#order="+ORDER+"&recovery="+TOKEN,respond(p,body){
    if(p==="/v1/recovery/redeem"){
      assert.equal(body.order_id,ORDER);
      assert.equal(body.recovery_token,TOKEN);
      return {code:200,data:{order_id:ORDER,order_token:ACCESS}};
    }
    assert.equal(p,"/v1/orders/"+ORDER+"/status");
    return {code:200,data:{status:"WAITING_UPLOAD"}};
  }});
  assert.equal(b.location.hash,"");
  assert.equal(b.calls.length,0);
  assert.equal(b.element("redeem-panel").hidden,false);
  assert.equal(b.saved.get(STORE).includes(TOKEN),false);
  await b.element("redeem-recovery").listeners.click();
  assert.equal(b.calls.length,2);
  assert.equal(b.calls[0].method,"POST");
  assert.equal(b.calls[1].headers["X-ZUNPY-Order-Token"],ACCESS);
  assert.equal(b.saved.get(STORE).includes(TOKEN),false);
  assert.equal(b.element("file-panel").hidden,false);

  const c=setup({respond(p,body){
    assert.equal(p,"/v1/recovery/request");
    assert.deepEqual(body,{order_id:ORDER,email:"buyer@example.com"});
    return {code:202,data:{status:"accepted"}};
  }});
  c.element("recovery-order").value=ORDER;
  c.element("recovery-email").value="buyer@example.com";
  c.element("recovery-form").listeners.submit({preventDefault(){}});
  await c.settle();
  assert.equal(c.calls.length,1);
  assert.equal(c.element("recovery-email").value,"");
  assert.equal(c.saved.get(STORE).includes("buyer@example.com"),false);
  console.log("JOB-005.2.17 WEB_RECOVERY_CONTRACT: PASS (3 scenarios)");
})().catch(error=>{console.error(error);process.exitCode=1;});
