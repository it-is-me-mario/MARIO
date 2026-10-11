/* Country-first browser: parsed scope metadata and explicit classification links. */
((global)=>{
 'use strict';
 const S=global.MarioCountryScope;
 const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const period=ys=>{const sorted=[...new Set(ys)].sort((a,b)=>a-b),parts=[];let first=sorted[0],last=first;for(const y of [...sorted.slice(1),null]){if(y===last+1){last=y;continue;}parts.push(first===last?String(first):`${first}–${last}`);first=last=y;}return parts.join(', ');};
 function mount(node,{load,base,onCountry,onTab,onIndicators}){
  let data,loading,country='ITA',tab='scope',year='all',older=false,classification='',code='',parent=null,search='',level='all',token=0,visible=[];
  const $=selector=>node.querySelector(selector);
  async function ensure(){
   if(data)return;
   if(!loading)loading=load('data/economy/country-scope.json').then(value=>{
    data={...value,profiles:value.profiles.filter(global.MarioEconomy.isMRIO)};
   }).catch(e=>{loading=null;throw e;});
   await loading;
  }
  node.innerHTML=`<div class="cf-header"><div class="eb-multi-field cf-country-field"><span>Country / territory</span><details class="eb-picker" data-cf-country-picker><summary data-cf-country-summary>Choose a country…</summary><input type="search" data-cf-country-search aria-label="Find a country" placeholder="Search name or ISO code…"><div class="eb-picker-options" data-cf-countries></div></details></div><div class="eb-toggle" role="group" aria-label="Country exploration"><button data-cf-tab="scope" aria-pressed="true">Scope</button><button data-cf-tab="indicators" aria-pressed="false">Indicators</button></div></div><div data-cf-scope><p class="eb-note" data-cf-status role="status">Choose a country to compare its representation in the available databases.</p><div data-cf-content hidden><div class="cf-controls"><label>Data year<select data-cf-year></select></label><label>Classification<select data-cf-classification></select></label><label class="cf-older"><input type="checkbox" data-cf-older>Include all versions</label></div><div class="cf-chart" data-cf-chart-wrap hidden><div data-cf-chart></div></div><div class="cf-comparison"><aside class="cf-taxonomy" data-cf-taxonomy hidden><div class="cf-taxonomy-controls"><label>Code level<select data-cf-level title="Limits which classification codes are shown; it does not aggregate indicator values."></select></label><label>Code or name<input type="search" data-cf-search placeholder="e.g. A, 01.11.11, wheat…"></label></div><p class="cf-tree-help">Choose a code to compare how databases represent it. A click also opens its subcategories.</p><div class="cf-selected" data-cf-selected hidden></div><button class="cf-all" data-cf-all hidden>Clear sector filter</button><nav class="cf-breadcrumbs" data-cf-breadcrumbs aria-label="Classification path"></nav><div class="cf-tree" data-cf-tree></div><p class="eb-note" data-cf-tree-note></p></aside><div class="cf-results"><div class="cf-result-heading"><h3 data-cf-heading></h3><span data-cf-count></span></div><div data-cf-results></div><p class="eb-note cf-year-note" data-cf-year-note hidden></p></div></div><p class="eb-note cf-method" data-cf-method></p><div class="eb-actions"><button data-cf-export>Download scope · CSV</button><a data-cf-excel href="${new URL('_static/data/economy/classification-concordances.xlsx',base)}" download hidden>NACE / CPA concordances · Excel ↗</a></div><details class="eb-other-notes"><summary>Sources and classification notes</summary><div data-cf-sources></div></details></div></div><p class="eb-note" data-cf-indicator-note hidden>Whole-economy indicators for the selected country. Detailed classification queries describe representation and do not split native economic or emission values.</p>`;
  function countryList(){
   const query=$('[data-cf-country-search]').value.trim().toLowerCase();
   $('[data-cf-countries]').innerHTML=S.countries(data.profiles).filter(c=>`${c.id} ${c.name}`.toLowerCase().includes(query)).map(c=>`<button type="button" data-cf-country="${esc(c.id)}" aria-pressed="${c.id===country}">${esc(c.name)} <small>${esc(c.id)}</small></button>`).join('')||'<p class="eb-note">No matching country.</p>';
  }
  function tree(){
   const c=data.classifications[classification];if(!c)return;
   const names={1:'Sections',2:'Divisions · 2 digits',3:'Groups · 3 digits',4:'Classes · 4 digits',5:'Categories · 5 digits',6:'Subcategories · 6 digits'};
   $('[data-cf-level]').innerHTML='<option value="all">All levels</option>'+c.levels.map(l=>`<option value="${l}" ${String(l)===level?'selected':''}>${names[l]}</option>`).join('');
   const query=search.trim().toLowerCase();
   const nodes=c.nodes.filter(n=>(level==='all'||n.level===Number(level))&&(query?`${n.code} ${n.name}`.toLowerCase().includes(query):level==='all'?n.parent===parent:true));
   const parentNode=c.nodes.find(n=>n.code===parent),chain=parentNode?[...S.ancestors(c,parent)].reverse():[];
   $('[data-cf-breadcrumbs]').innerHTML=`<button data-cf-parent="">All sections</button>`+chain.map(id=>`<span>›</span><button data-cf-parent="${esc(id)}">${esc(id)}</button>`).join('');
   $('[data-cf-tree]').innerHTML=nodes.slice(0,150).map(n=>{const children=c.nodes.some(child=>child.parent===n.code);return `<div class="cf-node"><button data-cf-code="${esc(n.code)}" aria-pressed="${code===n.code}"><b>${esc(n.code)}</b><span class="cf-node-name">${esc(n.name)}</span>${children?'<span class="cf-expand" aria-hidden="true">›</span>':''}</button></div>`;}).join('')||'<p class="eb-note">No matching classification codes.</p>';
   const selectedNode=c.nodes.find(n=>n.code===code);
   $('[data-cf-selected]').hidden=!selectedNode;
   $('[data-cf-selected]').innerHTML=selectedNode?`<small>Selected code</small><strong>${esc(selectedNode.code)} · ${esc(selectedNode.name)}</strong>`:'';
   $('[data-cf-all]').hidden=!selectedNode;
   $('[data-cf-tree-note]').textContent=nodes.length>150?'Showing the first 150 matches; refine the search.':'';
  }
  const setCount=value=>value==null?'not provided':value;
  const range=values=>{const ns=[...new Set(values.filter(v=>v!=null))].sort((a,b)=>a-b);return ns.length?ns[0]===ns.at(-1)?String(ns[0]):`${ns[0]}–${ns.at(-1)}`:'not provided';};
  const variant=p=>[p.release,p.units,p.price_basis,p.format,p.system].filter(Boolean).join(' · ');
  function nativeMatches(matches,limit=3,showRelation=true){
   const routeHTML=e=>{const route=data.mapping_routes?.[e.route_id];if(!route)return '';return `<details class="cf-route"><summary>Mapping &amp; sources</summary><p>${route.nodes.map(n=>n[0]==='NXB'&&data.mapping_node_names?.[n.join(':')]?`<span title="${esc(n.join(':'))}">NXB · ${esc(data.mapping_node_names[n.join(':')])}</span>`:`${esc(n[0])}:${esc(n[1])}`).join(' → ')}</p>${e.review_note?`<p>${esc(e.review_note)}</p>`:''}<ol>${route.steps.map(id=>{const s=data.mapping_route_steps[id],source=data.mapping_sources[s.source];return `<li>${esc(s.relation)} · <a href="${esc(new URL(source.url,new URL('_static/data/economy/',base)))}">${esc(source.publisher||s.source)}</a> · ${esc(s.location)}</li>`;}).join('')}</ol></details>`;};
   const item=e=>`<li><b>${esc(e.native_code)}</b> · ${esc(e.native_label===e.native_code&&e.native_description?e.native_description:e.native_label)}${showRelation?`<small>${esc(e.relation)}${e.precision==='partial'?' · qualified overlap':''}${e.mapping_origin==='reviewed_editorial'?' · editorial nxbase mapping':e.mapping_origin==='governed_nxbase'?' · nxbase parent chain':e.mapping_origin==='shared_exiobase_activity'?' · shared EXIOBASE activity correspondence':''}</small>`:''}${routeHTML(e)}</li>`;
   return `<ul class="cf-native-matches">${matches.slice(0,limit).map(item).join('')}</ul>${matches.length>limit?`<details class="cf-more-matches"><summary>Show ${matches.length-limit} more categories</summary><ul class="cf-native-matches">${matches.slice(limit).map(item).join('')}</ul></details>`:''}`;
  }
  function familyRepresentation(profiles){
   const c=data.classifications[classification], groups=new Map();
   for(const p of profiles){
    const result=S.query(p,country,c,code,data.mappings);
    const signature=e=>[e.native_code,e.native_label,e.relation,e.precision,e.route_id,e.mapping_origin];
    const key=JSON.stringify([result.status,result.reason,result.ancestor?.code,result.matches.map(signature),(result.coarse_matches||[]).map(signature),result.complete]);
    if(!groups.has(key))groups.set(key,{result,profiles:[]});
    groups.get(key).profiles.push(p);
   }
   return [...groups.values()].map(({result,profiles:ps})=>{
    const labels=[...new Set(ps.map(p=>[p.variant,p.units,p.format,p.system].filter(Boolean).join(' · ')))];
    const label=groups.size>1?`<p class="cf-mapping-variant">${esc(labels.join(' / '))}</p>`:'';
    if(result.status==='coarse')return `<div class="cf-representation cf-coarse">${label}<p><strong>Detailed mapping unavailable</strong></p><p class="cf-mapping-note">Known broader scope: ${(result.broaderAnchors||[result.ancestor]).map(n=>`${esc(n.code)} · ${esc(n.name)}`).join('; ')}</p>${result.matches.length===1?nativeMatches(result.matches,1,false):`<details class="cf-more-matches"><summary>${result.matches.length} native categories with a broader anchor</summary>${nativeMatches(result.matches,result.matches.length,false)}</details>`}</div>`;
    if(result.status!=='mapped')return `<div class="cf-representation cf-unverified">${label}<p>Correspondence to ${esc(c.label)} unavailable.</p></div>`;
    return `<div class="cf-representation">${label}<p class="cf-mapping-count"><strong>${result.matches.length}</strong> linked native ${result.matches.length===1?'category':'categories'}${result.matches.some(e=>e.precision==='partial')?' · qualified overlap':result.complete||result.matches.every(e=>e.precision)?'':' · partial correspondence'}</p>${nativeMatches(result.matches)}${result.coarse_matches?.length?`<details class="cf-more-matches"><summary>${result.coarse_matches.length} broader anchors · leaf membership unverified</summary>${nativeMatches(result.coarse_matches,result.coarse_matches.length)}</details>`:''}</div>`;
   }).join('');
  }
  function profileDetails(p){
   const counts=S.counts(p,country),ys=S.years(p),availableIds=p.reading_ids.filter(id=>year==='all'||p.reading_years[id]===Number(year)),numeric=availableIds.length>0;
   const satellite=p.set_flags['Satellite account']?.status==='not_loaded'?'not loaded':counts['Satellite account']==null?'not provided':`${counts['Satellite account']} accounts`;
   const dimensions=['Sector','Activity','Commodity'].filter(k=>k in counts).map(k=>`<span><b>${counts[k]}</b> ${k==='Sector'?'sectors':k==='Activity'?'activities':'commodities'}</span>`).join('');
   return `<article class="cf-profile" data-cf-profile="${esc(p.id)}"><div class="cf-profile-title"><b>${esc(variant(p))}</b><span>${p.status==='source_verified'?'Base year ':''}${esc(period(ys))}</span></div><div class="cf-stats"><span><b>${counts.Region}</b> regions</span>${dimensions}<span>Satellite: <b>${esc(satellite)}</b></span></div><details class="cf-set-details"><summary>Native set lists</summary><p>Factors of production: ${setCount(counts['Factor of production'])} · Final-demand categories: ${setCount(counts['Consumption category'])}.${p.set_flags['Satellite account']?.status==='not_loaded'?' Satellite accounts were not loaded.':''}</p>${['Sector','Activity','Commodity','Satellite account','Factor of production','Consumption category'].filter(k=>p.sets[k]?.length&&p.set_flags[k]?.status!=='not_loaded').map(k=>`<details data-cf-set-list="${esc(k)}" data-cf-set-profile="${esc(p.id)}"><summary>${esc(k)} · ${['Sector','Activity','Commodity'].includes(k)?S.nativeSet(p,country,k).length:p.sets[k].length}</summary><ul></ul></details>`).join('')}</details><div class="cf-row-links">${p.guide?`<a href="${new URL(p.guide,base)}">Parsing guide ↗</a>`:`<a href="${esc(p.source_url)}">Source ↗</a>`}<a href="${new URL(p.workbook,base)}" download>Native sets · Excel ↗</a><button data-cf-indicators="${esc(p.id)}" ${numeric?'':'disabled'} title="${numeric?'Explore country indicators for this reading':p.parser_supported===false?'MARIO has no parser for this database; only source-verified scope is available':'Numerical results are unavailable in the public browser'}">Indicators →</button></div></article>`;
  }
  function familyVersions(profiles){
   const hasVersions=profiles.some(p=>p.release),showUnits=new Set(profiles.map(p=>p.units)).size>1,showFormats=!hasVersions||new Set(profiles.map(p=>p.format)).size>1,showSystems=!hasVersions||new Set(profiles.map(p=>p.system).filter(Boolean)).size>1,groups=new Map();
   for(const p of profiles){const key=JSON.stringify([p.release,p.units,p.price_basis]);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(p);}
   return [...groups.values()].map(ps=>[ps[0].release,ps[0].price_basis,showUnits?ps[0].units:null,showFormats?[...new Set(ps.map(p=>p.format))].join(' / '):null,showSystems?[...new Set(ps.map(p=>p.system).filter(Boolean))].join(' / '):null].filter(Boolean).join(' · ')).join('; ');
  }
  function familyOverview(f){
   const ps=visible.filter(p=>p.family===f),counts=ps.map(p=>S.counts(p,country));
   const metrics=[['Region','regions'],['Sector','sectors'],['Activity','activities'],['Commodity','commodities']].filter(([key])=>counts.some(c=>key in c)).map(([key,label])=>`<span><b>${range(counts.map(c=>c[key]))}</b> ${label}</span>`).join('');
   const satellite=ps.every(p=>p.set_flags['Satellite account']?.status==='not_loaded')?'not loaded':range(counts.map(c=>c['Satellite account']));
   const versions=familyVersions(ps),ys=year==='all'?[...new Set(ps.flatMap(S.years))]:[Number(year)],sourceOnly=ps.every(p=>p.parser_supported===false);
   const first=ps[0],numeric=ps.some(p=>p.reading_ids.some(id=>(year==='all'||p.reading_years[id]===Number(year))));
   const readings=ps.flatMap(p=>p.reading_ids.filter(id=>year==='all'||p.reading_years[id]===Number(year)).map(id=>p.availability[id]));
   const indicators=['gdp','value_added','ghg'].filter(metric=>readings.some(a=>a[metric])).map(metric=>({gdp:'GDP',value_added:'VA',ghg:'GHG'}[metric]));
   return `<section class="cf-family" data-cf-family="${esc(f)}"><div class="cf-family-row"><div class="cf-database-cell"><h4>${esc(f==='OECD'?'OECD ICIO':f)}</h4>${versions?`<p class="cf-versions">${esc(versions)}</p>`:""}<p class="cf-family-years">${sourceOnly?'Base year ':''}${esc(period(ys))}${numeric?' · '+esc(indicators.join(' / ')):''}</p>${sourceOnly?`<p class="cf-source-status">No MARIO parser · <a class="cf-source-link" href="${esc(first.source_url)}">Source ↗</a></p>`:numeric?'':`<p class="cf-indicator-status">${ps.some(p=>p.numeric_publication===false)?'<a href="'+esc(first.license_url)+'">Licensed source</a> · numerical indicators not published':'Public indicators unavailable'}</p>`}</div><div class="cf-scope-cell">${metrics}<span>Satellite: <b>${esc(satellite)}</b></span></div>${code?`<div class="cf-mapping-cell">${familyRepresentation(ps)}</div>`:''}</div><details class="cf-family-details"><summary>${ps.some(p=>p.release)?"Version details, set lists":"Set lists"} &amp; downloads</summary>${ps.map(profileDetails).join('')}</details></section>`;
  }
  const indicatorNames={gdp:'GDP',value_added:'VA',ghg:'GHG'};
  const environmental=p=>typeof p.environmental==='boolean'?p.environmental:(p.counts['Satellite account']||0)>0&&p.set_flags['Satellite account']?.status!=='not_loaded';
  function chartHover(p,y,c){
   const name=p.family==='OECD'?'OECD ICIO':p.family,rid=p.reading_ids.find(id=>p.reading_years[id]===y),a=rid&&p.availability[rid];
   const economic=[['Sector','sectors'],['Activity','activities'],['Commodity','commodities']].filter(([k])=>c[k]!=null).map(([k,l])=>`${c[k].toLocaleString()} ${l}`).join(' · ');
   const satellite=p.set_flags['Satellite account']?.status==='not_loaded'?'not loaded':c['Satellite account']==null?'not provided':`${c['Satellite account'].toLocaleString()} accounts`;
   const indicators=a?['gdp','value_added','ghg'].filter(m=>a[m]).map(m=>indicatorNames[m]).join(' / '):'';
   return [`<b>${esc(name)}${p.release?' '+esc(p.release):''}</b> · ${p.status==='source_verified'?'base year ':''}${y}`,
    esc([p.units,p.format,p.system,p.price_basis].filter(Boolean).join(' · ')),
    `${esc(economic)} in this country`,
    `${c.Region} regions · Satellite: ${esc(satellite)}`,
    indicators?`Indicators: ${indicators}`:'Public indicators unavailable',
    p.status==='source_verified'?(p.parser_supported===false?'Source metadata · no MARIO parser':'Native metadata · MARIO parser available'):'Verified MARIO parse'].join('<br>');
  }
  function chart(){
   const wrap=$('[data-cf-chart-wrap]'),el=$('[data-cf-chart]');
   const points=visible.flatMap(p=>{const c=S.counts(p,country),n=c.Sector??c.Activity;return n==null?[]:S.years(p).map(y=>({p,c,n,year:y}));});
   wrap.hidden=!global.Plotly||!points.length;
   if(wrap.hidden)return;
   // Readings with the same year and a similar count are spread sideways so none hides another.
   const buckets=new Map();
   for(const q of points){const k=`${q.year}|${Math.round(Math.log(Math.max(q.n,1))/.04)}`;if(!buckets.has(k))buckets.set(k,[]);buckets.get(k).push(q);}
   for(const group of buckets.values()){const ids=[...new Set(group.map(q=>q.p.id))],step=ids.length>1?Math.min(.18,.6/(ids.length-1)):0;for(const q of group)q.x=q.year+(ids.indexOf(q.p.id)-(ids.length-1)/2)*step;}
   const css=getComputedStyle(wrap),get=n=>css.getPropertyValue(n).trim();
   const colors={background:get('--surface-2'),surface:get('--surface'),ink:get('--ink'),muted:get('--ink-muted'),grid:get('--line'),font:css.fontFamily,extended:get('--cf-extended'),base:get('--cf-base')};
   const families=[...new Set(points.map(q=>q.p.family))],symbols=['circle','square','diamond','triangle-up','triangle-down','pentagon','hexagon','star','hourglass','cross','x'];
   const traces=families.flatMap((f,i)=>{
    const symbol=symbols[i%symbols.length],group=points.filter(q=>q.p.family===f),label=f==='OECD'?'OECD ICIO':f;
    const lines=[...new Set(group.map(q=>q.p.id))].map(id=>group.filter(q=>q.p.id===id).sort((a,b)=>a.year-b.year)).filter(g=>g.length>1).map(g=>({type:'scatter',mode:'lines',x:g.map(q=>q.x),y:g.map(q=>q.n),legendgroup:f,showlegend:false,hoverinfo:'skip',line:{color:colors.ink,width:1},opacity:.14}));
    const fill=q=>environmental(q.p)?colors.extended:colors.base,open=q=>q.p.parser_supported===false;
    return [...lines,
     {type:'scatter',mode:'markers',x:[null],y:[null],name:label,legendgroup:f,showlegend:true,hoverinfo:'skip',marker:{color:colors.ink,symbol,size:10}},
     {type:'scatter',mode:'markers',x:group.map(q=>q.x),y:group.map(q=>q.n),name:label,legendgroup:f,showlegend:false,
      customdata:group.map(q=>[chartHover(q.p,q.year,q.c),q.p.id]),hovertemplate:'%{customdata[0]}<extra></extra>',
      marker:{size:12,symbol:group.map(q=>open(q)?symbol+'-open':symbol),color:group.map(fill),opacity:group.map(q=>year==='all'||q.year===Number(year)?1:.25),
       line:{color:group.map(q=>open(q)?fill(q):colors.background),width:group.map(q=>open(q)?2:1)}}}];
   });
   const ys=points.map(q=>q.year),lo=Math.min(...ys),hi=Math.max(...ys),pad=hi-lo<4?2:.8;
   const ns=points.map(q=>q.n),nLo=Math.max(1,Math.min(...ns)),nHi=Math.max(...ns),yticks=[1,2,5,10,20,50,100,200,500,1000,2000,5000,10000].filter(v=>v>=nLo/1.3&&v<=nHi*1.3);
   const axis={gridcolor:colors.grid,showline:true,linecolor:colors.ink,linewidth:1.5,zeroline:false,automargin:true};
   const place=S.countries(data.profiles).find(c=>c.id===country)?.name||country;
   const context=[`${families.length} ${families.length===1?'database':'databases'}`,`data years ${period(ys)}`,year==='all'?'':`highlighted: ${year}`,older?'all versions':'latest versions'].filter(Boolean).join(' · ');
   const key=`<span style="color:${colors.extended}">●</span> Environmental data included    <span style="color:${colors.base}">●</span> No environmental accounts    ○ No MARIO parser`;
   const layout={height:480,autosize:true,paper_bgcolor:colors.background,plot_bgcolor:colors.background,font:{family:colors.font,color:colors.ink,size:12},margin:{l:65,r:20,t:100,b:90},
    title:{text:`<b>Native sector detail · ${esc(place)}</b>`,font:{size:16,color:colors.ink},subtitle:{text:esc(context),font:{size:12,color:colors.muted}},xref:'container',x:0,xanchor:'left',yref:'container',y:1,yanchor:'top',pad:{l:18,t:18}},
    annotations:[{text:key,xref:'paper',x:0,xanchor:'left',yref:'paper',y:1,yanchor:'bottom',yshift:14,showarrow:false,font:{size:11,color:colors.muted}}],
    xaxis:{...axis,title:{text:'Data year',standoff:12},range:[lo-pad,hi+pad],tickformat:'d',nticks:9},
    yaxis:{...axis,title:{text:'N. sectors (SUT: activities)',standoff:12},type:'log',range:[Math.log10(nLo/1.3),Math.log10(nHi*1.3)],tickmode:'array',tickvals:yticks,ticktext:yticks.map(v=>v.toLocaleString())},
    hovermode:'closest',hoverlabel:{align:'left',bgcolor:colors.surface,bordercolor:colors.grid,font:{color:colors.ink}},legend:{orientation:'h',y:-.25,x:0,groupclick:'togglegroup'},dragmode:'zoom',uirevision:country};
   el.setAttribute('aria-label',`Native sector detail by data year for the selected country, one marker per database reading.`);
   global.Plotly.react(el,traces,layout,{responsive:true,showTips:false,displaylogo:false,doubleClick:'autosize',modeBarButtonsToRemove:['select2d','lasso2d'],toImageButtonOptions:{filename:`mario-${country}-sector-detail`,format:'png',scale:2}});
   if(!el._cfBound){el._cfBound=true;el.on('plotly_click',ev=>{const id=ev.points[0]?.customdata?.[1],card=id&&node.querySelector(`[data-cf-profile="${CSS.escape(id)}"]`);if(!card)return;card.closest('details').open=true;card.scrollIntoView({block:'center',behavior:'smooth'});card.classList.remove('cf-flash');void card.offsetWidth;card.classList.add('cf-flash');});}
  }
  function cards(){
   visible=S.visibleProfiles(data.profiles,{country,year,older});
   const groups=[...new Set(visible.map(p=>p.family))];
   $('[data-cf-heading]').textContent=code?`${code} · ${data.classifications[classification].nodes.find(n=>n.code===code)?.name||code}`:classification?'Choose a code to compare · overall scope below':'Database scope';
   $('[data-cf-count]').textContent=`${groups.length} databases`;
   $('[data-cf-results]').classList.toggle('cf-has-mapping',!!code);
   $('[data-cf-results]').innerHTML=groups.length?`<div class="cf-column-heads"><span>Database</span><span>Native scope</span>${code?'<span>Native representation of the selected code</span>':''}</div>`+groups.map(familyOverview).join(''):'<p class="eb-empty">No individually represented country observation for this selection.</p>';
   chart();
   const missing=year==='all'?[]:[...new Set(data.profiles.filter(p=>S.countryRegions(p,country).length&&!groups.includes(p.family)).map(p=>p.family))];
   $('[data-cf-year-note]').hidden=!missing.length;
   $('[data-cf-year-note]').textContent=missing.length?`No ${year} scope inventory for: ${missing.map(f=>{const ps=data.profiles.filter(p=>p.family===f);return f==='CEDA'?`CEDA (base year ${period(ps.flatMap(S.years))})`:f;}).join(', ')}.`:'';
   $('[data-cf-method]').textContent=code?'Native representation is shown beside each database. Detailed matches and known broader sections are distinguished; unverified allocation is not zero coverage. This view does not disaggregate GDP or GHG.':'Regions describe the entire database; economic categories describe the selected country. Ranges reflect the displayed versions and years. Expand a database for individual inventories and downloads.';
   const cls=data.classifications[classification];
   $('[data-cf-excel]').hidden=!cls;
   $('[data-cf-sources]').innerHTML=`<p>Counts and native set lists come from verified MARIO parses or documented source inventories. Unchanged classifications share set profiles across years.</p>${cls?`<p><a href="${esc(cls.source_url)}">${esc(cls.label)} · classification source</a>. Each revision is treated separately; cross-revision equivalence is not inferred.</p>`:''}<p>Detailed CPA 2002 links use the supplied EXIOBASE correspondence and its explicit product-code/name bridge to EXIOBASE 3. It covers part of the native classification; source links do not assert exact equivalence or provide allocation weights. NACE Rev. 1.1 links are verified at section level only. For a finer code, broader section categories are context, not a verified allocation of that code.</p>`+visible.filter(p=>p.status==='source_verified').map(p=>`<p><a href="${esc(p.source_url)}">${esc(p.family)} · source</a> · <a href="${esc(p.license_url)}">Source licence</a>. ${esc(p.attribution)} ${esc(p.scope_note)}</p>`).join('');
  }
  async function render(){
   const request=++token;node.setAttribute('aria-busy','true');
   try{await ensure();}catch(e){$('[data-cf-status]').textContent=`Country scope could not load. ${e.message}`;node.setAttribute('aria-busy','false');return;}
   if(request!==token)return;
   countryList();const selected=S.countries(data.profiles).find(c=>c.id===country);
   $('[data-cf-country-summary]').textContent=selected?.name||'Choose a country…';
   $('[data-cf-scope]').hidden=tab!=='scope';$('[data-cf-indicator-note]').hidden=tab!=='indicators';
   $('[data-cf-content]').hidden=!selected;
   $('[data-cf-status]').hidden=!!selected;
   node.querySelectorAll('[data-cf-tab]').forEach(b=>{b.setAttribute('aria-pressed',b.dataset.cfTab===tab);b.disabled=b.dataset.cfTab==='indicators'&&!selected;});
   if(selected){
    const pool=data.profiles.filter(p=>S.countryRegions(p,country).length), ys=[...new Set(pool.flatMap(S.years))].sort((a,b)=>b-a);
    if(year!=='all'&&!ys.includes(Number(year)))year='all';
    $('[data-cf-year]').innerHTML='<option value="all">Any available year</option>'+ys.map(y=>`<option value="${y}" ${String(year)===String(y)?'selected':''}>${y}</option>`).join('');
    const clsIds=[...new Set(S.visibleProfiles(data.profiles,{country,year,older}).flatMap(p=>(p.mapping_ids || [p.mapping]).map(id=>data.mappings[id]?.classification)).filter(Boolean))];
    if(classification&&!clsIds.includes(classification)){classification='';code='';parent=null;}
    $('[data-cf-classification]').innerHTML='<option value="">Native sets</option>'+clsIds.map(id=>`<option value="${id}" ${classification===id?'selected':''}>${esc(data.classifications[id].label)}</option>`).join('');
    $('[data-cf-taxonomy]').hidden=!classification;
    if(classification)tree();cards();
   }
   onTab(tab,country);node.setAttribute('aria-busy','false');
  }
  node.addEventListener('toggle',e=>{const el=e.target;if(el.open&&el.dataset.cfSetList&&!el.dataset.loaded){const p=data.profiles.find(p=>p.id===el.dataset.cfSetProfile);el.querySelector('ul').innerHTML=(['Sector','Activity','Commodity'].includes(el.dataset.cfSetList)?S.nativeSet(p,country,el.dataset.cfSetList):p.sets[el.dataset.cfSetList]).map(label=>`<li>${p.native_codes?.[label]?`<b>${esc(p.native_codes[label])}</b> · `:''}${esc(label)}</li>`).join('');el.dataset.loaded='true';}},true);
  node.addEventListener('input',e=>{if(e.target.matches('[data-cf-country-search]'))countryList();if(e.target.matches('[data-cf-search]')){search=e.target.value;tree();}});
  node.addEventListener('change',e=>{
   e.stopPropagation();
   if(!e.target.matches('[data-cf-year],[data-cf-classification],[data-cf-older],[data-cf-level]'))return;
   if(e.target.matches('[data-cf-year]'))year=e.target.value;
   if(e.target.matches('[data-cf-classification]')){classification=e.target.value;code='';parent=null;search='';level='all';$('[data-cf-search]').value='';}
   if(e.target.matches('[data-cf-older]'))older=e.target.checked;
   if(e.target.matches('[data-cf-level]')){level=e.target.value;tree();return;}
   render();
  });
  node.addEventListener('click',e=>{
   e.stopPropagation();const b=e.target.closest('button');if(!b||b.disabled)return;
   if(b.dataset.cfCountry){country=b.dataset.cfCountry;year='all';$('[data-cf-country-picker]').open=false;onCountry(country);render();}
   if(b.dataset.cfTab){tab=b.dataset.cfTab;render();}
   if(b.dataset.cfCode){code=b.dataset.cfCode;const c=data.classifications[classification],n=c.nodes.find(n=>n.code===code);parent=c.nodes.some(child=>child.parent===code)?code:n.parent;search='';level='all';$('[data-cf-search]').value='';cards();tree();}
   if(b.hasAttribute('data-cf-parent')){parent=b.dataset.cfParent||null;code=parent||'';search='';level='all';$('[data-cf-search]').value='';cards();tree();}
   if(b.hasAttribute('data-cf-all')){code='';parent=null;search='';level='all';$('[data-cf-search]').value='';tree();cards();}
   if(b.dataset.cfIndicators){const p=data.profiles.find(p=>p.id===b.dataset.cfIndicators);tab='indicators';onIndicators(p,country,year);render();}
   if(b.hasAttribute('data-cf-export')){
    const records=visible.map(p=>{const c=S.counts(p,country),result=code?S.query(p,country,data.classifications[classification],code,data.mappings):null;return {country,database:p.family,version:p.release,units:p.units,table_format:p.format,system:p.system||'',years:period(p.years),regions:c.Region,sectors:c.Sector??'',activities:c.Activity??'',commodities:c.Commodity??'',satellite_accounts:c['Satellite account']??'',factors:c['Factor of production']??'',final_demand_categories:c['Consumption category']??'',classification:classification||'',code,matched_native_categories:result?.status==='mapped'?result.matches.length:'',mapping_status:result?.status||'',native_matches:result?.matches.map(e=>`${e.native_code}: ${e.native_label} (${e.relation})`).join('; ')||'',source_url:p.source_url||'',source_license:p.license_url||'',attribution:p.attribution||''};});
    if(!records.length)return;
    const cell=v=>'"'+String(v??'').replace(/^[=+@\t\r]/,m=>"'"+m).replace(/"/g,'""')+'"';
    const csv='\ufeff'+[Object.keys(records[0]),...records.map(Object.values)].map(row=>row.map(cell).join(',')).join('\r\n');
    const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=`mario-${country}-scope.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
   }
  });
  const redraw=()=>{if(data&&!$('[data-cf-chart-wrap]').hidden)chart();};
  new MutationObserver(redraw).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change',redraw);
  return {async activate(requested){await ensure();if(requested&&S.countries(data.profiles).some(c=>c.id===requested))country=requested;await render();},isIndicators:()=>tab==='indicators'&&!!country,country:()=>country};
 }
 global.MarioCountryFocus={mount};
})(globalThis);
