/* Country-specific set comparison and revision-aware correspondence queries. */
((global)=>{
 "use strict";
 const unique=values=>[...new Set(values)];
 const economic=['Sector','Activity','Commodity'];
 const countryRegions=(profile,country)=>profile.regions.filter(r=>r.kind==='country'&&r.iso3===country);
 const years=profile=>unique(profile.years.map(Number)).sort((a,b)=>a-b);
 function countries(profiles){
  const entries=new Map();
  for(const p of profiles)for(const r of p.regions)if(r.kind==='country'&&r.iso3&&!entries.has(r.iso3))entries.set(r.iso3,{id:r.iso3,name:r.name});
  return [...entries.values()].sort((a,b)=>a.name.localeCompare(b.name));
 }
 function nativeSet(profile,country,dimension){
  const regions=countryRegions(profile,country);
  if(!regions.length)return [];
  return unique(regions.flatMap(r=>profile.memberships[r.label]?.[dimension] || profile.sets[dimension] || []));
 }
 function counts(profile,country){
  return {...profile.counts,...Object.fromEntries(economic.filter(k=>k in profile.sets).map(k=>[k,nativeSet(profile,country,k).length]))};
 }
 function latestProfiles(profiles){
  const revision=p=>p.version||p.release;
  const families=unique(profiles.map(p=>p.family)), ids=new Set();
  for(const f of families){
   const rows=profiles.filter(p=>p.family===f);
   if(f==='OECD'){for(const p of rows)ids.add(p.id);continue;}
   const numeric=rows.filter(p=>/^\d+(\.\d+)*$/.test(revision(p))||f==='ADB');
   const release=revision(numeric.length?[...numeric].sort((a,b)=>f==='ADB'?parseInt(revision(b))-parseInt(revision(a)):revision(b).localeCompare(revision(a),undefined,{numeric:true}))[0]:[...rows].sort((a,b)=>Math.max(...years(b))-Math.max(...years(a)))[0]);
   // Preserve alternative unit and scope structures alongside newer releases.
   const scopeKey=p=>JSON.stringify([p.units,p.scope_group||'']);
   for(const group of unique(rows.map(scopeKey))){
    const candidates=rows.filter(p=>scopeKey(p)===group), pool=candidates.filter(p=>revision(p)===release);
    const chosen=pool.length?pool:[...candidates].sort((a,b)=>Math.max(...years(b))-Math.max(...years(a))).filter((p,i,all)=>revision(p)===revision(all[0]));
    for(const p of chosen)ids.add(p.id);
   }
  }
  return profiles.filter(p=>ids.has(p.id));
 }
 function visibleProfiles(profiles,{country,year='all',older=false}){
  const eligible=profiles.filter(p=>countryRegions(p,country).length && (year==='all'||years(p).includes(Number(year))));
  return (older?eligible:latestProfiles(eligible)).sort((a,b)=>a.family.localeCompare(b.family)||b.release.localeCompare(a.release,undefined,{numeric:true})||a.units.localeCompare(b.units)||String(a.system).localeCompare(String(b.system))||Math.max(...years(b))-Math.max(...years(a)));
 }
 const nodeCache=new WeakMap();
 function ancestors(classification,code){
  if(!nodeCache.has(classification))nodeCache.set(classification,new Map(classification.nodes.map(n=>[n.code,n])));
  const nodes=nodeCache.get(classification), seen=new Set();let current=nodes.get(code);
  while(current&&!seen.has(current.code)){seen.add(current.code);current=nodes.get(current.parent);}
  return seen;
 }
 function query(profile,country,classification,code,mappings){
  const mapping=(profile.mapping_ids || [profile.mapping]).map(id=>mappings[id]).find(m=>m?.classification===classification.id);
  if(!mapping||mapping.classification!==classification.id)return {status:'unavailable',reason:'No verified mapping for this classification revision.',matches:[]};
  const node=classification.nodes.find(n=>n.code===code);
  if(!node)return {status:'unavailable',reason:'Select a classification code.',matches:[]};
  const natives=new Set((mapping.dimensions||(mapping.dimension && economic.includes(mapping.dimension)?[mapping.dimension]:economic)).flatMap(d=>nativeSet(profile,country,d)));
  const source=mapping.depth>1?mapping.section_entries:mapping.entries;
  if(node.level===1){
   const matches=source.filter(e=>e.official_code.split('+').includes(code)&&natives.has(e.native_label));
   const seen=new Set();
   const distinct=matches.filter(e=>{if(seen.has(e.native_code))return false;seen.add(e.native_code);return true;});
   return {status:'mapped',matches:distinct.map(e=>({...e,relation:e.official_code.includes('+')?'Cross-section aggregate':'Within section'})),within:distinct.filter(e=>e.official_code===code).length,cross:distinct.filter(e=>e.official_code!==code).length,complete:true,source:mapping};
  }
  if(mapping.depth<node.level){
   const ancestor=classification.nodes.find(n=>n.level===1&&ancestors(classification,code).has(n.code));
   const broader=ancestor?query(profile,country,classification,ancestor.code,mappings):null;
   return {status:'coarse',reason:'Detailed mapping unavailable; only section-level correspondences are verified.',ancestor,
    matches:broader?.matches.map(e=>({...e,relation:'Section-level correspondence; detailed allocation unverified'}))||[],complete:false,source:mapping};
  }
  const descendants=new Set(classification.nodes.filter(n=>ancestors(classification,n.code).has(code)).map(n=>n.code));
  const edges=mapping.entries.filter(e=>descendants.has(e.official_code)&&natives.has(e.native_label));
  const coarse=(mapping.coarse_entries||[]).filter(e=>natives.has(e.native_label)&&e.reference_candidates.some(c=>descendants.has(c)));
  if(!edges.length&&coarse.length){
   const broaderAnchors=unique(coarse.map(e=>e.official_code)).map(code=>classification.nodes.find(n=>n.code===code));
   const ancestor=broaderAnchors[0];
   return {status:'coarse',reason:'Only broader nxbase anchors are available; leaf membership is unverified.',ancestor,broaderAnchors,matches:coarse,complete:false,source:mapping};
  }
  const nativeCodes=unique(edges.map(e=>e.native_code));
  const matches=nativeCodes.map(native_code=>{
   const all=mapping.entries.filter(e=>e.native_code===native_code), selected=edges.filter(e=>e.native_code===native_code), first=selected[0];
   const split=selected.some(e=>unique(mapping.entries.filter(other=>other.official_code===e.official_code).map(other=>other.native_code)).length>1);
   const outside=all.some(e=>!descendants.has(e.official_code));
   return {...first,...mapping.native_details?.[native_code],official_codes:unique(selected.map(e=>e.official_code)),precision:selected.some(e=>e.precision==='partial')?'partial':first.precision,relation:split?'Shared across native categories':outside?'Included in a broader aggregate':'Source correspondence',outside,split};
  });
  return {status:matches.length?'mapped':'unverified',reason:matches.length?'':'No verified detailed correspondence for this code.',matches,coarse_matches:coarse,within:matches.filter(e=>!e.outside).length,cross:matches.filter(e=>e.outside).length,complete:mapping.complete,source:mapping};
 }
 const api={countries,countryRegions,nativeSet,counts,years,latestProfiles,visibleProfiles,ancestors,query};
 if(typeof module!=='undefined')module.exports=api;else global.MarioCountryScope=api;
})(globalThis);
