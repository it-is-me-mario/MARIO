/* Figure exports retain source attribution and the relevant documentation URL. */
((global)=>{
  'use strict';
  function withCredit(config,lines){
    return {...config,
      modeBarButtonsToRemove:[...new Set([...(config.modeBarButtonsToRemove||[]),'toImage'])],
      modeBarButtonsToAdd:[...(config.modeBarButtonsToAdd||[]),{
        name:'Download chart with source credit',icon:global.Plotly.Icons.camera,
        click:async chart=>{
          const uri=await global.Plotly.toImage(chart,{format:'png',scale:2});
          const image=new Image();image.src=uri;await image.decode();
          const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d'),pad=32;
          canvas.width=image.naturalWidth;
          ctx.font='20px Arial';
          const wrapped=[];
          for(const line of lines){
            let current='';
            for(const word of String(line).split(/\s+/)){
              const next=current?current+' '+word:word;
              if(ctx.measureText(next).width>canvas.width-pad*2&&current){wrapped.push(current);current=word;}else current=next;
            }
            wrapped.push(current);
          }
          canvas.height=image.naturalHeight+pad*2+wrapped.length*28;
          ctx.fillStyle=chart.layout.paper_bgcolor||'#fff';ctx.fillRect(0,0,canvas.width,canvas.height);
          ctx.drawImage(image,0,0);ctx.fillStyle=chart.layout.font?.color||'#231b17';ctx.font='20px Arial';
          wrapped.forEach((line,i)=>ctx.fillText(line,pad,image.naturalHeight+pad+22+i*28));
          const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
          const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;
          a.download=(config.toImageButtonOptions?.filename||'mario-data-explorer')+'.png';a.click();
          setTimeout(()=>URL.revokeObjectURL(url),1000);
        }
      }]
    };
  }
  global.MarioFigureDownload={withCredit};
})(globalThis);
