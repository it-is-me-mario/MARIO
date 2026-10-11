/* Display scaling and Plotly figures. Source observations remain unchanged. */
((global) => {
  "use strict";
  const isReference = row => ["World Bank", "EDGAR"].includes(row.database);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  function traceUid(value) {
    let hash=2166136261;
    for(const char of value)hash=Math.imul(hash^char.charCodeAt(0),16777619);
    return "series-"+(hash>>>0).toString(16);
  }
  function scaleFor(rows, state, nativeUnit) {
    const values = rows.map(row => row.value).filter(Number.isFinite);
    const largest = values.reduce((max, value) => Math.max(max, Math.abs(value)), 0);
    if (state.metric !== "ghg") {
      const prefixes = [[1e12,"trillion"],[1e9,"billion"],[1e6,"million"],[1e3,"thousand"]];
      const [factor, prefix] = prefixes.find(([factor]) => largest >= factor) || [1, ""];
      return {factor, unit: `${nativeUnit.replace(" / person","")}${prefix ? " " + prefix : ""}${state.perCapita ? "/person" : ""}`, nativeUnit};
    }
    if (state.perCapita) return {factor:1, unit:"t CO₂eq/person", nativeUnit};
    const nativeTonnes = nativeUnit.startsWith("Mt") ? 1e6 : nativeUnit.startsWith("Gg") ? 1e3 : 1;
    const [tonnes, prefix] = [[1e9,"Gt"],[1e6,"Mt"],[1e3,"kt"],[1,"t"]].find(([factor]) => largest * nativeTonnes >= factor) || [1,"t"];
    return {factor:tonnes/nativeTonnes, unit:`${prefix} CO₂eq`, nativeUnit};
  }
  const scaled = (value, scale) => Number.isFinite(value) ? value / scale.factor : null;
  function hoverDistance(years, pixelsPerYear) {
    if(years.length<2)return 10;
    const gap=Math.min(...years.slice(1).map((year,i)=>year-years[i]).filter(gap=>gap>0));
    return Math.max(1,Math.floor(gap*Math.abs(pixelsPerYear)*.45));
  }
  const scatterMarkerSize = count => Math.max(7.5, Math.min(15, 32 / Math.sqrt(Math.max(1, count))));
  const usesBars=(rows,state,years)=>years.length<=1 || (["focus","country"].includes(state.mode)&&new Set(rows.filter(row=>!isReference(row)).map(row=>row.series || row.version)).size<=1);
  function figure(rows, options) {
    const {state, years, colors, catalogue = []} = options;
    const scale = scaleFor(rows, state, options.nativeUnit);
    const primary = rows.filter(row => !isReference(row) && Number.isFinite(row.value));
    const references = rows.filter(row => isReference(row) && Number.isFinite(row.value));
    if (!primary.length) return {data:[], scale};
    const temporal = years.length > 1;
    const markerSize = scatterMarkerSize(new Set(primary.map(row => row.year)).size);
    // Several sector aggregates stack within each single-year bar; over time they stay separate series.
    const sectors = [...new Set(primary.map(row => row.sector ?? "all"))], stacked = sectors.length > 1;
    const bars=usesBars(rows,state,years) && !(stacked && temporal);
    const countries = [...new Set(primary.map(row => row.country))];
    const referenceLines=bars&&!temporal;
    // A single-year reference uses the value axis vertically so its line spans the plot horizontally.
    const horizontal = bars && !temporal && primary.length > 7 && !references.length;
    const compactLegend=!temporal;
    const barGroups=[...new Set(primary.map(row=>JSON.stringify([row.series,row.country])))];
    const barOffset=row=>(barGroups.indexOf(JSON.stringify([row.series,row.country]))-(barGroups.length-1)/2)*.7/barGroups.length;
    const groups = new Map();
    for (const row of [...primary, ...references]) {
      const id = JSON.stringify([row.series, row.country, ...(stacked ? [row.sector ?? "all"] : [])]);
      if (!groups.has(id)) groups.set(id, []);
      groups.get(id).push(row);
    }
    const palette = colors.palette;
    const databaseFamilies=options.databaseFamilies || [...new Set(primary.map(row=>row.database))];
    const category = row => `${countries.length > 1 ? escape(row.country_name) + "<br>" : ""}${escape(row.database)}<br>${escape(row.version)}`;
    // Each release branches only when it has several selected variants. Shorter branches
    // stop at the release row; a single system is written alongside its release instead.
    const releaseOf = row => String(row.release || row.version || "");
    const variantOf = row => {const release=row.release, version=String(row.version ?? "");
      return release && version.startsWith(release+" · ") ? version.slice(release.length+3) : "";};
    const variants = new Map(), branchKey = row => JSON.stringify([row.country, row.database, releaseOf(row)]);
    for (const row of primary) {
      const key=branchKey(row);
      if (!variants.has(key)) variants.set(key, new Set());
      variants.get(key).add(variantOf(row));
    }
    const branches = row => variants.get(branchKey(row)).size > 1;
    const releaseLabel = row => branches(row) ? releaseOf(row) : [releaseOf(row),variantOf(row)].filter(Boolean).join(" ");
    const outer = [row=>row.country_name, row=>row.database, releaseLabel]
      .filter(level=>new Set(primary.map(level)).size>1);
    const hasRelease = outer.includes(releaseLabel);
    const levels = [...outer, ...(primary.some(branches) ? [row=>branches(row) ? variantOf(row) || releaseOf(row) : hasRelease ? null : releaseLabel(row)] : [])];
    const hierarchy = bars && !temporal && !horizontal && levels.length > 1 ? levels : [];
    const ordering = [row=>row.country, row=>row.database, releaseOf, variantOf];
    const ranks = ordering.map(level=>[...new Set(primary.map(level))]);
    const ordered = hierarchy.length ? [...primary].sort((a,b)=>{
      for (let i=0;i<ordering.length;i++) {const d=ranks[i].indexOf(ordering[i](a))-ranks[i].indexOf(ordering[i](b)); if (d) return d;}
      return 0;}) : primary;
    const categoryOrder = [...new Set(ordered.map(category))];
    const keyed = categoryOrder.map(name=>ordered.find(row=>category(row)===name));
    const innerLabel = row => hierarchy.at(-1)(row) ?? "";
    // Labels adapt to the room per bar: smaller type first, then vertical bar labels on phones.
    const plotWidth = Math.max(160, (options.width || 900) - 98), perBar = plotWidth / Math.max(1, categoryOrder.length);
    const textWidth = (text, size) => String(text).length*size*.58;
    const longest = !hierarchy.length ? "" : keyed.reduce((top,row)=>String(innerLabel(row)).length>top.length?String(innerLabel(row)):top, "");
    const innerSize = [12,10,9].find(size=>textWidth(longest,size)<=perBar*.92);
    const rotate = hierarchy.length && innerSize === undefined;
    const TICK = rotate ? Math.round(textWidth(longest,10))+16 : 22, ROW=19, annotations=[], brackets=[];
    let depth=TICK;
    for (let level=hierarchy.length-2; level>=0; level--) {
      const runs=[];
      for (let start=0, i=1; i<=keyed.length; i++) {
        if (i<keyed.length && hierarchy.slice(0,level+1).every(f=>f(keyed[i])===f(keyed[start]))) continue;
        const label=hierarchy[level](keyed[start]);
        if (label != null) runs.push({start, end:i-1, label:String(label), room:(i-start)*perBar*.92});
        start=i;
      }
      // A level whose labels do not fit even at 9 px turns vertical as a whole, in a taller row.
      const upright=runs.every(run=>textWidth(run.label,9)<=run.room);
      const height=upright ? ROW : Math.round(Math.max(...runs.map(run=>textWidth(run.label,10))))+12;
      for (const run of runs) {
        brackets.push({type:"line",xref:"x",x0:run.start-.42,x1:run.end+.42,yref:"paper",ysizemode:"pixel",yanchor:0,y0:-depth,y1:-depth,
          line:{color:colors.muted,width:1},opacity:.7,layer:"above"});
        annotations.push({xref:"x",x:(run.start+run.end)/2,yref:"paper",y:0,showarrow:false,text:escape(run.label),
          ...(upright ? {yanchor:"top",yshift:-(depth+1),font:{size:[level===0?12:11,10,9].find(size=>textWidth(run.label,size)<=run.room) || 9,color:colors.ink}}
                      : {yanchor:"middle",yshift:-(depth+height/2),textangle:-90,font:{size:10,color:colors.ink}})});
      }
      depth+=height;
    }
    // Narrow legends wrap below the bracketed labels. Reserve their rows before
    // Plotly computes margins so its automatic expansion cannot lift them onto the axis.
    const narrow = (options.width || 900) < 600;
    const legendCount = (stacked ? sectors.length : new Set(primary.map(row=>row.database)).size) + new Set(references.map(row=>row.database)).size;
    const legendSpace = narrow ? Math.min(6,legendCount)*24+20 : 48;
    const bottom = hierarchy.length ? depth+legendSpace : 95;
    const height = hierarchy.length && narrow ? Math.max(460,36+bottom+240) : 460;
    const data = [], shapes=[], shownLegend=new Set(), shownReferences=new Set();
    for (const [id, group] of groups) {
      group.sort((a,b) => a.year - b.year);
      const first = group[0], reference = isReference(first);
      const index = Math.max(0, catalogue.indexOf(first.series));
      const sectorLabel = first.sector_name || first.sector;
      const name = `${first.database}${reference || !first.version ? "" : " · " + first.version}${countries.length > 1 ? " · " + first.country_name : ""}${stacked && !reference ? " · " + sectorLabel : ""}`;
      const styleIndex=countries.length>1?index*countries.length+countries.indexOf(first.country):index;
      const focus=state.mode==="focus" && !reference;
      const colorIndex=state.mode==="focus"?0:Math.max(0,databaseFamilies.indexOf(first.database));
      const color = reference ? colors.muted : palette[(stacked ? sectors.indexOf(first.sector ?? "all") : colorIndex) % palette.length];
      const systemSymbol=first.format === "SUT" ? "diamond" : ({ixi:"circle",pxp:"square",Industry:"circle",Product:"square",Activity:"diamond"})[first.system] || "circle";
      const symbol=focus?systemSymbol+(first.units==="Hybrid"?"-open":""):["circle","square","diamond"][styleIndex % 3];
      let points = group;
      if ((!temporal || bars) && reference) points = primary.flatMap(row => {
        const match = group.find(ref => ref.year === row.year && ref.country === row.country);
        return match ? [{...match, category:category(row),offset:barOffset(row)}] : [];
      });
      const categories = points.map(row => row.category || category(row));
      const values = points.map(row => scaled(row.value, scale));
      const countryOffset=bars&&temporal?barOffset(first):0;
      const coordinates = temporal ? {x:points.map(row => row.year+(reference&&bars?row.offset || 0:0)), y:values} : horizontal ? {x:values,y:categories} : {x:categories,y:values};
      const numericAxis = horizontal ? "x" : "y";
      const legendKey=stacked&&!reference?"sector:"+(first.sector ?? "all"):"database:"+first.database;
      const legendgroup=compactLegend?legendKey:id;
      const showlegend=!compactLegend || (!reference&&!shownLegend.has(legendKey));
      if(!reference)shownLegend.add(legendKey);
      const trace = {
        uid:traceUid(id), name:escape(compactLegend?(stacked&&!reference?sectorLabel:first.database):name), legendgroup, showlegend, legendrank:reference ? 10000 : stacked ? sectors.indexOf(first.sector ?? "all") : index,
        type:reference || !bars ? "scatter" : "bar", ...coordinates,
        customdata:points.map(row => [row.country_name, row.year, row.note, row.value, row.unit]),
        hovertemplate:points.map(row=>`<b>${escape(name)}</b>: %{${numericAxis}:,.3~f} ${escape(scale.unit)}${row.note?.startsWith("GDP estimate")?" (estimate)":""}<extra></extra>`),
      };
      if (trace.type === "bar") {
        trace.orientation = horizontal ? "h" : "v";
        trace.marker = {color,line:{color:stacked?colors.background:color,width:stacked?.6:1},...(focus&&first.units==="Hybrid"&&!stacked?{color:"transparent"}:{} )};
        trace.width = bars&&temporal ? .7/barGroups.length : .55;
        if(temporal)trace.offset=countryOffset-trace.width/2;
      } else {
        trace.mode = "markers";
        trace.marker = reference
          ? referenceLines ? {color:colors.reference || "#786e9c",size:7,opacity:0} : bars ? {color:colors.reference || "#786e9c",symbol:"diamond",size:7,opacity:.85,line:{color:colors.background,width:.8}} : {color, symbol:horizontal ? "line-ns" : "line-ew", size:9, opacity:.55, line:{color,width:1.2}}
          : {color, symbol, size:markerSize, line:{color:focus&&first.units==="Hybrid"?color:colors.background,width:focus&&first.units==="Hybrid"?1.5:.6}};
        trace.zorder = reference ? 0 : 1;
      }
      if(reference&&referenceLines)for(const row of group) {
        const value=scaled(row.value,scale);
        // With several countries, each reference spans only its own country's bars
        // (one segment per run of adjacent categories); otherwise the whole plot.
        const indices=countries.length>1?[...new Set(primary.filter(bar=>bar.country===row.country&&bar.year===row.year)
          .map(bar=>categoryOrder.indexOf(category(bar))).filter(i=>i>=0))].sort((a,b)=>a-b):[];
        const runs=[];
        for(const i of indices){const last=runs.at(-1);if(last&&i===last[1]+1)last[1]=i;else runs.push([i,i]);}
        const spans=runs.length?runs.map(([start,end])=>({xref:"x",x0:start-.42,x1:end+.42})):[{xref:"paper",x0:0,x1:1}];
        for(const span of spans) {
          shapes.push({type:"line",...span,yref:"y",y0:value,y1:value,
            line:{color:colors.reference || "#786e9c",width:1.4,dash:"dash"},opacity:.8,
            name:escape(first.database),legendgroup,legendrank:10000,
            showlegend:!shownReferences.has(first.database)});
          shownReferences.add(first.database);
        }
      }
      data.push(trace);
    }
    const numberAxis = {
      title:{text:scale.unit,standoff:14,font:{size:12}},
      tickformat:",~g", nticks:6, rangemode:"tozero", exponentformat:"none",
      showgrid:true, gridcolor:colors.grid, zeroline:true, zerolinecolor:colors.grid,
      automargin:true, fixedrange:false,
    };
    const categoryAxis = {
      type:"category", categoryorder:"array", categoryarray:categoryOrder,
      showgrid:false, automargin:!hierarchy.length, fixedrange:false,
      ...(hierarchy.length ? {tickmode:"array", tickvals:categoryOrder, ticktext:keyed.map(row=>escape(innerLabel(row))),
        tickangle:rotate ? -90 : 0, tickfont:{size:innerSize || 10}} : {}),
      unifiedhovertitle:{text:`<b>${years[0]}</b>`},
    };
    const layout = {
      autosize:true, height:horizontal ? Math.min(760, Math.max(430,primary.length*36+145)) : height,
      paper_bgcolor:colors.background, plot_bgcolor:colors.background,
      font:{family:colors.font,size:12,color:colors.ink},
      margin:{l:horizontal ? 175 : 76,r:22,t:36,b:bottom},
      hovermode:horizontal ? "y unified" : "x unified", hoverdistance:10,
      hoverlabel:{bgcolor:colors.surface,bordercolor:colors.grid,font:{family:colors.font,color:colors.ink,size:12},namelength:-1},
      dragmode:"zoom", showlegend:true, barmode:stacked && bars && !temporal ? "stack" : "overlay", shapes:[...shapes,...brackets], annotations,
      legend:{maxheight:.25,orientation:"h",y:hierarchy.length ? -(depth+14)/(height-36-bottom) : -.2,x:0,xanchor:"left",yanchor:"top",font:{size:11},itemclick:"toggle",itemdoubleclick:"toggleothers",groupclick:compactLegend?"togglegroup":"toggleitem"},
      uirevision:options.revision,
      xaxis:temporal ? {type:"linear",title:{text:"Year",font:{size:12}},tickformat:"d",dtick:Math.max(1,Math.ceil((years.at(-1)-years[0])/7)),showgrid:false,automargin:true,unifiedhovertitle:{text:"<b>%{x:.0f}</b>"}} : horizontal ? numberAxis : categoryAxis,
      yaxis:horizontal ? {...categoryAxis,autorange:"reversed"} : numberAxis,
    };
    const config = {
      responsive:true, showTips:false, displaylogo:false, scrollZoom:true, doubleClick:"autosize",
      displayModeBar:true, modeBarButtonsToRemove:["select2d","lasso2d","toggleSpikelines","hoverClosestCartesian","hoverCompareCartesian"],
      toImageButtonOptions:{format:"png",filename:"mario-data-explorer",scale:2},
    };
    return {data, layout, config, scale};
  }
  const api = {scaleFor, scaled, hoverDistance, scatterMarkerSize, usesBars, figure};
  if (typeof module !== "undefined") module.exports = api;
  else global.MarioEconomyCharts = api;
})(globalThis);
