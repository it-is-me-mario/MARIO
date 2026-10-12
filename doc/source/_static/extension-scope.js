/* Satellite accounts by theme: native labels per published reading, grouped by reviewed rules. */
((global) => {
  "use strict";
  const esc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const GAS_ORDER=["co2","ch4","n2o","fgas","total"],MAIN_GASES=["co2","ch4","n2o","fgas"];
  const name=(family,variant)=>variant?`${family} · ${variant}`:family;
  const ICONS={ghg:'<path d="M14 14.8V4.5a2 2 0 0 0-4 0v10.3a4 4 0 1 0 4 0ZM12 17.5v-6"/>',
    air:'<path d="M3 8h10a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h7"/>',
    energy:'<path d="M13 2 4.5 13.5H11L10 22l8.5-11.5H12Z"/>',
    materials:'<path d="m12 2.5 8.5 4.75v9.5L12 21.5l-8.5-4.75v-9.5ZM3.5 7.25 12 12l8.5-4.75M12 12v9.5"/>',
    land:'<path d="M2.5 20.5h19M4 20.5l5.5-9 3.5 5.5 2.5-3.5 4.5 7M16.5 5.5a2 2 0 1 1-4 0 2 2 0 0 1 4 0Z"/>',
    water:'<path d="M12 3s-6.5 7-6.5 11.5a6.5 6.5 0 0 0 13 0C18.5 10 12 3 12 3Z"/>',
    waste:'<path d="M4 7h16M9.5 7V4h5v3M6 7l1 13.5h10L18 7M10 11l.5 6M14 11l-.5 6"/>',
    employment:'<path d="M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM2.5 20.5a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 6.5M21.5 20.5a6.5 6.5 0 0 0-3.5-5.8"/>',
    economic:'<path d="M3 20.5h18M6 20.5v-7M11 20.5V6M16 20.5v-10M21 20.5V9"/>',
    other:'<path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM8 12h.01M12 12h.01M16 12h.01"/>'};
  const icon=id=>`<svg class="ext-icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[id]||ICONS.other}</svg>`;
  const cell=(data,reading,category)=>data.sets[reading.set][category];
  const readingLabel=r=>[r.release,r.system,r.years].filter(Boolean).join(" · ");
  // One row per family variant: account counts differ across releases, systems and year groups.
  function categoryRows(data,category) {
    const rows=[];
    for(const f of data.families)for(const v of f.variants) {
      const readings=v.readings.filter(r=>cell(data,r,category));
      if(!readings.length)continue;
      const counts=readings.map(r=>cell(data,r,category).labels.length);
      rows.push({family:f.family,variant:v.variant,readings,min:Math.min(...counts),max:Math.max(...counts),
        gases:[...new Set(readings.flatMap(r=>cell(data,r,category).gases||[]))],releases:[...new Set(readings.map(r=>r.release))]});
    }
    return rows.sort((a,b)=>b.max-a.max||a.family.localeCompare(b.family));
  }
  function chip(row,category,gases) {
    const ordered=GAS_ORDER.map(id=>gases.find(g=>g.id===id)).filter(Boolean);
    const pills=category==="ghg"?`<span class="ext-gases">${ordered.filter(g=>MAIN_GASES.includes(g.id)||row.gases.includes(g.id)).map(g=>
      `<span class="ext-gas"${row.gases.includes(g.id)?"":" data-absent"} title="${esc(g.label)}${row.gases.includes(g.id)?"":" not included"}">${esc(g.label)}</span>`).join("")}</span>`:"";
    const count=row.min===row.max?row.max.toLocaleString():`${row.min.toLocaleString()}–${row.max.toLocaleString()}`;
    const span=row.readings.length>1?`${row.readings.length} readings · releases ${row.releases.join(", ")}`:readingLabel(row.readings[0]);
    return `<li><button type="button" class="ext-chip" data-ext-family="${esc(row.family)}" data-ext-variant="${esc(row.variant)}" data-ext-category="${esc(category)}" aria-expanded="false" title="${esc(span)}">`
      +`<b>${esc(name(row.family,row.variant))}</b><span class="ext-count">${count} ${row.max===1?"account":"accounts"}</span>${pills}</button></li>`;
  }
  function render(data) {
    const cards=data.categories.map(c=>{
      const rows=categoryRows(data,c.id);
      return `<section class="ext-card" data-ext-card="${esc(c.id)}"><h4>${icon(c.id)}${esc(c.label)}</h4><p>${esc(c.description)}</p>${rows.length
        ?`<ul class="ext-chips">${rows.map(r=>chip(r,c.id,data.gases)).join("")}</ul>`:'<p class="ext-empty">No loaded accounts.</p>'}</section>`;
    }).join("");
    return `<div class="ext-grid">${cards}</div><div class="ext-detail" data-ext-detail hidden></div>`;
  }
  // Labels of one reading in one category; the newest reading is the default.
  function readingLabels(data,family,variant,category,readingId) {
    const row=categoryRows(data,category).find(r=>r.family===family&&r.variant===variant),reading=row.readings.find(r=>r.id===readingId)||row.readings[0];
    return {row,reading,labels:cell(data,reading,category).labels.map(i=>data.labels[i])};
  }
  function detail(data,family,variant,category,readingId) {
    const c=data.categories.find(x=>x.id===category),{row,reading,labels}=readingLabels(data,family,variant,category,readingId);
    const options=row.readings.map(r=>`<option value="${esc(r.id)}"${r.id===reading.id?" selected":""}>${esc(readingLabel(r))} — ${cell(data,r,category).labels.length.toLocaleString()} accounts</option>`).join("");
    return `<div class="ext-detail-head"><h4>${esc(name(family,variant))} · ${esc(c.label)}</h4><span>${labels.length.toLocaleString()} native ${labels.length===1?"account":"accounts"} in this reading</span>
      <button type="button" class="ext-close" data-ext-close aria-label="Close the account list">×</button></div>
      <div class="ext-detail-tools">${row.readings.length>1?`<label class="ext-reading">Reading<select data-ext-reading>${options}</select></label>`:`<span class="ext-reading-one">${esc(readingLabel(reading))}</span>`}
      <input type="search" data-ext-search placeholder="Filter accounts…" aria-label="Filter accounts"><button type="button" data-ext-download>Download list · CSV</button></div>
      <ol class="ext-labels" data-ext-labels>${labels.map(l=>`<li>${esc(l)}</li>`).join("")}</ol>`;
  }
  const api={categoryRows,render,detail,readingLabels};
  if(typeof module!=="undefined")module.exports=api;
  else global.MarioExtensionScope=api;
})(globalThis);

(() => {
  if(typeof document==="undefined")return;
  const root=document.querySelector("[data-extension-scope]");
  if(!root)return;
  const base=new URL(root.dataset.root || "../../",location.href),E=window.MarioExtensionScope;
  fetch(new URL("_static/data/economy/extension-scope.json",base),{cache:"no-cache"}).then(r=>{if(!r.ok)throw new Error("Extension catalogue unavailable");return r.json();}).then(data=>{
    root.innerHTML=E.render(data);root.setAttribute("aria-busy","false");
    const panel=root.querySelector("[data-ext-detail]");let open=null,reading=null;
    const show=()=>{panel.innerHTML=E.detail(data,open.dataset.extFamily,open.dataset.extVariant,open.dataset.extCategory,reading);panel.hidden=false;};
    const close=()=>{panel.hidden=true;panel.innerHTML="";if(open){open.setAttribute("aria-expanded","false");open.focus({preventScroll:true});}open=null;reading=null;};
    root.addEventListener("click",event=>{
      const button=event.target.closest("button");if(!button)return;
      if(button.matches("[data-ext-close]")){close();return;}
      if(button.matches("[data-ext-download]")){
        const {reading:r,labels}=E.readingLabels(data,open.dataset.extFamily,open.dataset.extVariant,open.dataset.extCategory,reading);
        const quote=v=>'"'+String(v).replace(/^[=+@\-\t\r]/,m=>"'"+m).replace(/"/g,'""')+'"';
        const csv="﻿"+[["database","variant","release","system","years","category","native_account"],...labels.map(l=>[open.dataset.extFamily,open.dataset.extVariant,r.release,r.system,r.years,open.dataset.extCategory,l])].map(row=>row.map(quote).join(",")).join("\r\n");
        const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"})),a=document.createElement("a");
        a.href=url;a.download=`mario-${(open.dataset.extFamily+"-"+open.dataset.extVariant+"-"+r.release).toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/-+$/,"")}-${open.dataset.extCategory}-accounts.csv`;
        a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;
      }
      if(button.matches("[data-ext-family]")){
        if(open===button){close();return;}
        if(open)open.setAttribute("aria-expanded","false");
        open=button;reading=null;button.setAttribute("aria-expanded","true");show();
        panel.scrollIntoView({block:"nearest",behavior:"smooth"});
      }
    });
    root.addEventListener("change",event=>{if(event.target.matches("[data-ext-reading]")){reading=event.target.value;show();panel.querySelector("[data-ext-reading]").focus();}});
    root.addEventListener("input",event=>{
      if(!event.target.matches("[data-ext-search]"))return;
      const query=event.target.value.trim().toLowerCase();
      panel.querySelectorAll("[data-ext-labels] li").forEach(li=>{li.hidden=!!query&&!li.textContent.toLowerCase().includes(query);});
    });
    root.addEventListener("keydown",event=>{if(event.key==="Escape"&&open)close();});
  }).catch(error=>{root.textContent=`The extension view could not load. ${error.message}`;root.setAttribute("aria-busy","false");});
})();
