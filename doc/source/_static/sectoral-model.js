/* Reference-leaf resolution. Filtering never changes a section denominator. */
((global)=>{
 'use strict';
 function index(data,kind='activity'){
  const ref=data.references[kind],nodes=new Map(ref.nodes.map(n=>[n.code,n]));
  const leaves=ref.leaves.map(code=>nodes.get(code));
  const columns=data.columns[kind].map(column=>{
   const byReference=new Map(),native=column.native.map(item=>{
    const links=Object.fromEntries(Object.entries(item.links).map(([code,link])=>[code,{...item.link_defaults,...link}]));
    const classes=Object.keys(links),bySection=new Map();
    for(const code of classes){const section=nodes.get(code)?.section;if(!section)continue;if(!bySection.has(section))bySection.set(section,[]);bySection.get(section).push(code);}
    return {...item,links,classes,bySection};
   });
   for(const item of native)for(const code of item.classes){if(!byReference.has(code))byReference.set(code,[]);byReference.get(code).push(item);}
   return {...column,native,byReference};
  });
  const model={kind,ref,nodes,leaves,columns};
  model.maximum=Math.max(2,...columns.flatMap(c=>leaves.map(n=>cell(model,c,n.code).resolution||1)));
  return model;
 }
 function ancestors(model,code){const chain=[];let node=model.nodes.get(code);while(node){chain.unshift(node);node=model.nodes.get(node.parent);}return chain;}
 function rows(model,area=''){if(!area)return model.leaves;return model.leaves.filter(n=>ancestors(model,n.code).some(a=>a.code===area));}
 function cell(model,column,code){
  const reference=model.nodes.get(code),denominator=model.ref.section_counts[reference.section];
  const matches=(column.byReference.get(code)||[]).map(native=>{
   const inside=native.bySection.get(reference.section)||[];
   return {native,inside,outside:native.classes.filter(c=>model.nodes.get(c).section!==reference.section),count:inside.length,denominator,fraction:inside.length/denominator,link:native.links[code]};
  });
  const counts=matches.map(m=>m.count);
  // A many-to-many overlap is not a subdivision. Use 1/k only when every
  // matching category links exclusively to this leaf across the full taxonomy
  // and no selected correspondence route contains a partial overlap.
  const split=matches.length>1&&matches.every(m=>m.native.classes.length===1&&m.link.status!=='partial'&&m.link.exclusive_reference!==false);
  const maximum=matches.length?Math.max(...counts):null;
  const pending=column.native.filter(n=>n.pending?.references.includes(code));
  const coarse=column.native.filter(n=>n.coarse?.reference_candidates?n.coarse.reference_candidates.includes(code):n.coarse?.reference_sections.includes(reference.section));
  return {code,section:reference.section,denominator,matches,pending,coarse,status:matches.length?'documented':'unverified',
   minimum:matches.length?Math.min(...counts):null,maximum,
   resolution:split?1/matches.length:maximum,splitCount:split?matches.length:0,
   resolutionBasis:split?'exclusive_native_split':matches.length?'linked_reference_classes':'unverified'};
 }
 function labels(model,visible,level){
  const groups=[];
  visible.forEach((row,i)=>{
   const node=ancestors(model,row.code).find(n=>n.level===level)||row;
   const last=groups.at(-1);if(last?.code===node.code){last.end=i;return;}
   groups.push({code:node.code,name:node.name,start:i,end:i});
  });
  const stride=Math.max(1,Math.ceil(groups.length/32));
  return groups.filter((_,i)=>i%stride===0).map(g=>({...g,position:(g.start+g.end)/2}));
 }
 function geometry(visible){
  const counts=new Map();for(const row of visible)counts.set(row.section,(counts.get(row.section)||0)+1);
  // Thousands of CPA rows need larger minimum section bands to keep the
  // overview letters legible. This changes coordinates only, never counts.
  const minimum=visible.length>1000?visible.length/12:25;
  const edges=[0];for(const row of visible)edges.push(edges.at(-1)+Math.max(1,minimum/counts.get(row.section)));
  return {edges,centres:visible.map((_,i)=>(edges[i]+edges[i+1])/2),end:edges.at(-1)};
 }
 function rowAt(geometry,value){let lo=0,hi=geometry.edges.length-1;while(lo<hi){const mid=Math.floor((lo+hi)/2);if(geometry.edges[mid+1]<=value)lo=mid+1;else hi=mid;}return Math.min(lo,geometry.edges.length-2);}
 // Fixed domains survive filtering. CPA has many more leaves than NACE, so
 // its broad tail needs more room; log spacing retains the low-count detail.
 // These display transforms never change native resolution or CSV values.
 const domains={
  activity:{midpoint:10,ceiling:50,ticks:[0,1,2,5,10,20,50],logLow:false},
  commodity:{midpoint:50,ceiling:300,ticks:[0,1,5,10,25,50,100,300],logLow:true}
 };
 function colourDomain(kind='activity'){return domains[kind]||domains.activity;}
 function scaleValue(value,kind='activity'){
  if(value===null)return null;
  const {midpoint:scaleMidpoint,ceiling:scaleCeiling,logLow}=colourDomain(kind);
  const bounded=Math.min(scaleCeiling,Math.max(0,value));
  return bounded<=scaleMidpoint?.5*(logLow?Math.log1p(bounded)/Math.log1p(scaleMidpoint):bounded/scaleMidpoint):.5+.5*Math.log(bounded/scaleMidpoint)/Math.log(scaleCeiling/scaleMidpoint);
 }
 function colourScale(fine,middle,coarse){return [[0,fine],[.5,middle],[1,coarse]];}
 function resolutionLabel(c){return c.resolution===null?'Unverified':c.splitCount?'1/'+c.splitCount:String(c.resolution);}
 function selection(visible,columns,coordinates,code,columnId){
  const row=visible.findIndex(n=>n.code===code),column=columns.findIndex(c=>c.id===columnId);
  return row<0||column<0?null:{x0:column-.5,x1:column+.5,y0:coordinates.edges[row],y1:coordinates.edges[row+1]};
 }
 function matrix(model,visible,columns){
  return visible.map(row=>columns.map(column=>scaleValue(cell(model,column,row.code).resolution,model.kind)));
 }
 const api={index,ancestors,rows,cell,labels,geometry,rowAt,scaleValue,colourDomain,colourScale,resolutionLabel,selection,matrix};
 if(typeof module!=='undefined')module.exports=api;else global.MarioSectoralScope=api;
})(globalThis);
