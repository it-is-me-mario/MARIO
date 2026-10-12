/* Parsed classification sizes only; no restricted numerical accounts are exposed. */
((global) => {
  "use strict";
  const unique=values=>[...new Set(values)];
  const familyName=source=>source==="Asian Development Bank"?"ADB":source==="OECD"?"OECD ICIO":source;
  const accessLabels={open:"Open use",noncommercial:"Non-commercial",restricted:"Proprietary / restricted",unverified:"Licence not classified"};
  const escape=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  function profileLicence(profile,metadata) {
    const guide=metadata.aliases?.[profile.guide] || profile.guide;
    const entries=(metadata.guides?.[guide] || []).filter(entry=>!entry.releases || entry.releases.includes(profile.release));
    if(entries.length!==1 || !["open","noncommercial","restricted"].includes(entries[0].access))
      return {category:"unverified",label:"Source terms not classified",url:profile.license_url || null};
    const entry=entries[0];return {category:entry.access,label:entry.label,url:entry.url,metadata:entry.metadata_licence || null};
  }
  function licenceText(point) {
    const mixed=point.licences.length>1;
    return (mixed?"<b>Licences vary by release</b><br>":"")+point.licences.map(entry=>{
      const label=entry.url&&/^https?:\/\//.test(entry.url)?`<a href="${escape(entry.url)}">${escape(entry.label)}</a>`:escape(entry.label);
      const metadata=entry.metadata?`<br>Scope metadata: <a href="${escape(entry.metadata.url)}">${escape(entry.metadata.label)}</a>`:"";
      return `${accessLabels[entry.category]} · ${label}${mixed?` (${escape(entry.releases.join(", "))})`:""}${metadata}`;
    }).join("<br>");
  }
  function scopePoints(profiles,licenceMetadata={}) {
    const groups=new Map();
    for(const p of profiles) {
      if(!["parsed","source_verified"].includes(p.status) || !(p.counts?.Region>1))continue;
      const environmental=typeof p.environmental === "boolean" ? p.environmental : (p.counts["Satellite account"] || 0)>0 && p.set_flags?.["Satellite account"]?.status!=="not_loaded";
      const units=p.provenance?.options?.unit || "Monetary";
      const licence=profileLicence(p,licenceMetadata);
      for(const dimension of ["Sector","Activity","Commodity"]) {
        const sectors=p.counts[dimension];
        if(!(sectors>0))continue;
        const key=JSON.stringify([p.source,sectors,p.counts.Region,units,environmental]);
        if(!groups.has(key))groups.set(key,{family:familyName(p.source),sectors,regions:p.counts.Region,units,environmental,dimensions:[],systems:[],releases:[],years:[],ids:[],statuses:[],parser_supported:[],yearEvidence:[],sourceCoverage:[],licensed:false,licences:[]});
        const item=groups.get(key);
        let terms=item.licences.find(entry=>entry.category===licence.category&&entry.label===licence.label&&entry.url===licence.url);
        if(!terms){terms={...licence,releases:[]};item.licences.push(terms);}
        terms.releases=unique([...terms.releases,p.release].filter(Boolean)).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
        item.dimensions=unique([...item.dimensions,dimension]);
        item.systems=unique([...item.systems,p.provenance?.options?.system || (p.provenance?.options?.iot_mode==="product"?"pxp":p.provenance?.options?.iot_mode==="industry"?"ixi":p.table)].filter(Boolean));
        item.releases=unique([...item.releases,p.release].filter(Boolean));
        item.years=unique([...item.years,...(p.years || [p.year])].filter(y=>y!=null)).sort((a,b)=>a-b);
        item.ids=unique([...item.ids,p.id]);item.statuses=unique([...item.statuses,p.status]);item.parser_supported=unique([...item.parser_supported,p.parser_supported!==false]);item.yearEvidence=unique([...item.yearEvidence,p.year_evidence?.hover_status].filter(Boolean));const coverage=p.source_coverage;if(coverage?.first_year&&coverage?.last_year)item.sourceCoverage=unique([...item.sourceCoverage,`${coverage.first_year}–${coverage.last_year}${coverage.forecast_from?` · ${coverage.forecast_from}–${coverage.last_year} forecasts`:""}`]);item.licensed ||= p.numeric_publication===false;
      }
    }
    for(const point of groups.values()) {
      const categories=point.licences.map(entry=>entry.category);
      point.access=categories.includes("restricted")?"restricted":categories.includes("noncommercial")?"noncommercial":categories.includes("unverified")?"unverified":"open";
    }
    return [...groups.values()].sort((a,b)=>a.family.localeCompare(b.family)||a.sectors-b.sectors||a.regions-b.regions);
  }
  function yearPeriods(years) {
    const sorted=unique(years.map(Number)).sort((a,b)=>a-b);
    if(!sorted.length)return "";
    const parts=[];let first=sorted[0],last=first;
    for(const year of [...sorted.slice(1),null]) {
      if(year!==null&&year===last+1){last=year;continue;}
      parts.push(first===last?String(first):`${first}–${last}`);first=last=year;
    }
    return parts.join(", ");
  }
  function familyLabels(points,width=900,height=470) {
    // Place one family label near its cluster, avoiding points and earlier labels.
    // The positions are calculated from geometry, never from database names.
    const families=unique(points.map(p=>p.family));
    const maxX=Math.max(1,...points.map(p=>p.sectors))*1.15,maxY=Math.max(1,...points.map(p=>p.regions))*1.15;
    const plotWidth=Math.max(160,width-PLOT_LEFT-PLOT_RIGHT),plotHeight=height-80;
    const sx=plotWidth/maxX,sy=plotHeight/maxY,fontSize=width<540?10:12;
    const pointRects=points.map(p=>({x:p.sectors*sx-10,y:p.regions*sy-10,w:20,h:20})),placed=[];
    const overlap=(a,b)=>Math.max(0,Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.y+a.h,b.y+b.h)-Math.max(a.y,b.y));
    return families.map(family=>{
      const group=points.filter(p=>p.family===family),xs=group.map(p=>p.sectors*sx),ys=group.map(p=>p.regions*sy);
      const cx=xs.reduce((a,b)=>a+b,0)/xs.length,cy=ys.reduce((a,b)=>a+b,0)/ys.length;
      const w=family.length*fontSize*.62+8,h=fontSize+6;
      const candidates=[
        [cx,Math.max(...ys)+23],[cx,Math.min(...ys)-23],
        [Math.max(...xs)+w/2+14,cy],[Math.min(...xs)-w/2-14,cy],
        [cx,Math.max(...ys)+43],[cx,Math.min(...ys)-43],
        [Math.max(...xs)+w/2+14,cy+25],[Math.min(...xs)-w/2-14,cy+25]
      ].map(([x,y],index)=>{
        x=Math.max(w/2,Math.min(plotWidth-w/2,x));y=Math.max(h/2,Math.min(plotHeight-h/2,y));
        const rect={x:x-w/2,y:y-h/2,w,h};
        const collision=[...pointRects,...placed].reduce((sum,other)=>sum+overlap(rect,other),0);
        return {family,x:x/sx,y:y/sy,rect,score:collision*100+index};
      });
      candidates.sort((a,b)=>a.score-b.score);const best=candidates[0];placed.push(best.rect);
      return {...best,fontSize};
    });
  }
  // Both charts share a fixed left margin so their y axes line up vertically.
  const PLOT_LEFT=100,PLOT_RIGHT=20;
  const SYMBOLS=["circle","square","diamond","triangle-up","triangle-down","pentagon","hexagon","star","hourglass","cross"];
  // Symbols follow one family order shared by both views, so a filter never swaps a family's marker.
  const symbolFor=(family,order)=>SYMBOLS[Math.max(0,order.indexOf(family))%SYMBOLS.length];
  const GLYPHS={circle:'<circle cx="6" cy="6" r="5"/>',square:'<rect x="1.5" y="1.5" width="9" height="9"/>',diamond:'<path d="M6 .5 11.5 6 6 11.5 .5 6Z"/>',
    "triangle-up":'<path d="M6 1 11.5 11H.5Z"/>',"triangle-down":'<path d="M.5 1h11L6 11Z"/>',pentagon:'<path d="M6 .6 11.4 4.6 9.3 11H2.7L.6 4.6Z"/>',
    hexagon:'<path d="M6 .5 10.8 3.2v5.6L6 11.5 1.2 8.8V3.2Z"/>',star:'<path d="M6 .4 7.6 4.3 11.8 4.6 8.6 7.3 9.6 11.4 6 9.2 2.4 11.4 3.4 7.3.2 4.6 4.4 4.3Z"/>',
    hourglass:'<path d="M1.5 1h9L1.5 11h9Z"/>',cross:'<path d="M4.3 .8h3.4v3.5h3.5v3.4H7.7v3.5H4.3V7.7H.8V4.3h3.5Z"/>'};
  const symbolGlyph=symbol=>`<svg class="scope-symbol" viewBox="0 0 12 12" aria-hidden="true">${GLYPHS[symbol]}</svg>`;
  function figure(points, colors, width=900, order=unique(points.map(p=>p.family))) {
    const families=unique(points.map(p=>p.family));
    const height=width<540?440:410;
    const labels=familyLabels(points,width,height);
    const data=families.flatMap((family,index)=>{
      const group=points.filter(p=>p.family===family),symbol=symbolFor(family,order);
      return [{type:"scatter",mode:"markers",x:group.map(p=>p.sectors),y:group.map(p=>p.regions),name:family,legendgroup:family,showlegend:false,
          marker:{symbol,size:16,color:group.map(p=>p.environmental?colors.extended:colors.base),line:{color:group.map(()=>colors.outline || colors.ink),width:group.map(p=>p.access==="open"?0:2),dash:group.map(p=>p.access==="noncommercial"?"3px,2px":p.access==="unverified"?"dot":"solid")}},
          customdata:group.map(p=>[family,p.units,[p.dimensions.join(" / "),p.systems.join(" / ")].filter(Boolean).join(" · "),p.releases.length?"Versions: "+p.releases.sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})).join(" · ")+"<br>":"",yearPeriods(p.years)+(p.sourceCoverage.length?"<br>Publisher series: "+p.sourceCoverage.join(" / "):""),p.environmental?"Environmental data included":"No environmental accounts",(p.yearEvidence.length?p.yearEvidence.join(" / "):p.statuses?.includes("source_verified")?(p.parser_supported.every(v=>!v)?"Source metadata · MARIO parser unavailable":"Native metadata · MARIO parser available"):"Verified MARIO parse · parser available")+(p.licensed?" · scope only; numerical indicators not published":""),licenceText(p)]),
          hovertemplate:"<b>%{customdata[0]}</b><br>%{x} sectors · %{y} regions<br>%{customdata[1]} · %{customdata[2]}<br>%{customdata[3]}Base / data years: %{customdata[4]}<br>%{customdata[5]}<br>%{customdata[6]}<br>%{customdata[7]}<extra></extra>"},
        {type:"scatter",mode:"text",x:[labels[index].x],y:[labels[index].y],text:[family],textposition:"middle center",textfont:{color:colors.ink,size:labels[index].fontSize},name:family,legendgroup:family,showlegend:false,hoverinfo:"skip"}];
    });
    const base={rangemode:"tozero",tickformat:",d",nticks:6,gridcolor:colors.grid,gridwidth:1,zerolinecolor:colors.ink,zerolinewidth:1.5,showline:true,linecolor:colors.ink,linewidth:1.5,mirror:false,automargin:true};
    const xaxis={...base,tickmode:"linear",tick0:0,dtick:50,title:{text:"N. sectors",standoff:15}};
    function niceStep(max){const raw=max/5,mag=Math.pow(10,Math.floor(Math.log10(raw))),steps=[1,2,5,10];return mag*steps.find(s=>s*mag>=raw);}
    const maxY=Math.max(1,...points.map(p=>p.regions)),step=niceStep(maxY);
    const yticks=[];for(let v=step;v<=maxY*1.15;v+=step)yticks.push(Math.round(v));
    const yaxis={...base,automargin:false,title:{text:"N. regions",standoff:15},tickmode:"array",tickvals:yticks,ticktext:yticks.map(v=>v.toLocaleString())};
    const xs=points.map(p=>p.sectors),ys=points.map(p=>p.regions),n=xs.length;
    const sx=xs.reduce((a,b)=>a+b,0),sy=ys.reduce((a,b)=>a+b,0),sxy=xs.reduce((a,x,i)=>a+x*ys[i],0),sxx=xs.reduce((a,x)=>a+x*x,0);
    const slope=(n*sxy-sx*sy)/(n*sxx-sx*sx||1),intercept=(sy-slope*sx)/n;
    const maxX=Math.max(...xs),trendX1=0,trendX2=maxX*1.1;
    data.push({type:"scatter",mode:"lines",x:[trendX1,trendX2],y:[intercept,slope*trendX2+intercept],line:{color:colors.ink,width:2,dash:"dash"},opacity:0.55,showlegend:false,hoverinfo:"skip"});
    return {data,layout:{height,autosize:true,paper_bgcolor:colors.background,plot_bgcolor:colors.background,font:{family:colors.font,color:colors.ink,size:12},margin:{l:PLOT_LEFT,r:PLOT_RIGHT,t:20,b:60},xaxis,yaxis,hovermode:"closest",hoverlabel:{bgcolor:colors.surface,bordercolor:colors.grid,font:{color:colors.ink}},showlegend:false,dragmode:"zoom",uirevision:"scope"},config:{responsive:true,showTips:false,scrollZoom:true,doubleClick:"autosize",displaylogo:false,toImageButtonOptions:{filename:"mario-database-scope",format:"png",scale:2},modeBarButtonsToRemove:["select2d","lasso2d"]}};
  }
  const listed=p=>["parsed","source_verified"].includes(p.status)&&p.counts?.Region>1;
  const profileYears=profiles=>unique(profiles.filter(listed).flatMap(p=>(p.years || [p.year]).map(Number)).filter(Number.isFinite)).sort((a,b)=>b-a);
  // A selected year keeps the profiles covering it and narrows their years to it, so hovers name only that year.
  function profilesForYear(profiles,year) {
    if(year==="all")return profiles;
    const y=Number(year);
    return profiles.filter(p=>(p.years || [p.year]).map(Number).includes(y)).map(p=>({...p,year:y,years:[y]}));
  }
  // One row per database family, one point per available year.
  function timelinePoints(profiles) {
    const cells=new Map();
    for(const p of profiles.filter(listed)) {
      const environmental=typeof p.environmental === "boolean" ? p.environmental : (p.counts["Satellite account"] || 0)>0 && p.set_flags?.["Satellite account"]?.status!=="not_loaded";
      const system=p.provenance?.options?.system || (p.provenance?.options?.iot_mode==="product"?"pxp":p.provenance?.options?.iot_mode==="industry"?"ixi":p.table);
      for(const year of unique((p.years || [p.year]).map(Number).filter(Number.isFinite))) {
        const key=familyName(p.source)+"|"+year;
        if(!cells.has(key))cells.set(key,{family:familyName(p.source),year,versions:[],systems:[],environmental:false,sourceOnly:true,publisher:false});
        const cell=cells.get(key);
        cell.versions=unique([...cell.versions,p.release].filter(Boolean)).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
        cell.systems=unique([...cell.systems,system].filter(Boolean));
        cell.environmental ||= environmental;
        cell.sourceOnly &&= p.status==="source_verified" && p.parser_supported===false;
      }
    }
    // Years the publisher documents but MARIO has not parsed yet; forecasts are flagged.
    for(const p of profiles.filter(listed)) {
      const coverage=p.source_coverage;if(!coverage?.first_year||!coverage?.last_year)continue;
      for(let year=coverage.first_year;year<=coverage.last_year;year+=1) {
        const key=familyName(p.source)+"|"+year,forecast=!!coverage.forecast_from&&year>=coverage.forecast_from;
        if(cells.has(key)){cells.get(key).forecast ||= forecast;continue;}
        cells.set(key,{family:familyName(p.source),year,versions:[p.release].filter(Boolean),systems:[],environmental:false,sourceOnly:false,publisher:true,forecast});
      }
    }
    return [...cells.values()].sort((a,b)=>a.family.localeCompare(b.family)||a.year-b.year);
  }
  function timelineFigure(cells, colors, {year="all",order=unique(cells.map(c=>c.family)),width=900}={}) {
    const families=order.filter(f=>cells.some(c=>c.family===f)),selected=year==="all"?null:Number(year);
    const years=cells.map(c=>c.year),lo=Math.min(...years),hi=Math.max(...years);
    const covers=family=>selected===null || cells.some(c=>c.family===family&&c.year===selected&&!c.publisher);
    const data=families.map(family=>{
      const group=cells.filter(c=>c.family===family),symbol=symbolFor(family,order),fill=c=>c.environmental?colors.extended:colors.base;
      return {type:"scatter",mode:"markers",name:family,showlegend:false,x:group.map(c=>c.year),y:group.map(()=>family),
        opacity:covers(family)?1:.28,
        marker:{size:width<540?8:10,symbol,color:group.map(c=>c.publisher?colors.ink:fill(c)),opacity:group.map(c=>c.publisher?.3:1),line:{color:colors.background,width:.5}},
        customdata:group.map(c=>[c.versions.length?"Versions: "+c.versions.join(" · "):"",c.systems.join(" / "),c.publisher?"Environmental data not yet checked":c.environmental?"Environmental data included":"No environmental accounts",(c.publisher?"Published by source · not yet explorable in this website":c.sourceOnly?"Source base year · no MARIO parser":"Verified MARIO parse")+(c.forecast?" · publisher forecast":"")]),
        hovertemplate:"<b>%{y}</b> · %{x}<br>%{customdata[0]}<br>%{customdata[1]}<br>%{customdata[2]}<br>%{customdata[3]}<extra></extra>"};
    });
    const shapes=selected===null?[]:[{type:"line",xref:"x",yref:"paper",x0:selected,x1:selected,y0:0,y1:1,line:{color:colors.ink,width:1.5,dash:"dash"}}];
    const axis={showline:true,linecolor:colors.ink,linewidth:1.5,gridcolor:colors.grid,automargin:true,fixedrange:true};
    return {data,layout:{height:families.length*30+65,autosize:true,paper_bgcolor:colors.background,plot_bgcolor:colors.background,font:{family:colors.font,color:colors.ink,size:12},
      margin:{l:PLOT_LEFT,r:PLOT_RIGHT,t:15,b:30},shapes,hovermode:"closest",hoverlabel:{bgcolor:colors.surface,bordercolor:colors.grid,font:{color:colors.ink}},
      xaxis:{...axis,side:"bottom",range:[lo-1,hi+1],dtick:5,tick0:Math.floor(lo/5)*5,tickformat:"d"},
      yaxis:{...axis,automargin:false,type:"category",categoryorder:"array",categoryarray:[...families].reverse(),showgrid:true,ticks:""},
      uirevision:"timeline"},
      config:{responsive:true,showTips:false,displaylogo:false,toImageButtonOptions:{filename:"mario-database-years",format:"png",scale:2},modeBarButtonsToRemove:["select2d","lasso2d","zoom2d","pan2d","zoomIn2d","zoomOut2d","autoScale2d","resetScale2d"]}};
  }
  const api={scopePoints,figure,familyLabels,profileYears,profilesForYear,timelinePoints,timelineFigure,symbolFor,symbolGlyph};
  if(typeof module!=="undefined")module.exports=api;
  else global.MarioDatabaseScope=api;
})(globalThis);

(() => {
  if(typeof document==="undefined")return;
  const root=document.querySelector("[data-database-scope]");
  if(!root)return;
  const base=new URL(root.dataset.root || "../../",location.href);
  Promise.all(["database_profiles.json","external_profiles.json","database_licences.json"].map(file=>fetch(new URL("_static/data/"+file,base),{cache:"no-cache"}).then(response=>{
    if(!response.ok)throw new Error("Classification catalogue unavailable");
    return response.json();
  }))).then(async catalogues=>{
    const catalogue={profiles:catalogues.slice(0,2).flatMap(c=>c.profiles)};
    const years=window.MarioDatabaseScope.profileYears(catalogue.profiles);
    let year="all",points=[];
    const M=window.MarioDatabaseScope,cells=M.timelinePoints(catalogue.profiles),order=[...new Set(cells.map(c=>c.family))];
    const key=()=>'<div class="scope-key-group" role="group" aria-label="Marker symbol"><b>Database</b>'+order.map(f=>`<span>${M.symbolGlyph(M.symbolFor(f,order))}${f}</span>`).join('')+'</div>'
      +'<div class="scope-key-group" role="group" aria-label="Marker fill"><b>Fill</b><span><i class="scope-extended"></i>Environmental data included</span><span><i class="scope-base"></i>No environmental accounts</span></div><div class="scope-key-group" role="group" aria-label="Marker outline"><b>Outline</b><span>No border: open use</span><span><i class="scope-access-nc"></i>Non-commercial</span><span><i class="scope-access-restricted"></i>Proprietary / restricted</span>'+(points.some(p=>p.access==="unverified")?'<span><i class="scope-access-unknown"></i>Not classified</span>':'')+'</div>';
    root.innerHTML='<div class="scope-controls"><h4 class="scope-title">Regions and sectors by database</h4><label>Year<select data-scope-year><option value="all">All available years</option>'+years.map(y=>`<option value="${y}">${y}</option>`).join('')+'</select></label></div><div class="scope-extension-key" data-scope-key></div><div data-scope-chart></div>'
      +'<div class="scope-timeline"><h4 class="scope-title">Available years by database</h4><div data-scope-timeline></div>'+(cells.some(c=>c.publisher)?'<p class="scope-timeline-note">Faded markers: years published by the source but not yet explorable in this website.</p>':'')+'</div>';
    const timeline=root.querySelector("[data-scope-timeline]");
    timeline.setAttribute("aria-label","Available data or base years for each database family. The selected year is marked by a vertical line.");
    const node=root.querySelector("[data-scope-chart]");
    node.setAttribute("aria-label","Interactive MRIO comparison: number of sectors and regions. Marker identifies database family; fill identifies environmental data; outline identifies source licence conditions.");
    let operations=Promise.resolve();
    const render=()=>{
      const css=getComputedStyle(root),get=name=>css.getPropertyValue(name).trim();
      const colors={background:get("--surface-2"),surface:get("--surface"),ink:get("--ink"),grid:get("--line"),font:css.fontFamily,extended:get("--scope-extended"),base:get("--scope-base"),outline:get("--scope-terms-outline")};
      points=window.MarioDatabaseScope.scopePoints(window.MarioDatabaseScope.profilesForYear(catalogue.profiles,year),catalogues[2]);
      root.querySelector("[data-scope-key]").innerHTML=key();
      const f=M.figure(points,colors,node.clientWidth || 900,order),t=M.timelineFigure(cells,colors,{year,order,width:timeline.clientWidth || 900});
      timeline.style.height=t.layout.height+"px";
      node.style.height=f.layout.height+"px";
      operations=operations.then(()=>window.Plotly.react(node,f.data,f.layout,window.MarioFigureDownload.withCredit(f.config,['MARIO · native database scope'+(year==="all"?"":" · "+year)+' · '+[...new Set(catalogue.profiles.map(p=>p.source))].join(', '),'Fill: turquoise = environmental data; lilac = no environmental accounts. Outline: none = open use; dashed = non-commercial; solid = proprietary/restricted. Mixed releases show the most restrictive terms.','Counts from parsed inputs or cited public metadata; no licensed economic observations. Sources and terms: https://mario-suite.readthedocs.io/en/latest/resources/data-explorer/scope.html'])));
      operations=operations.then(()=>window.Plotly.react(timeline,t.data,t.layout,window.MarioFigureDownload.withCredit(t.config,['MARIO · available data / base years by database family'+(year==="all"?"":" · selected "+year),'Fill: turquoise = environmental data; lilac = no environmental accounts. Faded markers: years published by the source but not yet explorable in this website.'])));
      return operations;
    };
    await render();root.setAttribute("aria-busy","false");
    const yearControl=root.querySelector("[data-scope-year]");
    yearControl.addEventListener("change",event=>{year=event.target.value;render().catch(()=>{});});
    // Clicking a year in the timeline selects it; clicking the selected year again returns to all years.
    timeline.on("plotly_click",event=>{const clicked=String(event.points[0]?.x);if(!clicked||clicked==="undefined")return;year=year===clicked?"all":clicked;yearControl.value=year;render().catch(()=>{});});
    new MutationObserver(()=>render().catch(()=>{})).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change",()=>render().catch(()=>{}));
  }).catch(error=>{root.textContent=`The scope chart could not load. ${error.message}`;root.setAttribute("aria-busy","false");});
})();
