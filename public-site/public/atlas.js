'use strict';
import {catalogMaps,mapFor,clockFor,mapAtHour,hourFromTime,hourLabel,hourFromDialPoint,offsetForBounds,editionFromQuery,levelForEdition} from './atlas-model.js';
const query=new URLSearchParams(location.search);
let activeEdition=editionFromQuery(query.get('dataset')),selectedLevel=Number(query.get('level')||0),mapUnavailable=false;
const lastLevels=new Map();
const catalogs=new Map(),editionButtons=[...document.querySelectorAll('[data-edition]')];
let preferredHour=hourFromTime(query.get('time'))??12,clockUnavailable=false;
const clockDial=document.querySelector('#clock-dial'),clockValue=document.querySelector('#clock-value');
const lightingControls=document.querySelector('#lighting-controls');
const canvas=document.querySelector('#map'),ctx=canvas.getContext('2d'),levelList=document.querySelector('#levels');
const notice=document.querySelector('#notice'),download=document.querySelector('#download');
let MAPS=[],current,scale=1,ox=0,oy=0,overview,raf=0,loaded=new Map(),available=new Set(),failures=0;
const tiffDownload=document.querySelector('#download-tiff');
function fileSize(bytes){if(!Number.isFinite(bytes))return '—';return bytes>=1e9?(bytes/1e9).toFixed(2)+' GB':bytes>=1e6?(bytes/1e6).toFixed(1)+' MB':(bytes/1e3).toFixed(0)+' KB'}
const pointers=new Map();let gesture=null,panDistance=0;
const credits=document.querySelector('#credits'),creditsOpen=document.querySelector('#credits-open');
creditsOpen.addEventListener('click',()=>credits.showModal());
credits.addEventListener('click',e=>{if(e.target===credits){const r=credits.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)credits.close()}});
credits.addEventListener('close',()=>creditsOpen.focus({preventScroll:true}));
function request(){if(!raf)raf=requestAnimationFrame(draw)}
function fit(){if(!current)return;scale=Math.min(canvas.width/current.width,canvas.height/current.height)*.94;ox=(canvas.width-current.width*scale)/2;oy=(canvas.height-current.height*scale)/2;request()}
function resize(){const r=canvas.getBoundingClientRect();canvas.width=Math.round(r.width);canvas.height=Math.round(r.height);if(current)fit()}
function file(name){return '/api/file?'+new URLSearchParams({revision:current.revision,level:current.level,variant:current.variant,dataset:activeEdition,name})}
function updateClock(level){
 const clock=clockFor(MAPS,level);lightingControls.hidden=!clock||mapUnavailable;
 clockValue.value=hourLabel(preferredHour);clockDial.setAttribute('aria-valuenow',preferredHour);
 document.querySelector('#clock-hand').setAttribute('transform','rotate('+(preferredHour*15)+' 60 60)');
 for(const label of document.querySelectorAll('#clock-labels text'))label.classList.toggle('selected',Number(label.dataset.hour)===preferredHour);
 const state=clock?.hours.find(h=>h.hour===preferredHour)?.variant;
 const phase=state==='twilight'?(preferredHour<12?'Dawn':'Dusk'):state==='night'?'Night':'Daylight';
 clockDial.setAttribute('aria-valuetext',hourLabel(preferredHour)+', '+phase);
 document.querySelector('#clock-title').textContent=hourLabel(preferredHour)+' · '+phase+' — drag the hour hand';
}
function updateRecovery(){const note=document.querySelector('#recovery-note');note.hidden=mapUnavailable||!current?.recovery;note.textContent=current?.recovery?'Recovered · '+current.recovery.omitted_placements+' missing object placements':''}
function downloadEdition(){return activeEdition==='retail'?'retail-1.22l'+(current?.recovery?'-recovered':''):'july-1999'}
function updateDownloads(){
 for(const link of [download,tiffDownload])link.setAttribute('aria-disabled',String(clockUnavailable||mapUnavailable));
 if(clockUnavailable||mapUnavailable){for(const link of [download,tiffDownload]){link.removeAttribute('href');link.removeAttribute('download')}document.querySelector('#png-size').textContent='—';document.querySelector('#tiff-size').textContent='—';document.querySelector('#dimensions').textContent='';return}
 download.href=file('full-resolution.png');download.setAttribute('download','revenant-'+downloadEdition()+'-level-'+current.level+'-'+current.variant+'.png');
 document.querySelector('#png-size').textContent=fileSize(current.png_bytes);download.title='Download '+(current.recovery?'recovered ':'')+'PNG, '+fileSize(current.png_bytes);download.setAttribute('aria-label',download.title);
 document.querySelector('#tiff-size').textContent=fileSize(current.tiff_bytes);
 if(current.tiff_bytes){tiffDownload.href=file('full-resolution.tif');tiffDownload.setAttribute('download','revenant-'+downloadEdition()+'-level-'+current.level+'-'+current.variant+'.tif');tiffDownload.title='Download '+(current.recovery?'recovered ':'')+'lossless tiled BigTIFF, '+fileSize(current.tiff_bytes);tiffDownload.setAttribute('aria-label',tiffDownload.title)}
 else{tiffDownload.removeAttribute('href');tiffDownload.setAttribute('aria-disabled','true')}
 document.querySelector('#dimensions').textContent=current.width.toLocaleString()+' × '+current.height.toLocaleString()+' pixels';
}
function updateLocation(level){try{const url=new URL(window.parent.location.href);url.searchParams.set('level',level);url.searchParams.set('time',hourLabel(preferredHour));url.searchParams.set('dataset',activeEdition);window.parent.history.replaceState(null,'',url)}catch{}}
function change(preserveView=false){
 const level=selectedLevel,previous=current;updateLevelSelection();mapUnavailable=!MAPS.some(m=>m.level===level);updateClock(level);
 if(mapUnavailable){clockUnavailable=false;updateLocation(level);updateRecovery();updateDownloads();canvas.setAttribute('aria-busy','false');notice.hidden=false;notice.textContent='This location is not available in '+(activeEdition==='july'?'July 1999':'Retail 1.22L')+'. Choose another location or switch editions.';request();return}
 const selected=mapAtHour(MAPS,level,preferredHour);clockUnavailable=!selected;
 current=selected||(previous?.level===level?previous:mapFor(MAPS,level,'day'));if(!current)return;
 if(clockPointer===null)updateLocation(level);
 updateRecovery();updateDownloads();canvas.setAttribute('aria-busy',String(clockUnavailable));clockDial.classList.toggle('pending',clockUnavailable);
 if(clockUnavailable){notice.hidden=false;notice.textContent=hourLabel(preferredHour)+' lighting is still rendering.'}
 if(previous?.revision===current.revision){if(!clockUnavailable&&!mapUnavailable)notice.hidden=true;request();return}
 loaded.clear();available=new Set(current.tiles.map(t=>t.join('_')));failures=0;
 if(!clockUnavailable){notice.hidden=false;notice.textContent='Opening '+(current.names.join(' / ')||'level '+current.level)+'…'}
 const image=new Image();overview=image;image.onload=()=>{if(overview!==image)return;if(!clockUnavailable&&!mapUnavailable)notice.hidden=true;request()};image.onerror=()=>{if(overview===image){notice.hidden=false;notice.textContent='The map could not load. Select it again to retry.'}};image.src=file('overview.jpg');
 if(preserveView&&previous&&previous.level===current.level){const offset=offsetForBounds(ox,oy,scale,previous.bounds,current.bounds);ox=offset.x;oy=offset.y;request()}else fit();
}
function setHour(hour){preferredHour=((hour%24)+24)%24;change(true)}
const svgNS='http://www.w3.org/2000/svg';
for(let hour=0;hour<24;hour++){
 const angle=hour*Math.PI/12,sin=Math.sin(angle),cos=Math.cos(angle);
 const mark=document.createElementNS(svgNS,'line');
 for(const [name,value]of Object.entries({x1:60+sin*(hour%6?51:49),y1:60-cos*(hour%6?51:49),x2:60+sin*54,y2:60-cos*54}))mark.setAttribute(name,value);
 document.querySelector('#clock-marks').append(mark);
 const label=document.createElementNS(svgNS,'text');label.setAttribute('x',60+sin*42);label.setAttribute('y',60-cos*42);label.dataset.hour=hour;label.textContent=hour;document.querySelector('#clock-labels').append(label);
}
let clockPointer=null;
function pointHour(e){const r=clockDial.getBoundingClientRect();return hourFromDialPoint((e.clientX-r.left-r.width/2)*2/r.width,(e.clientY-r.top-r.height/2)*2/r.height)}
clockDial.addEventListener('pointerdown',e=>{if(e.button!==0||clockPointer!==null)return;e.preventDefault();clockDial.focus({preventScroll:true});clockPointer=e.pointerId;clockDial.setPointerCapture(e.pointerId);clockDial.classList.add('dragging');const h=pointHour(e);if(h!==null)setHour(h)});
clockDial.addEventListener('pointermove',e=>{if(e.pointerId!==clockPointer)return;const h=pointHour(e);if(h!==null&&h!==preferredHour)setHour(h)});
for(const type of ['pointerup','pointercancel','lostpointercapture'])clockDial.addEventListener(type,e=>{if(e.pointerId!==clockPointer)return;clockPointer=null;updateLocation(selectedLevel);clockDial.classList.remove('dragging');if(clockDial.hasPointerCapture(e.pointerId))clockDial.releasePointerCapture(e.pointerId)});
clockDial.addEventListener('keydown',e=>{let h=preferredHour;if(e.key==='ArrowRight'||e.key==='ArrowUp')h++;else if(e.key==='ArrowLeft'||e.key==='ArrowDown')h--;else if(e.key==='Home')h=0;else if(e.key==='End')h=23;else return;e.preventDefault();e.stopPropagation();setHour(h)});
function tile(tx,ty){const key=tx+'_'+ty;if(!available.has(key))return null;if(loaded.has(key)){const im=loaded.get(key);loaded.delete(key);loaded.set(key,im);return im}const im=new Image();const revision=current.revision;im.onload=()=>{if(current.revision===revision)request()};im.onerror=()=>{if(current.revision===revision&&!mapUnavailable){failures++;notice.hidden=false;notice.textContent='Some map tiles could not load. Select the map again to retry.'}};im.src='/api/tile?'+new URLSearchParams({revision:current.revision,level:current.level,x:tx,y:ty});loaded.set(key,im);const limit=canvas.width<700?48:120;while(loaded.size>limit)loaded.delete(loaded.keys().next().value);return im}
function draw(){raf=0;ctx.fillStyle='#000';ctx.fillRect(0,0,canvas.width,canvas.height);if(!current||mapUnavailable)return;ctx.imageSmoothingEnabled=scale<1;if(overview?.complete&&overview.naturalWidth)ctx.drawImage(overview,ox,oy,current.width*scale,current.height*scale);if(scale>.095){const n=current.tile_size,x0=Math.max(0,Math.floor(-ox/scale/n)),y0=Math.max(0,Math.floor(-oy/scale/n)),x1=Math.min(Math.ceil(current.width/n),Math.ceil((canvas.width-ox)/scale/n)),y1=Math.min(Math.ceil(current.height/n),Math.ceil((canvas.height-oy)/scale/n));for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){const im=tile(x,y);if(im?.complete&&im.naturalWidth)ctx.drawImage(im,ox+x*n*scale,oy+y*n*scale,im.naturalWidth*scale,im.naturalHeight*scale)}}document.querySelector('#zoom-value').textContent=(scale*100).toFixed(scale<.1?1:0)+'%';document.querySelector('#actual').setAttribute('aria-pressed',String(scale===1))}
function zoom(f,x=canvas.width/2,y=canvas.height/2){if(!current)return;const next=Math.max(.002,Math.min(8,scale*f));ox=x-(x-ox)*next/scale;oy=y-(y-oy)*next/scale;scale=next;request()}
function gestureState(){const values=[...pointers.values()];if(values.length>=2){const[a,b]=values;gesture={kind:'pinch',x:(a.x+b.x)/2,y:(a.y+b.y)/2,distance:Math.hypot(a.x-b.x,a.y-b.y)}}else if(values.length===1){gesture={kind:'pan',...values[0]}}else gesture=null}
canvas.addEventListener('pointerdown',e=>{if(!current||e.button!==0)return;canvas.focus({preventScroll:true});pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});canvas.setPointerCapture(e.pointerId);gestureState();canvas.classList.add('dragging');panDistance=0});
canvas.addEventListener('pointermove',e=>{if(!pointers.has(e.pointerId))return;const old=gesture;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});gestureState();if(!old||!gesture||old.kind!==gesture.kind)return;const dx=gesture.x-old.x,dy=gesture.y-old.y;panDistance+=Math.abs(dx)+Math.abs(dy);ox+=dx;oy+=dy;if(gesture.kind==='pinch'&&old.distance>0){const r=canvas.getBoundingClientRect();zoom(gesture.distance/old.distance,gesture.x-r.left,gesture.y-r.top)}request()});
for(const type of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(type,e=>{pointers.delete(e.pointerId);gestureState();if(!pointers.size)canvas.classList.remove('dragging')});
canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect();zoom(Math.exp(-e.deltaY*.0015),e.clientX-r.left,e.clientY-r.top)},{passive:false});
document.querySelector('#minus').onclick=()=>zoom(.5);document.querySelector('#plus').onclick=()=>zoom(2);document.querySelector('#actual').onclick=()=>zoom(1/scale);document.querySelector('#fit').onclick=fit;window.addEventListener('resize',resize);window.addEventListener('keydown',e=>{if(credits.open||e.target.closest('select,input,button,a,[role=slider]'))return;if(e.key.toLowerCase()==='f')fit();else if(e.key==='1')zoom(1/scale);else if(e.key==='+'||e.key==='=')zoom(2);else if(e.key==='-')zoom(.5)});
function updateLevelSelection(){
 for(const button of levelList.querySelectorAll('[data-level]')){
  const selected=Number(button.dataset.level)===selectedLevel;
  button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;
 }
}
function chooseLevel(level,focus=false){
 selectedLevel=level;lastLevels.set(activeEdition,level);change();
 const button=levelList.querySelector('[data-level="'+level+'"]');
 if(focus)button?.focus({preventScroll:true});button?.scrollIntoView({block:'nearest'});
}
levelList.addEventListener('click',e=>{const button=e.target.closest('[data-level]');if(button)chooseLevel(Number(button.dataset.level))});
levelList.addEventListener('keydown',e=>{
 const buttons=[...levelList.querySelectorAll('[data-level]')],index=buttons.findIndex(b=>Number(b.dataset.level)===selectedLevel);
 let next=index;
 if(e.key==='ArrowDown')next=Math.min(index+1,buttons.length-1);else if(e.key==='ArrowUp')next=Math.max(index-1,0);
 else if(e.key==='Home')next=0;else if(e.key==='End')next=buttons.length-1;else return;
 e.preventDefault();e.stopPropagation();if(buttons[next])chooseLevel(Number(buttons[next].dataset.level),true);
});
function editionUI(){
 for(const button of editionButtons)button.setAttribute('aria-pressed',String(button.dataset.edition===activeEdition));
 const all=[...catalogs.values()].flatMap(c=>catalogMaps(c));
 const levels=[...new Set(MAPS.map(m=>m.level))].sort((a,b)=>a-b);
 levelList.replaceChildren();
 for(const level of levels){
  const own=MAPS.find(m=>m.level===level),m=own.names?.length?own:all.find(m=>m.level===level&&m.names?.length)||own;
  const button=document.createElement('button');button.type='button';button.dataset.level=level;button.setAttribute('role','option');
  const name=document.createElement('span');name.className='level-name';name.textContent=level===0?'Ahkuilon island':m.names.join(' / ')||'Map '+level;
  const number=document.createElement('span');number.className='level-number';number.textContent='Level '+level;button.append(name,number);
  if(own.recovery){const label=document.createElement('span');label.className='level-recovered';label.textContent='Recovered';button.append(label)}
  levelList.append(button);
 }
 updateLevelSelection();
}
function activateEdition(edition,preserveView=true){
 lastLevels.set(activeEdition,selectedLevel);activeEdition=edition;MAPS=catalogMaps(catalogs.get(edition));
 selectedLevel=levelForEdition(MAPS,selectedLevel,lastLevels.get(edition));lastLevels.set(edition,selectedLevel);
 editionUI();change(preserveView);levelList.querySelector('[aria-selected="true"]')?.scrollIntoView({block:'nearest'});
}
let refreshId=0;
async function loadCatalog(initial=false){
 const id=++refreshId,edition=activeEdition;
 const editions=initial?['july','retail']:[edition];
 const results=await Promise.allSettled(editions.map(async key=>{const r=await fetch('/api/catalog'+(key==='retail'?'?dataset=retail':''),{cache:'no-store'});if(!r.ok)throw Error('The '+(key==='july'?'July 1999':'retail')+' maps could not load. Refresh to retry.');const c=await r.json();if(!catalogMaps(c).length)throw Error('No maps are available yet.');return c}));
 if(id!==refreshId)return;
 for(let i=0;i<results.length;i++)if(results[i].status==='fulfilled')catalogs.set(editions[i],results[i].value);
 if(!catalogs.has(edition))throw results[editions.indexOf(edition)].reason;
 if(initial)selectedLevel=levelForEdition(catalogMaps(catalogs.get(edition)),selectedLevel);
 activateEdition(edition,!initial);
}
for(const button of editionButtons)button.addEventListener('click',async()=>{
 const edition=button.dataset.edition;if(edition===activeEdition)return;
 if(catalogs.has(edition)){refreshId++;activateEdition(edition);return}
 // Keep the visible edition selected until a failed catalog can be fetched again.
 button.disabled=true;const id=++refreshId;
 try{const r=await fetch('/api/catalog'+(edition==='retail'?'?dataset=retail':''),{cache:'no-store'});if(!r.ok)throw Error();const c=await r.json();if(!catalogMaps(c).length)throw Error();if(id!==refreshId)return;catalogs.set(edition,c);activateEdition(edition)}catch{notice.hidden=false;notice.textContent='That edition could not load. Select it again to retry.'}finally{button.disabled=false}
});
resize();loadCatalog(true).catch(e=>{notice.hidden=false;notice.textContent=e.message});
setInterval(()=>{if(clockUnavailable)loadCatalog().catch(()=>{})},30000);
