/* One scope view at a time, with persistent filters and shareable fragment URLs. */
(() => {
  'use strict';
  const nav=document.querySelector('[data-scope-tabs]');
  if(!nav)return;
  const controls=nav.closest('[data-scope-controls]');
  const tabs=[...nav.querySelectorAll('[role="tab"][aria-controls]')];
  const panels=tabs.map(tab=>document.getElementById(tab.getAttribute('aria-controls')));
  if(panels.some(panel=>!panel)||!panels.length)return;
  const owner=panels[0].parentElement;
  let selected=null;
  const target=()=>{
    try{return document.getElementById(decodeURIComponent(location.hash.slice(1)));}catch{return null;}
  };
  const indexFor=element=>panels.findIndex(panel=>panel===element||panel.contains(element));
  function select(index,{url=false,scroll=false}={}) {
    const changed=selected!==index;selected=index;
    tabs.forEach((tab,i)=>{tab.setAttribute('aria-selected',String(i===index));tab.tabIndex=i===index?0:-1;});
    panels.forEach((panel,i)=>{panel.hidden=i!==index;});
    if(url&&location.hash!==tabs[index].hash)history.pushState(null,'',tabs[index].hash);
    requestAnimationFrame(()=>{
      if(changed)window.dispatchEvent(new Event('resize'));
      if(scroll)controls.scrollIntoView({block:'start',behavior:'instant'});
    });
  }
  function readHash(scroll=false) {
    const index=indexFor(target());
    select(index<0?0:index,{scroll});
  }
  panels.forEach((panel,i)=>{
    panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',tabs[i].id);panel.tabIndex=0;
  });
  owner.classList.add('explorer-scope-ready');controls.hidden=false;readHash();
  tabs.forEach((tab,index)=>{
    tab.addEventListener('click',event=>{
      if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
      event.preventDefault();select(index,{url:true});
    });
    tab.addEventListener('keydown',event=>{
      let next=index;
      if(event.key==='ArrowRight')next=(index+1)%tabs.length;
      else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
      else if(event.key==='Home')next=0;
      else if(event.key==='End')next=tabs.length-1;
      else if(event.key!==' ')return;
      event.preventDefault();tabs[next].focus();select(next,{url:true});
    });
  });
  window.addEventListener('hashchange',()=>readHash(true));
  window.addEventListener('popstate',()=>readHash(true));
  // Stabilise an initial deep link while fonts and the selected chart load.
  // Stop as soon as the reader interacts, so delayed loading never moves them.
  if(indexFor(target())>=0) {
    let pending=true;
    const events=['wheel','touchstart','pointerdown','keydown'];
    const stop=()=>{pending=false;observer.disconnect();events.forEach(type=>window.removeEventListener(type,stop,true));};
    const settle=()=>{
      if(!pending||document.fonts?.status==='loading'||panels[selected].querySelector('[aria-busy="true"]'))return;
      requestAnimationFrame(()=>{if(pending){controls.scrollIntoView({block:'start',behavior:'instant'});stop();}});
    };
    const observer=new MutationObserver(settle);
    observer.observe(owner,{subtree:true,attributes:true,attributeFilter:['aria-busy']});
    events.forEach(type=>window.addEventListener(type,stop,{capture:true,passive:true}));
    window.addEventListener('load',settle,{once:true});document.fonts?.ready.then(settle);
    requestAnimationFrame(settle);
  }
})();
