'use strict';
import {catalogMaps,mapFor,clockFor,mapAtHour,hourFromTime,hourLabel} from './atlas-model.js';
const query=new URLSearchParams(location.search),retailPreview=query.get('dataset')==='retail';
let preferredHour=hourFromTime(query.get('time'))??12,clockUnavailable=false;
const clockTime=document.querySelector('#clock-time'),clockHour=document.querySelector('#clock-hour'),clockState=document.querySelector('#clock-state');
const lightingControls=document.querySelector('#lighting-controls');
document.querySelector('#dataset-label').hidden=!retailPreview;
const canvas=document.querySelector('#map'),ctx=canvas.getContext('2d'),select=document.querySelector('#levels');
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
function file(name){return '/api/file?'+new URLSearchParams({revision:current.revision,level:current.level,variant:current.variant,name})}
function updateClock(level){
 const clock=clockFor(MAPS,level);lightingControls.hidden=!clock;
 clockTime.value=hourLabel(preferredHour);clockHour.value=preferredHour;
 clockHour.setAttribute('aria-valuetext',hourLabel(preferredHour));
 document.querySelector('#clock-hand').setAttribute('transform','rotate('+(preferredHour*15)+' 24 24)');
 const state=clock?.hours.find(h=>h.hour===preferredHour)?.variant;
 clockState.textContent=state==='twilight'?(preferredHour<12?'Dawn':'Dusk'):state==='night'?'Night':'Daylight';
}
function updateDownloads(){
 for(const link of [download,tiffDownload])link.setAttribute('aria-disabled',String(clockUnavailable));
 if(clockUnavailable){download.removeAttribute('href');tiffDownload.removeAttribute('href');return}
 download.href=file('full-resolution.png');download.setAttribute('download','revenant-level-'+current.level+'-'+current.variant+'.png');
 document.querySelector('#png-size').textContent=fileSize(current.png_bytes);download.title='Download PNG, '+fileSize(current.png_bytes);download.setAttribute('aria-label',download.title);
 document.querySelector('#tiff-size').textContent=fileSize(current.tiff_bytes);
 if(current.tiff_bytes){tiffDownload.href=file('full-resolution.tif');tiffDownload.setAttribute('download','revenant-level-'+current.level+'-'+current.variant+'.tif');tiffDownload.title='Download lossless tiled BigTIFF, '+fileSize(current.tiff_bytes);tiffDownload.setAttribute('aria-label',tiffDownload.title)}
 else{tiffDownload.removeAttribute('href');tiffDownload.setAttribute('aria-disabled','true')}
 document.querySelector('#dimensions').textContent=current.width.toLocaleString()+' × '+current.height.toLocaleString()+' pixels';
}
function change(preserveView=false){
 const level=Number(select.value),previous=current;updateClock(level);
 const selected=mapAtHour(MAPS,level,preferredHour);clockUnavailable=!selected;
 current=selected||(previous?.level===level?previous:mapFor(MAPS,level,'day'));if(!current)return;
 try{const url=new URL(window.parent.location.href);url.searchParams.set('level',level);url.searchParams.set('time',hourLabel(preferredHour));if(retailPreview)url.searchParams.set('dataset','retail');window.parent.history.replaceState(null,'',url)}catch{}
 updateDownloads();canvas.setAttribute('aria-busy',String(clockUnavailable));
 if(clockUnavailable){notice.hidden=false;notice.textContent=hourLabel(preferredHour)+' lighting is still rendering.';clockState.textContent='Rendering…'}
 if(previous?.revision===current.revision){if(!clockUnavailable)notice.hidden=true;return}
 loaded.clear();available=new Set(current.tiles.map(t=>t.join('_')));failures=0;
 if(!clockUnavailable){notice.hidden=false;notice.textContent='Opening '+(current.names.join(' / ')||'level '+current.level)+'…'}
 const image=new Image();overview=image;image.onload=()=>{if(overview!==image)return;if(!clockUnavailable)notice.hidden=true;request()};image.onerror=()=>{if(overview===image){notice.hidden=false;notice.textContent='The map could not load. Select it again to retry.'}};image.src=file('overview.jpg');
 if(preserveView&&previous&&previous.level===current.level){ox+=(current.bounds[0]-previous.bounds[0])*scale;oy+=(current.bounds[1]-previous.bounds[1])*scale;request()}else fit();
}
function setHour(hour){clockTime.setCustomValidity('');preferredHour=hour;change(true)}
clockHour.addEventListener('input',()=>setHour(Number(clockHour.value)));
clockTime.addEventListener('change',()=>{const h=hourFromTime(clockTime.value);if(h==null){clockTime.setCustomValidity('Choose a whole hour, such as 06:00.');clockTime.reportValidity();return}clockTime.setCustomValidity('');setHour(h)});
clockTime.addEventListener('input',()=>clockTime.setCustomValidity(''));
function tile(tx,ty){const key=tx+'_'+ty;if(!available.has(key))return null;if(loaded.has(key)){const im=loaded.get(key);loaded.delete(key);loaded.set(key,im);return im}const im=new Image();const revision=current.revision;im.onload=()=>{if(current.revision===revision)request()};im.onerror=()=>{if(current.revision===revision){failures++;notice.hidden=false;notice.textContent='Some map tiles could not load. Select the map again to retry.'}};im.src='/api/tile?'+new URLSearchParams({revision:current.revision,level:current.level,x:tx,y:ty});loaded.set(key,im);const limit=canvas.width<700?48:120;while(loaded.size>limit)loaded.delete(loaded.keys().next().value);return im}
function draw(){raf=0;ctx.fillStyle='#000';ctx.fillRect(0,0,canvas.width,canvas.height);if(!current)return;ctx.imageSmoothingEnabled=scale<1;if(overview?.complete&&overview.naturalWidth)ctx.drawImage(overview,ox,oy,current.width*scale,current.height*scale);if(scale>.095){const n=current.tile_size,x0=Math.max(0,Math.floor(-ox/scale/n)),y0=Math.max(0,Math.floor(-oy/scale/n)),x1=Math.min(Math.ceil(current.width/n),Math.ceil((canvas.width-ox)/scale/n)),y1=Math.min(Math.ceil(current.height/n),Math.ceil((canvas.height-oy)/scale/n));for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){const im=tile(x,y);if(im?.complete&&im.naturalWidth)ctx.drawImage(im,ox+x*n*scale,oy+y*n*scale,im.naturalWidth*scale,im.naturalHeight*scale)}}document.querySelector('#zoom-value').textContent=(scale*100).toFixed(scale<.1?1:0)+'%';document.querySelector('#actual').setAttribute('aria-pressed',String(scale===1))}
function zoom(f,x=canvas.width/2,y=canvas.height/2){if(!current)return;const next=Math.max(.002,Math.min(8,scale*f));ox=x-(x-ox)*next/scale;oy=y-(y-oy)*next/scale;scale=next;request()}
function gestureState(){const values=[...pointers.values()];if(values.length>=2){const[a,b]=values;gesture={kind:'pinch',x:(a.x+b.x)/2,y:(a.y+b.y)/2,distance:Math.hypot(a.x-b.x,a.y-b.y)}}else if(values.length===1){gesture={kind:'pan',...values[0]}}else gesture=null}
canvas.addEventListener('pointerdown',e=>{if(!current||e.button!==0)return;canvas.focus({preventScroll:true});pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});canvas.setPointerCapture(e.pointerId);gestureState();canvas.classList.add('dragging');panDistance=0});
canvas.addEventListener('pointermove',e=>{if(!pointers.has(e.pointerId))return;const old=gesture;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});gestureState();if(!old||!gesture||old.kind!==gesture.kind)return;const dx=gesture.x-old.x,dy=gesture.y-old.y;panDistance+=Math.abs(dx)+Math.abs(dy);ox+=dx;oy+=dy;if(gesture.kind==='pinch'&&old.distance>0){const r=canvas.getBoundingClientRect();zoom(gesture.distance/old.distance,gesture.x-r.left,gesture.y-r.top)}request()});
for(const type of ['pointerup','pointercancel','lostpointercapture'])canvas.addEventListener(type,e=>{pointers.delete(e.pointerId);gestureState();if(!pointers.size)canvas.classList.remove('dragging')});
canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect();zoom(Math.exp(-e.deltaY*.0015),e.clientX-r.left,e.clientY-r.top)},{passive:false});
document.querySelector('#minus').onclick=()=>zoom(.5);document.querySelector('#plus').onclick=()=>zoom(2);document.querySelector('#actual').onclick=()=>zoom(1/scale);document.querySelector('#fit').onclick=fit;select.onchange=()=>change();for(const button of lightingControls.querySelectorAll('button'))button.onclick=()=>{setHour(button.dataset.time==='night'?1:12)};window.addEventListener('resize',resize);window.addEventListener('keydown',e=>{if(credits.open||e.target.closest('select,input,button,a'))return;if(e.key.toLowerCase()==='f')fit();else if(e.key==='1')zoom(1/scale);else if(e.key==='+'||e.key==='=')zoom(2);else if(e.key==='-')zoom(.5)});
const catalogUrl='/api/catalog'+(retailPreview?'?dataset=retail':'');
async function loadCatalog(initial=false){const r=await fetch(catalogUrl,{cache:'no-store'});if(!r.ok)throw Error('The maps could not load. Refresh the page to retry.');const c=await r.json();MAPS=catalogMaps(c);if(!MAPS.length)throw Error('No maps are available yet.');
 if(initial){select.replaceChildren();for(const level of [...new Set(MAPS.map(m=>m.level))]){const m=mapFor(MAPS,level,'day'),o=document.createElement('option');o.value=level;o.textContent=(level===0?'Ahkuilon island':m.names.join(' / ')||'Map')+' — Level '+level;select.append(o)}const requested=Number(query.get('level')||0);select.value=MAPS.some(m=>m.level===requested)?requested:MAPS[0].level}
 change(!initial);
}
resize();loadCatalog(true).catch(e=>{notice.hidden=false;notice.textContent=e.message});
setInterval(()=>{if(clockUnavailable)loadCatalog().catch(()=>{})},30000);
