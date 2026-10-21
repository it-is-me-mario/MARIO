/* Interactive classification heatmap; economic values are never disaggregated. */
(()=>{
 'use strict';
 const root=document.querySelector('[data-sectoral-scope]');if(!root)return;
 // Official leaf level of the reference: NACE classes (4 digits), CPA subcategories (6 digits).
 const leaves=ref=>`${ref.short_label} ${{class:'classes',subcategory:'subcategories'}[ref.leaf_name]||ref.leaf_name+'s'}`;
 // Fragment navigation runs before the asynchronous charts above are sized.
 // Keep the initial deep link until those layouts settle, unless the reader
 // starts navigating or scrolling. A deep link also bypasses lazy mounting.
 const initialHash=location.hash;
 let initialAnchor=null;
 try{initialAnchor=document.getElementById(decodeURIComponent(initialHash.slice(1)));}catch{}
 if(!root.closest('section')?.contains(initialAnchor))initialAnchor=null;
 let anchorPending=Boolean(initialAnchor)&&!document.querySelector('[data-scope-tabs]'),anchorObserver=null;
 const anchorEvents=['wheel','touchstart','pointerdown','keydown','hashchange'];
 function stopInitialAnchor(){
  anchorPending=false;anchorObserver?.disconnect();
  anchorEvents.forEach(type=>window.removeEventListener(type,stopInitialAnchor,true));
 }
 if(anchorPending)anchorEvents.forEach(type=>window.addEventListener(type,stopInitialAnchor,{capture:true,passive:true}));
 function restoreInitialAnchor(){
  if(!anchorPending)return;
  const settle=()=>{
   if(location.hash!==initialHash){stopInitialAnchor();return;}
   const abovePending=[...document.querySelectorAll('[aria-busy="true"]')].some(n=>n.compareDocumentPosition(initialAnchor)&Node.DOCUMENT_POSITION_FOLLOWING);
   if(abovePending||document.fonts?.status==='loading')return;
   requestAnimationFrame(()=>{
    if(anchorPending&&location.hash===initialHash)initialAnchor.scrollIntoView({block:'start',behavior:'instant'});
    stopInitialAnchor();
   });
  };
  anchorObserver=new MutationObserver(settle);
  anchorObserver.observe(document.querySelector('.mario-article')||document.body,{subtree:true,attributes:true,attributeFilter:['aria-busy']});
  document.fonts?.ready.then(settle);settle();
 }
 const M=window.MarioSectoralScope,esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const base=new URL(root.dataset.root||'../../',location.href),$=s=>root.querySelector(s);
 const sourceURL=s=>new URL(s.url,new URL('_static/data/economy/',base)).href;
 let data,model,kind='activity',selections=new Map(),area='',level=1,selected='',selectedColumn='',visible=[],coordinates,columns=[],enabled=new Set(),operations=Promise.resolve(),generation=0;
 const period=ys=>ys.length?`${ys[0]}${ys.length>1?'–'+ys.at(-1):''}`:'';
 async function mount(){
  try{
   const response=await fetch(new URL('_static/data/economy/sectoral-scope.json',base),{cache:'no-cache'});if(!response.ok)throw Error('Classification data unavailable');
   const snapshot=await response.json();
   // The table has one native Sector set. Also enforce the display policy
   // when an older snapshot still includes its auxiliary CPC vocabulary.
   data={...snapshot,columns:{...snapshot.columns,commodity:snapshot.columns.commodity.filter(c=>!['GTAP','CEDA'].includes(c.family))}};
   model=M.index(data);enabled=new Set(model.columns.filter(c=>c.default_visible!==false&&['documented','section_only'].includes(c.status)).map(c=>c.id));
   root.innerHTML=`<div class="ss-heading"><div><div class="ss-kind" role="group" aria-label="Native set"><button data-ss-kind="activity" aria-pressed="true">Activities</button><button data-ss-kind="commodity" aria-pressed="false">Commodities</button></div><strong data-ss-reference>NACE Rev. 2.1</strong></div><p data-ss-count role="status"></p></div>
    <div class="ss-controls"><div class="ss-field ss-area"><span>Classification area</span><details data-ss-picker><summary data-ss-area>All sections</summary><div class="ss-picker-panel"><input type="search" data-ss-search aria-label="Find a NACE code or name" placeholder="Search a code or name…"><nav data-ss-picker-path aria-label="Classification path"></nav><div data-ss-options></div><p data-ss-search-note></p></div></details></div>
    <label class="ss-field">Label detail<select data-ss-labels><option value="1">Sections · A, B, C…</option><option value="2">Divisions · 2 digits</option><option value="3">Groups · 3 digits</option><option value="4">Classes · 4 digits</option></select></label>
    <div class="ss-field ss-databases"><span>Databases</span><details data-ss-databases><summary data-ss-db-summary></summary><div class="ss-picker-panel"><div class="ss-picker-actions"><button data-ss-select="all">Select all</button><button data-ss-select="none">Unselect all</button></div><div data-ss-db-list></div></div></details></div></div>
    <div class="ss-chart-toolbar"><nav data-ss-path aria-label="Selected classification area"></nav><div class="ss-zoom" role="group" aria-label="Heatmap row zoom"><button data-ss-zoom="in" aria-label="Zoom in on classification rows" title="Zoom in">+</button><button data-ss-zoom="out" aria-label="Zoom out on classification rows" title="Zoom out">−</button><button data-ss-zoom="reset">Reset zoom</button></div></div>
    <div class="ss-selection-status" data-ss-selection-status role="status"><span data-ss-selection-label>Select a cell for native sectors.</span><button data-ss-show-details hidden>View native sectors ↓</button></div>
    <div class="ss-chart-scroll"><div data-ss-chart role="img" aria-label="Sectoral resolution heatmap. Choose a code from Classification area for accessible native-sector details."></div></div>
    <div class="ss-key"><span class="ss-unknown"><i></i>Concordance unverified</span></div>
    <div class="ss-detail" data-ss-detail aria-live="polite"><p class="ss-detail-hint">Choose a row or click the heatmap to see where each database places it.</p></div>
    <div class="ss-footer"><details class="ss-notes"><summary>Method &amp; sources</summary><p class="ss-chart-help" data-ss-help></p><p class="ss-chart-help" data-ss-database-note hidden></p><div data-ss-notes></div></details></div>`;
   vocabulary();databaseList();picker();notes();await render();bind();root.setAttribute('aria-busy','false');
   new MutationObserver(()=>render().catch(fail)).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
   matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>render().catch(fail));
  }catch(e){fail(e);}finally{restoreInitialAnchor();}
 }
 function fail(error){root.setAttribute('aria-busy','false');let status=$('[data-ss-count]');if(status)status.textContent='Unable to render the heatmap. '+error.message;else root.textContent='The sectoral comparison could not load. '+error.message;}
 function vocabulary(){
  $('[data-ss-reference]').textContent=model.ref.label;
  const names=['Sections','Divisions · 2 digits','Groups · 3 digits','Classes · 4 digits','Categories · 5 digits','Subcategories · 6 digits'];
  $('[data-ss-labels]').innerHTML=names.slice(0,model.ref.leaf_level).map((name,i)=>`<option value="${i+1}" ${level===i+1?'selected':''}>${name}</option>`).join('');
  $('[data-ss-search]').setAttribute('aria-label',`Find a ${model.ref.short_label} code or name`);
  $('[data-ss-help]').textContent=`Every row is one ${model.ref.short_label} ${model.ref.leaf_name}. Below 1: verified native subdivisions (1/2 = two categories linked exclusively to this reference). At 1: one linked reference per native category within its section. Above 1: several linked references within that section. Qualified and joined correspondence footprints do not prove exact containment or provide allocation weights.`;
  root.querySelectorAll('[data-ss-kind]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.ssKind===kind)));
 }
 function changeKind(next){
  if(next===kind)return;
  selections.set(kind,new Set(enabled));kind=next;model=M.index(data,kind);
  enabled=selections.get(kind)||new Set(model.columns.filter(c=>c.default_visible!==false&&c.status==='documented').map(c=>c.id));
  area='';level=1;selected='';selectedColumn='';$('[data-ss-search]').value='';
  vocabulary();databaseList();picker();notes();render().catch(fail);
 }
 function alternatives(link){
  return [...(link.alternatives||[]),...(link.alternative_steps||[]).map(ids=>({steps:ids,nodes:[data.route_steps[ids[0]].source_left,...ids.map(id=>data.route_steps[id].source_right)]}))];
 }
 function databaseList(){
  $('[data-ss-db-list]').innerHTML=model.columns.map(c=>`<label class="ss-db-option"><input type="checkbox" data-ss-column="${esc(c.id)}" ${enabled.has(c.id)?'checked':''}><span><b>${esc(c.label)}</b><small>${c.native_count} native categories · ${c.status==='documented'?c.native.filter(n=>n.classes.length).length+'/'+c.native_count+' with a documented route':c.status==='section_only'?'published section anchors · fine mapping pending':'concordance pending'}</small></span></label>`).join('');
  $('[data-ss-db-summary]').textContent=`${enabled.size} classifications selected`;
 }
 function pathHTML(code){return '<button data-ss-area="">All sections</button>'+M.ancestors(model,code).map(n=>`<span aria-hidden="true">›</span><button data-ss-area="${esc(n.code)}" title="${esc(n.name)}">${esc(n.code)}</button>`).join('');}
 function picker(){
  const query=$('[data-ss-search]').value.trim().toLowerCase();
  const matches=model.ref.nodes.filter(n=>query?`${n.code} ${n.name}`.toLowerCase().includes(query):n.parent===(area||null));
  const current=model.nodes.get(area);
  $('[data-ss-area]').innerHTML=current?`<span title="${esc(current.name)}">${esc(current.code)} · ${esc(current.name)}</span>`:'<span>All sections</span>';
  $('[data-ss-picker-path]').innerHTML=pathHTML(area);$('[data-ss-path]').innerHTML=pathHTML(area);
  $('[data-ss-options]').innerHTML=matches.slice(0,80).map(n=>`<button data-ss-area="${esc(n.code)}" class="ss-node"><b>${esc(n.code)}</b><span>${esc(n.name)}</span>${n.level<model.ref.leaf_level?'<span aria-hidden="true">›</span>':''}</button>`).join('')||(current?.level===model.ref.leaf_level?'<p>Leaf reference selected. Use the path above to choose a broader area.</p>':'<p>No matching code or name.</p>');
  $('[data-ss-search-note]').textContent=matches.length>80?'First 80 matches; refine your search.':'Select a code to focus the heatmap and open its subcategories.';
 }
 function notes(){
  const referenceSource=data.sources[model.ref.source];
  const used=new Set([model.ref.source]);
  for(const c of model.columns)for(const n of c.native)for(const l of Object.values(n.links))for(const id of l.steps)used.add(data.route_steps[id].source);
  if(kind==='commodity'&&model.columns.some(c=>c.native.some(n=>n.production_review)))used.add('P19');
  const method=kind==='activity'?'Current NACE activity scopes are checked against native definitions, complete official revision tables and reviewed nxbase concepts. Published producer bridges, mixed categories and editorial decisions remain qualified. Existing nxbase parents are shown separately as lineage; they never enumerate native members.':'CPA paths remain product-only. FIGARO uses CPA 2.1, WIOD retains its qualified product-code interpretation, and EXIOBASE follows CPA 2002 → 2008 → 2.1 → 2.2 with explicit current product reviews where definitions permit. CEDA and GLORIA retain the published EPA commodity bridges, constrained by an explicit, qualified producer-origin review. A broad common category cannot establish a specific product correspondence by itself. Hybrid uses the publisher’s separate 200-product SUT and 164-product IOT definitions and their explicit aggregation. Categories without a verified route remain unverified.';
  $('[data-ss-notes]').innerHTML=`<p><a href="${esc(sourceURL(referenceSource))}">Eurostat · ${esc(model.ref.label)}</a> · ${model.leaves.length} leaf references. Snapshot ${esc(data.as_of)}. Every row is retained, even when only section letters are labelled.</p><p>Colours measure linked ${leaves(model.ref)} per native category within the original section. A fraction 1/k is used only for exclusive, verified same-reference links; unknown precision or partial routes cannot become exact subdivisions. Joined classifications can give a wider possible footprint and do not prove exact containment. No allocation weights are provided.</p><p>${method}</p><div class="ss-source-list">${Object.values(data.sources).filter(s=>used.has(s.id)).map(s=>`<a href="${esc(sourceURL(s))}">${esc(s.title)}</a>`).join('')}</div>`;
 }
 async function render(){
  const request=++generation;visible=M.rows(model,area);coordinates=M.geometry(visible);columns=model.columns.filter(c=>enabled.has(c.id));const leafOnly=visible.length===1;$('[data-ss-labels]').disabled=leafOnly;$('[data-ss-labels]').value=String(leafOnly?model.ref.leaf_level:level);
  $('[data-ss-count]').textContent=`${visible.length} / ${model.leaves.length} ${leaves(model.ref)} · ${columns.length} native classifications`;
  $('[data-ss-db-summary]').textContent=`${enabled.size} classifications selected`;
  const databaseNotes=columns.filter(c=>['GTAP','CEDA'].includes(c.family)&&c.note),databaseNote=$('[data-ss-database-note]');
  databaseNote.hidden=!databaseNotes.length;databaseNote.innerHTML=databaseNotes.map(c=>esc(c.note)).join('<br>');
  const chart=$('[data-ss-chart]');chart.setAttribute('aria-busy','true');chart.style.minWidth=Math.max(520,columns.length*92+215)+'px';
  if(!columns.length){await operations;if(request!==generation)return;window.Plotly.purge(chart);chart.innerHTML='<p class="ss-empty">Select a database to display its classification.</p>';chart.setAttribute('aria-busy','false');detail();return;}
  const styles=getComputedStyle(root),get=name=>styles.getPropertyValue(name).trim();
  const ink=get('--ink'),muted=get('--ink-muted'),bg=get('--surface-2'),surface=get('--surface'),line=get('--line'),unknown=get('--ss-unknown'),fine=get('--ss-fine'),middle=get('--ss-middle'),coarse=get('--ss-coarse');
  const cells=visible.map(row=>columns.map(c=>M.cell(model,c,row.code)));
  const domain=M.colourDomain(kind),maximum=domain.ceiling,barLength=leafOnly?.72:.8;
  const scale=leafOnly?[0,domain.midpoint,maximum]:domain.ticks,labelTicks=M.labels(model,visible,leafOnly?model.ref.leaf_level:level).map(g=>({...g,position:(coordinates.edges[g.start]+coordinates.edges[g.end+1])/2}));
  const hover=(c,col,row)=>`<b>${esc(col.label)} · ${esc(row.code)}</b><br>${esc(row.name)}<br>${c.matches.length?`<b>Resolution: ${M.resolutionLabel(c)}</b><br>${esc(resolutionDescription(c).summary)}${resolutionDescription(c).context?'<br>'+esc(resolutionDescription(c).context):''}<br>Section footprint: ${c.minimum===c.maximum?c.maximum:c.minimum+'–'+c.maximum} / ${c.denominator} in ${c.section}<br>${c.matches.some(m=>m.link.status==='partial')?'Route includes partial overlaps':c.matches.every(m=>m.link.status==='reviewed')?'Reviewed native correspondence':c.matches.every(m=>m.link.mapping_origin==='governed_nxbase')?'Existing nxbase containment':'Published correspondence · precision retained in details'}${c.pending.length?'<br>'+c.pending.length+' additional categories awaiting review · excluded from the index':''}<br>Click to highlight and view native sectors below`:`Fine concordance unverified<br>No absence is inferred.${c.coarse.length?`<br>${c.coarse.length} native categories have a broad section anchor`:''}<br>Click for classification details.`}`;
  const hoverRows=cells.map((cs,i)=>cs.map((c,j)=>hover(c,columns[j],visible[i])+(columns[j].scope_note?'<br>'+esc(columns[j].scope_note):'')));
  const traces=[{type:'heatmap',x:columns.map((_,i)=>i),y:coordinates.edges,z:visible.map(()=>columns.map(()=>0)),colorscale:[[0,unknown],[1,unknown]],showscale:false,text:hoverRows,hovertemplate:'%{text}<extra></extra>',name:'Unverified'},
   {type:'heatmap',x:columns.map((_,i)=>i),y:coordinates.edges,z:M.matrix(model,visible,columns),zmin:0,zmax:1,colorscale:M.colourScale(fine,middle,coarse),xgap:3,showscale:true,
    colorbar:{orientation:'v',x:1.015,y:.5,xanchor:'left',yanchor:'middle',len:barLength,title:{text:`Linked ${leaves(model.ref)}`,side:'right'},tickvals:scale.map(n=>M.scaleValue(n,kind)),ticktext:scale.map(n=>n===maximum?n+'+':String(n)),thickness:10,outlinewidth:0,tickfont:{size:11,color:muted}},text:hoverRows,hovertemplate:'%{text}<extra></extra>',name:'Documented'}];
  const boundaries=visible.flatMap((n,i)=>i&&n.section!==visible[i-1].section?[coordinates.edges[i]]:[]);
  const layout={height:visible.length===1?280:Math.max(430,Math.min(720,visible.length*9+100)),autosize:true,paper_bgcolor:bg,plot_bgcolor:unknown,font:{family:styles.fontFamily,color:ink,size:12},
   margin:{l:75,r:140,t:95,b:25},xaxis:{side:'top',range:[-.5,columns.length-.5],tickvals:columns.map((_,i)=>i),ticktext:columns.map(c=>esc(c.label).replace(' · ','<br>')+'<br>('+c.native_count+')'),tickangle:0,fixedrange:true,showgrid:false,zeroline:false},
   yaxis:{title:{text:model.ref.label,standoff:14},range:[coordinates.end,0],tickvals:labelTicks.map(g=>g.position),ticktext:labelTicks.map(g=>g.code),showgrid:false,zeroline:false,automargin:true},
   annotations:[{xref:'paper',yref:'paper',x:1.015,y:.5+barLength/2,text:'Coarser than<br>'+model.ref.short_label,showarrow:false,xanchor:'left',yanchor:'bottom',font:{size:11,color:muted}},{xref:'paper',yref:'paper',x:1.015,y:.5-barLength/2,text:'Finer than<br>'+model.ref.short_label,showarrow:false,xanchor:'left',yanchor:'top',font:{size:11,color:muted}}],
   shapes:[...boundaries.map(y=>({type:'line',xref:'paper',x0:0,x1:1,y0:y,y1:y,line:{color:bg,width:2}})),...selectionShapes()],
   hoverlabel:{bgcolor:surface,bordercolor:line,font:{color:ink}},hovermode:'closest',dragmode:'zoom',showlegend:false,uirevision:`${kind}:${area}:${[...enabled].join(',')}:${level}`};
  const config={responsive:true,scrollZoom:true,doubleClick:'autosize',displaylogo:false,showTips:false,modeBarButtonsToRemove:['select2d','lasso2d','hoverClosestCartesian','hoverCompareCartesian'],toImageButtonOptions:{filename:`mario-${model.ref.short_label.toLowerCase()}-sectoral-coverage`,format:'png',scale:2}};
  const credited=window.MarioFigureDownload.withCredit(config,['MARIO / nxbase · '+model.ref.label+' concordance review · '+columns.map(c=>c.label).join(', '),'Classification facts and qualified links; retain upstream source-specific terms. Sources: https://www.marioproject.com/en/latest/resources/data-explorer/scope.html#sectoral-coverage']);
  const viewKey=kind+'|'+area+'|'+columns.map(c=>c.id).join(',');
  operations=operations.then(()=>{if(request!==generation)return;if(chart.dataset.ssView!==viewKey||!chart._fullLayout){chart.dataset.ssView=viewKey;window.Plotly.purge(chart);chart.innerHTML='';return window.Plotly.newPlot(chart,traces,layout,credited);}return window.Plotly.react(chart,traces,layout,credited);});
  await operations;if(request!==generation)return;chart.setAttribute('aria-busy','false');
  chart.removeAllListeners?.('plotly_click');chart.on('plotly_click',event=>{if(chart.getAttribute('aria-busy')==='true')return;const point=event.points[0],row=visible[M.rowAt(coordinates,point.y)],col=columns[Math.round(point.x)];if(row&&col){selected=row.code;selectedColumn=col.id;detail();highlight();}});
  detail();
 }
 function selectionShapes(){
  const rectangle=M.selection(visible,columns,coordinates,selected,selectedColumn);if(!rectangle)return [];
  const css=getComputedStyle(root),get=name=>css.getPropertyValue(name).trim();
  return [{name:'ss-selection-halo',colour:get('--surface'),width:6},{name:'ss-selection-outline',colour:get('--ink'),width:2.5}].map(style=>({name:style.name,type:'rect',xref:'x',yref:'y',...rectangle,line:{color:style.colour,width:style.width},fillcolor:'rgba(0,0,0,0)',layer:'above'}));
 }
 function highlight(){
  const chart=$('[data-ss-chart]'),request=generation;
  operations=operations.then(()=>{if(request!==generation||!chart._fullLayout)return;const shapes=(chart.layout.shapes||[]).filter(s=>!s.name?.startsWith('ss-selection-'));return window.Plotly.relayout(chart,{shapes:[...shapes,...selectionShapes()]});}).catch(fail);
 }
 function referenceList(codes){return `<div class="ss-reference-list">${codes.map(code=>`<button data-ss-area="${esc(code)}" title="${esc(model.nodes.get(code).name)}">${esc(code)}</button>`).join('')}</div>`;}
 function routeHTML(link){
  return `<ol class="ss-route">${link.nodes.map((n,i)=>`<li><span><b>${esc(n[0])}</b> · ${esc(n[1])}${data.node_names[n.join(':')]?' · '+esc(data.node_names[n.join(':')]):''}</span>${i<link.steps.length?(()=>{const step=data.route_steps[link.steps[i]],source=data.sources[step.source];return `<small>${esc(step.relation)} · ${source?`<a href="${esc(sourceURL(source))}">${esc(source.publisher||source.title)}</a>`:esc(step.source)} · ${esc(step.location)}${step.raw_type?' · '+esc(step.raw_type):''}${step.note?'<br>'+esc(step.note):''}</small>`;})():''}</li>`).join('')}</ol>`;
 }
 function resolutionDescription(cell){
  const reference=`${model.ref.short_label} ${model.ref.leaf_name}`;
  if(cell.splitCount)return {summary:`${cell.splitCount} native categories linked exclusively to this ${reference}`,context:''};
  const count=cell.matches.length,range=cell.minimum===cell.maximum?String(cell.maximum):`${cell.minimum}–${cell.maximum}`;
  const summary=`${count} native categor${count===1?'y':'ies'} linked to this ${reference}`;
  let context=`Within section ${cell.section}: ${range} linked ${model.ref.short_label} reference${cell.maximum===1?'':'s'} per native category.`;
  if(cell.matches.some(m=>m.outside.length))context+=' These categories also link outside this section; this is not an exclusive subdivision.';
  else if(cell.matches.some(m=>m.link.status==='partial'||m.link.exclusive_reference===false))context+=' Qualified links do not establish an exclusive subdivision.';
  return {summary,context};
 }
 function nativeHTML(match){
  const {native,inside,outside,link}=match;
  return `<details class="ss-native"><summary><b>${esc(native.code)}</b> · ${esc(native.name)}<small>Section footprint: ${match.count} / ${match.denominator}${outside.length?' · +'+outside.length+' outside section':''}</small></summary><p class="ss-relation">${esc(link.relation)}${link.status==='partial'?' · qualified / partial overlap':''}${link.mapping_origin==='reviewed_editorial'?' · editorial nxbase mapping':link.mapping_origin==='governed_nxbase'?' · existing nxbase parent chain':link.mapping_origin==='shared_exiobase_activity'?' · shared EXIOBASE activity correspondence':''}</p>${link.review_note?`<p>${esc(link.review_note)}</p>`:''}${native.production_review?`<details class="ss-intermediates"><summary>Qualified production review · separate from product paths</summary><p>${esc(native.production_review.basis)}</p><p>NACE Rev. 2.1 producer footprint: ${native.production_review.producer_scope[1].map(esc).join(', ')}.</p>${native.discarded_candidate_classes?`<p>${native.discarded_candidate_classes} incompatible joined candidate classes excluded.</p>`:''}<a href="${esc(sourceURL(data.sources.P19))}">Review definitions and source fingerprints</a></details>`:''}${native.lineage?`<details class="ss-intermediates"><summary>Existing nxbase parent lineage · context only</summary>${routeHTML(native.lineage)}</details>`:''}${link.historical_descriptors?.length?`<details><summary>Published GLORIA 97 → 120 descriptors</summary>${link.historical_descriptors.map(h=>`<p>${esc(h.code)} · ${esc(h.name)}<br><small>${esc(h.location)} · native positions ${h.native_positions.join(', ')}</small></p>`).join('')}</details>`:''}<p>Linked reference classes in this section</p>${referenceList(inside)}${outside.length?`<p>Also linked outside this section</p>${referenceList(outside)}`:''}<details class="ss-intermediates"><summary>Intermediate mappings &amp; sources</summary>${routeHTML(link)}${alternatives(link).length?`<details><summary>${alternatives(link).length} additional source routes</summary>${alternatives(link).map(routeHTML).join('')}</details>`:''}${link.evidence?.length?`<p>Definitions: ${link.evidence.map(id=>data.sources[id]).filter(Boolean).map(source=>`<a href="${esc(sourceURL(source))}">${esc(source.title)}</a>`).join(' · ')}</p>`:''}</details></details>`;
 }
 function pendingHTML(cell){
  if(!cell.pending.length)return '';
  return `<details class="ss-intermediates ss-pending-categories"><summary>${cell.pending.length} additional native categories awaiting review · excluded from the index</summary><p>The index describes the confirmed categories above. These candidates are kept separately because their current anchors do not establish exclusive containment.</p>${cell.pending.map(n=>`<details class="ss-native"><summary><b>${esc(n.code)}</b> · ${esc(n.name)}</summary><p>${esc(n.pending.review_note)}</p><p>Current nxbase anchor: ${esc(n.pending.nodes.at(-1)[1])}. Candidate classes: ${n.pending.references.map(esc).join(', ')}.</p><details class="ss-intermediates"><summary>Current nxbase path &amp; source</summary>${routeHTML(n.pending)}</details></details>`).join('')}</details>`;
 }
 function coarseHTML(cell){
  if(!cell.coarse.length)return '';
  const direct=cell.coarse.filter(n=>n.coarse.direct_nace);
  if(direct.length)return `<details class="ss-intermediates ss-section-anchors"><summary>${direct.length} native categories with a broader NACE anchor</summary><p>The nxbase parent is a container, not an enumeration of native member classes. These categories do not enter the colour index for ${esc(cell.code)}.</p>${direct.map(n=>`<details class="ss-native"><summary><b>${esc(n.code)}</b> · ${esc(n.name)}<small>NACE Rev. 2.1 · ${n.coarse.anchors.map(a=>esc(a.code)).join(' + ')}</small></summary><p>${esc(n.coarse.note)}</p>${n.coarse.anchors.map(routeHTML).join('')}</details>`).join('')}</details>`;

  return `<details class="ss-intermediates ss-section-anchors"><summary>${cell.coarse.length} native categories with a published broad section anchor</summary><p>These categories belong to a broader ISIC section that overlaps NACE section ${esc(cell.section)}. Their membership of ${esc(cell.code)} is unverified, so they do not enter the resolution index.</p>${cell.coarse.map(n=>`<details class="ss-native"><summary><b>${esc(n.code)}</b> · ${esc(n.name)}<small>ISIC Rev. 4 · ${n.coarse.anchors.map(a=>esc(a.code)).join(' + ')}</small></summary><p>${esc(n.coarse.note)}</p>${n.coarse.anchors.map(a=>`${routeHTML(a)}<p>Broad NACE Rev. 2.1 context: ${Object.keys(a.reference_context).map(esc).join(', ')} · via <a href="${esc(sourceURL(data.sources.S06))}">ISIC / NACE Rev. 2</a> and <a href="${esc(sourceURL(data.sources.S07))}">NACE revisions</a>.</p>`).join('')}</details>`).join('')}</details>`;
 }
 function unresolvedHTML(column){
  const native=column.native.filter(n=>n.unresolved);
  return native.length?`<details class="ss-intermediates ss-unresolved"><summary>${native.length} native categories without a current NACE Rev. 2.1 anchor</summary>${native.map(n=>`<details class="ss-native"><summary><b>${esc(n.code)}</b> · ${esc(n.name)}</summary><p>${esc(n.unresolved.review_note)}</p>${routeHTML(n.unresolved)}</details>`).join('')}</details>`:'';
 }
 function detail(){
  const row=model.nodes.get(selected);
  const column=columns.find(c=>c.id===selectedColumn);
  $('[data-ss-selection-status]').dataset.selected=String(!!row);
  $('[data-ss-selection-label]').textContent=row?`Selected: ${row.code}${column?' · '+column.label:''} — native-sector details below`:'Select a cell for native sectors.';
  $('[data-ss-show-details]').hidden=!row;
  $('[data-ss-detail]').hidden=!row;
  if(!row){$('[data-ss-detail]').innerHTML='';return;}
  const chain=M.ancestors(model,selected);
  $('[data-ss-detail]').innerHTML=`<div class="ss-detail-heading"><div><small>Native representation · ${chain.map(n=>esc(n.code)).join(' › ')}</small><h3>${esc(row.code)} · ${esc(row.name)}</h3></div><button data-ss-close aria-label="Close class details">×</button></div><p class="ss-denominator">Section ${row.section} contains ${model.ref.section_counts[row.section]} reference classes. This denominator stays fixed when narrowing the view.</p><div class="ss-native-comparison">${columns.map(column=>{
    const cell=M.cell(model,column,selected),link=column.guide?new URL(column.guide,base):column.source_url;
    return `<section class="ss-database-detail ${column.id===selectedColumn?'ss-active-database':''}" data-ss-native-database="${esc(column.id)}"><div class="ss-native-heading"><strong>${esc(column.label)}</strong><span>${column.native_count} native categories</span></div>${cell.matches.length?`<p class="ss-resolution"><b>${M.resolutionLabel(cell)}</b> · ${esc(resolutionDescription(cell).summary)}</p>${resolutionDescription(cell).context?`<p class="ss-resolution-context">${esc(resolutionDescription(cell).context)}</p>`:''}`+cell.matches.map(nativeHTML).join(''):'<p class="ss-pending">Fine concordance unverified. No absence is inferred.</p>'}${pendingHTML(cell)}${coarseHTML(cell)}${unresolvedHTML(column)}${column.note?`<p class="ss-column-note">${esc(column.note)}</p>`:''}<details class="ss-profile"><summary>Versions &amp; set list</summary><p>${esc(column.releases.join(' · ')||'No separate release')} · ${esc(column.units)} · ${esc(period(column.years))}</p><a href="${esc(new URL(column.workbook,base))}" download>Native sets · Excel</a>${link?` · <a href="${esc(link)}">${column.guide?'Parsing guide':'Source'}</a>`:''}</details></section>`;
   }).join('')}</div>`;
 }
 function bind(){
  root.addEventListener('input',event=>{if(event.target.matches('[data-ss-search]'))picker();});
  root.addEventListener('change',event=>{
   if(event.target.matches('[data-ss-labels]')){level=Number(event.target.value);render().catch(fail);}
   if(event.target.matches('[data-ss-column]')){event.target.checked?enabled.add(event.target.dataset.ssColumn):enabled.delete(event.target.dataset.ssColumn);render().catch(fail);}
  });
  root.addEventListener('click',event=>{
   const b=event.target.closest('button');if(!b)return;
   if(b.hasAttribute('data-ss-area')){area=b.dataset.ssArea;const current=model.nodes.get(area);selected=current?.level===model.ref.leaf_level?area:'';selectedColumn='';$('[data-ss-search]').value='';picker();render().catch(fail);if(current?.level===model.ref.leaf_level)$('[data-ss-picker]').open=false;}
   if(b.hasAttribute('data-ss-select')){enabled=b.dataset.ssSelect==='all'?new Set(model.columns.map(c=>c.id)):new Set();databaseList();render().catch(fail);}
   if(b.hasAttribute('data-ss-kind'))changeKind(b.dataset.ssKind);
   if(b.hasAttribute('data-ss-close')){selected='';selectedColumn='';detail();highlight();}
   if(b.hasAttribute('data-ss-show-details'))$('[data-ss-detail]').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'start'});
   if(b.hasAttribute('data-ss-zoom')){
    const chart=$('[data-ss-chart]');if(!columns.length)return;
    const request=generation,viewKey=kind+'|'+area+'|'+columns.map(c=>c.id).join(','),end=coordinates.end,action=b.dataset.ssZoom;
    chart.setAttribute('aria-busy','true');
    operations=operations.then(()=>{
     if(chart.dataset.ssView!==viewKey)return;
     const range=chart.layout.yaxis.range||[end,0],centre=(range[0]+range[1])/2,half=(range[0]-range[1])/2*(action==='in'?.5:2);
     return window.Plotly.relayout(chart,{'yaxis.range':action==='reset'?[end,0]:[Math.min(end,centre+half),Math.max(0,centre-half)]});
    }).then(()=>{if(request===generation)chart.setAttribute('aria-busy','false');}).catch(fail);
   }
  });
  document.addEventListener('click',event=>{const within=selector=>event.composedPath().some(n=>n.matches?.(selector));if(!within('[data-ss-picker]'))$('[data-ss-picker]').open=false;if(!within('[data-ss-databases]'))$('[data-ss-databases]').open=false;});
  root.addEventListener('keydown',event=>{if(event.key==='Escape'){root.querySelectorAll('details[open]').forEach(d=>{if(d.closest('.ss-controls'))d.open=false;});}});
 }
 // Start when near the viewport: geography and indicator browsers stay responsive.
 if(initialAnchor)mount();
 else if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){observer.disconnect();mount();}},{rootMargin:'500px'});observer.observe(root);}else mount();
})();
