/* Parsed classification sizes only; no restricted numerical accounts are exposed. */
((global) => {
  "use strict";
  const unique=values=>[...new Set(values)];
  const familyName=source=>source==="Asian Development Bank"?"ADB":source==="OECD"?"OECD ICIO":source;
  function scopePoints(profiles) {
    const groups=new Map();
    for(const p of profiles) {
      if(!["parsed","source_verified"].includes(p.status) || !(p.counts?.Region>1))continue;
      const environmental=typeof p.environmental === "boolean" ? p.environmental : (p.counts["Satellite account"] || 0)>0 && p.set_flags?.["Satellite account"]?.status!=="not_loaded";
      const units=p.provenance?.options?.unit || "Monetary";
      for(const dimension of ["Sector","Activity","Commodity"]) {
        const sectors=p.counts[dimension];
        if(!(sectors>0))continue;
        const key=JSON.stringify([p.source,sectors,p.counts.Region,units,environmental]);
        if(!groups.has(key))groups.set(key,{family:familyName(p.source),sectors,regions:p.counts.Region,units,environmental,dimensions:[],systems:[],releases:[],years:[],ids:[],statuses:[],parser_supported:[],licensed:false});
        const item=groups.get(key);
        item.dimensions=unique([...item.dimensions,dimension]);
        item.systems=unique([...item.systems,p.provenance?.options?.system || (p.provenance?.options?.iot_mode==="product"?"pxp":p.provenance?.options?.iot_mode==="industry"?"ixi":p.table)].filter(Boolean));
        item.releases=unique([...item.releases,p.release].filter(Boolean));
        item.years=unique([...item.years,...(p.years || [p.year])].filter(y=>y!=null)).sort((a,b)=>a-b);
        item.ids=unique([...item.ids,p.id]);item.statuses=unique([...item.statuses,p.status]);item.parser_supported=unique([...item.parser_supported,p.parser_supported!==false]);item.licensed ||= p.numeric_publication===false;
      }
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
  function figure(points, colors) {
    const families=unique(points.map(p=>p.family));
    const symbols=["circle","square","diamond","triangle-up","triangle-down","pentagon","hexagon","star"];
    const data=families.flatMap((family,index)=>{
      const group=points.filter(p=>p.family===family),symbol=symbols[index%symbols.length];
      return [{type:"scatter",mode:"markers",x:[null],y:[null],name:family,legendgroup:family,showlegend:true,hoverinfo:"skip",marker:{color:colors.ink,symbol,size:10}},
        {type:"scatter",mode:"markers",x:group.map(p=>p.sectors),y:group.map(p=>p.regions),name:family,legendgroup:family,showlegend:false,
          marker:{symbol,size:13,color:group.map(p=>p.environmental?colors.extended:colors.base),line:{color:colors.background,width:1}},
          customdata:group.map(p=>[family,p.units,[p.dimensions.join(" / "),p.systems.join(" / ")].filter(Boolean).join(" · "),p.releases.length?"Versions: "+p.releases.sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})).join(" · ")+"<br>":"",yearPeriods(p.years),p.environmental?"Environmental data included":"No environmental accounts",p.statuses?.includes("source_verified")?(p.parser_supported.every(v=>!v)?"Source metadata · MARIO parser unavailable":"Native metadata · MARIO parser available")+ (p.licensed?" · licensed source; numerical indicators not published":""):"Verified MARIO parse"]),
          hovertemplate:"<b>%{customdata[0]}</b><br>%{x} sectors · %{y} regions<br>%{customdata[1]} · %{customdata[2]}<br>%{customdata[3]}Base / data years: %{customdata[4]}<br>%{customdata[5]}<br>%{customdata[6]}<extra></extra>"}];
    });
    const base={rangemode:"tozero",tickformat:",d",nticks:6,gridcolor:colors.grid,gridwidth:1,zerolinecolor:colors.ink,zerolinewidth:1.5,showline:true,linecolor:colors.ink,linewidth:1.5,mirror:false,automargin:true};
    const xaxis={...base,title:{text:"N. sectors",standoff:15}};
    function niceStep(max){const raw=max/5,mag=Math.pow(10,Math.floor(Math.log10(raw))),steps=[1,2,5,10];return mag*steps.find(s=>s*mag>=raw);}
    const maxY=Math.max(1,...points.map(p=>p.regions)),step=niceStep(maxY);
    const yticks=[];for(let v=step;v<=maxY*1.15;v+=step)yticks.push(Math.round(v));
    const yaxis={...base,title:{text:"N. regions",standoff:15},tickmode:"array",tickvals:yticks,ticktext:yticks.map(v=>v.toLocaleString())};
    const xs=points.map(p=>p.sectors),ys=points.map(p=>p.regions),n=xs.length;
    const sx=xs.reduce((a,b)=>a+b,0),sy=ys.reduce((a,b)=>a+b,0),sxy=xs.reduce((a,x,i)=>a+x*ys[i],0),sxx=xs.reduce((a,x)=>a+x*x,0);
    const slope=(n*sxy-sx*sy)/(n*sxx-sx*sx||1),intercept=(sy-slope*sx)/n;
    const maxX=Math.max(...xs),trendX1=0,trendX2=maxX*1.1;
    data.push({type:"scatter",mode:"lines",x:[trendX1,trendX2],y:[intercept,slope*trendX2+intercept],line:{color:colors.ink,width:2,dash:"dash"},opacity:0.55,showlegend:false,hoverinfo:"skip"});
    return {data,layout:{height:470,autosize:true,paper_bgcolor:colors.background,plot_bgcolor:colors.background,font:{family:colors.font,color:colors.ink,size:12},margin:{l:65,r:20,t:25,b:95},xaxis,yaxis,hovermode:"closest",hoverlabel:{bgcolor:colors.surface,bordercolor:colors.grid,font:{color:colors.ink}},legend:{orientation:"h",y:-.22,x:0,groupclick:"togglegroup"},dragmode:"zoom",uirevision:"scope"},config:{responsive:true,showTips:false,scrollZoom:true,doubleClick:"autosize",displaylogo:false,toImageButtonOptions:{filename:"mario-database-scope",format:"png",scale:2},modeBarButtonsToRemove:["select2d","lasso2d"]}};
  }
  const api={scopePoints,figure};
  if(typeof module!=="undefined")module.exports=api;
  else global.MarioDatabaseScope=api;
})(globalThis);

(() => {
  if(typeof document==="undefined")return;
  const root=document.querySelector("[data-database-scope]");
  if(!root)return;
  const base=new URL(root.dataset.root || "../../",location.href);
  Promise.all(["database_profiles.json","external_profiles.json"].map(file=>fetch(new URL("_static/data/"+file,base)).then(response=>{
    if(!response.ok)throw new Error("Classification catalogue unavailable");
    return response.json();
  }))).then(async catalogues=>{
    const catalogue={profiles:catalogues.flatMap(c=>c.profiles)};
    const points=window.MarioDatabaseScope.scopePoints(catalogue.profiles);
    root.innerHTML='<div class="scope-extension-key"><span><i class="scope-extended"></i>Environmental data included</span><span><i class="scope-base"></i>No environmental accounts</span></div><div data-scope-chart></div>';
    const node=root.querySelector("[data-scope-chart]");
    node.setAttribute("aria-label","Interactive MRIO comparison: number of sectors and regions. Marker identifies database family; colour identifies available environmental data.");
    let operations=Promise.resolve();
    const render=()=>{
      const css=getComputedStyle(root),get=name=>css.getPropertyValue(name).trim();
      const colors={background:get("--surface-2"),surface:get("--surface"),ink:get("--ink"),grid:get("--line"),font:css.fontFamily,extended:get("--scope-extended"),base:get("--scope-base")};
      const f=window.MarioDatabaseScope.figure(points,colors);
      node.style.height=f.layout.height+"px";
      operations=operations.then(()=>window.Plotly.react(node,f.data,f.layout,f.config));
      return operations;
    };
    await render();root.setAttribute("aria-busy","false");
    new MutationObserver(()=>render().catch(()=>{})).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change",()=>render().catch(()=>{}));
  }).catch(error=>{root.textContent=`The scope chart could not load. ${error.message}`;root.setAttribute("aria-busy","false");});
})();
