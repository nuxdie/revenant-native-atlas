#!/usr/bin/env python3
"""Build a local, dependency-free tiled map viewer beside the exported PNGs."""
import argparse,json
from pathlib import Path

HTML=r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Revenant — The Isle of Ahkuilon</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#080d0c;color:#dce5dd;font:14px system-ui,sans-serif;overflow:hidden}header{height:74px;display:flex;align-items:center;padding:0 24px;gap:24px;border-bottom:1px solid #28332e;background:#101813}h1{font:600 20px Georgia,serif;margin:0;letter-spacing:.3px}h1 small{display:block;font:10px system-ui;letter-spacing:2px;text-transform:uppercase;color:#a6b79c;margin-bottom:5px}select,button,a{background:#1a261d;color:#dce5dd;border:1px solid #384b3d;border-radius:5px;padding:8px 10px;text-decoration:none}select{max-width:350px}nav{display:flex;gap:6px;margin-left:auto}button{cursor:pointer;font-size:16px}a{font-size:12px}canvas{display:block;touch-action:none;width:100vw;height:calc(100vh - 114px);cursor:grab}canvas.dragging{cursor:grabbing}footer{height:40px;display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-top:1px solid #28332e;background:#101813;color:#a6b79c;font-size:12px}.help{opacity:.75}@media(max-width:800px){header{padding:8px;height:106px;gap:8px;flex-wrap:wrap}h1{font-size:17px}select{max-width:200px}canvas{height:calc(100vh - 146px)}.help{display:none}footer{padding:0 8px}}
</style>
<header><h1><small id="provider">Revenant · Native artwork atlas</small>The Isle of Ahkuilon</h1><select id="levels" aria-label="Map area"></select><nav><button id="minus" aria-label="Zoom out">−</button><button id="plus" aria-label="Zoom in">+</button><button id="fit">Fit map</button><a href="../CREDITS.md" target="_blank">Credits</a><a id="validation" href="fidelity.html" hidden>Fidelity checks</a><a id="download" download>Full-resolution PNG ↓</a></nav></header>
<canvas id="map" aria-label="Pan and zoom the Revenant map"></canvas>
<footer><span id="status"></span><span class="help">Drag to pan · Scroll to zoom · 1 for actual pixels · F to fit</span></footer>
<script>
'use strict';
const MAPS=__MAPS__;
const canvas=document.querySelector('#map'), ctx=canvas.getContext('2d'), select=document.querySelector('#levels'), status=document.querySelector('#status');
let current,scale=1,ox=0,oy=0,overview,drag=null,raf=0,loaded=new Map(),available=new Set(),failures=0;
for(const m of MAPS){const o=document.createElement('option');o.value=m.level;o.textContent=`${m.level===0?'Outdoor island':(m.names.join(' / ')||'Map level '+m.level)} · Level ${m.level}`;select.append(o)}
function request(){if(!raf)raf=requestAnimationFrame(draw)}
function fit(){scale=Math.min(canvas.width/current.width,canvas.height/current.height)*.94;ox=(canvas.width-current.width*scale)/2;oy=(canvas.height-current.height*scale)/2;request()}
function resize(){const r=canvas.getBoundingClientRect();canvas.width=Math.round(r.width);canvas.height=Math.round(r.height);if(current)fit()}
function change(){current=MAPS.find(m=>m.level==select.value);document.querySelector('#provider').textContent=current.provider==='original_game'?'Revenant · Original game captures':'Revenant · Static artwork atlas';document.querySelector('#validation').hidden=current.provider!=='original_game';document.querySelector('.help').textContent='Drag to pan · Scroll to zoom · 1 for actual pixels · F to fit'+(current.provider==='original_game'?' · Double-click for live view':'');loaded.clear();failures=0;available=new Set(current.tiles.map(t=>t.join('_')));overview=new Image();overview.onload=request;overview.src=`level-${current.level}/overview.jpg?v=${current.content_revision||0}`;document.querySelector('#download').href=`level-${current.level}/full-resolution.png?v=${current.content_revision||0}`;document.querySelector("#download").textContent="Full-resolution PNG ↓";fit()}
function tile(tx,ty){const key=`${tx}_${ty}`;if(!available.has(key))return null;if(!loaded.has(key)){const im=new Image();im.onload=request;im.onerror=()=>{failures++;request()};im.src=`level-${current.level}/tiles/${key}.png?v=${current.content_revision||0}`;loaded.set(key,im);if(loaded.size>240){const first=loaded.keys().next().value;if(first!==key)loaded.delete(first)}}return loaded.get(key)}
function draw(){raf=0;ctx.fillStyle='#080d0c';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.imageSmoothingEnabled=scale<1;if(overview?.complete&&overview.naturalWidth)ctx.drawImage(overview,ox,oy,current.width*scale,current.height*scale);if(scale>.095){const n=current.tile_size;let x0=Math.max(0,Math.floor(-ox/scale/n)),y0=Math.max(0,Math.floor(-oy/scale/n)),x1=Math.min(Math.ceil(current.width/n),Math.ceil((canvas.width-ox)/scale/n)),y1=Math.min(Math.ceil(current.height/n),Math.ceil((canvas.height-oy)/scale/n));for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){const im=tile(x,y);if(im?.complete&&im.naturalWidth)ctx.drawImage(im,ox+x*n*scale,oy+y*n*scale,im.naturalWidth*scale,im.naturalHeight*scale)}}status.textContent=`${current.width.toLocaleString()} × ${current.height.toLocaleString()} native pixels · ${(scale*100).toFixed(scale<.1?1:0)}% · ${(current.statistics.rendered_objects??current.statistics.source_objects??0).toLocaleString()} source objects${(current.static_boundary_pixels_requiring_review??current.quilted_seams_requiring_review??current.unresolved_seams)?' · '+(current.static_boundary_pixels_requiring_review??current.quilted_seams_requiring_review??current.unresolved_seams)+' seam comparisons require review':''}${failures?' · '+failures+' tile load errors':''}`}
function zoom(f,x=canvas.width/2,y=canvas.height/2){const ns=Math.max(.002,Math.min(8,scale*f));ox=x-(x-ox)*ns/scale;oy=y-(y-oy)*ns/scale;scale=ns;request()}
canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect();zoom(Math.exp(-e.deltaY*.0015),e.clientX-r.left,e.clientY-r.top)},{passive:false});
canvas.addEventListener('pointerdown',e=>{drag={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);canvas.classList.add('dragging')});canvas.addEventListener('pointermove',e=>{if(!drag)return;ox+=e.clientX-drag.x;oy+=e.clientY-drag.y;drag={x:e.clientX,y:e.clientY};request()});canvas.addEventListener('pointerup',()=>{drag=null;canvas.classList.remove('dragging')});
canvas.addEventListener('dblclick',e=>{if(current.provider!=='original_game')return;const r=canvas.getBoundingClientRect(),sx=(e.clientX-r.left-ox)/scale+current.bounds[0],sy=(e.clientY-r.top-oy)/scale+current.bounds[1],q=new URLSearchParams({level:current.level,x:Math.round(sy+sx/2),y:Math.round(sy-sx/2),z:0});window.open('http://127.0.0.1:8766/?'+q,'revenant-live')});
select.addEventListener('change',change);document.querySelector('#fit').onclick=fit;document.querySelector('#plus').onclick=()=>zoom(2);document.querySelector('#minus').onclick=()=>zoom(.5);window.addEventListener('resize',resize);window.addEventListener('keydown',e=>{if(e.target===select)return;if(e.key.toLowerCase()==='f')fit();else if(e.key==='1')zoom(1/scale);else if(e.key==='+')zoom(2);else if(e.key==='-')zoom(.5)});
resize();if(MAPS.length){select.value=MAPS.some(m=>m.level===0)?0:MAPS[0].level;change()}else status.textContent='No rendered maps found';
</script></html>'''

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path,nargs='?',default=Path(__file__).parent/'output');a=p.parse_args()
    maps=[]
    for f in a.directory.glob('level-*/manifest.json'):
        m=json.loads(f.read_text())
        validation=f.parent/'validation.json'
        if validation.exists():
            report=json.loads(validation.read_text())
            m['content_revision']=report.get('full_png_sha256',str(f.stat().st_mtime_ns))[:16]
        if 'tiles'not in m:m['tiles']=[list(map(int,t.stem.split('_')))for t in (f.parent/'tiles').glob('*.png')]
        maps.append(m)
    maps.sort(key=lambda m:m['level'])
    if maps and all(m.get('provider')=='original_game'for m in maps):
        (a.directory/'atlas.json').write_text(json.dumps({'provider':'original_game','levels':maps},indent=2)+'\n')
    (a.directory/'index.html').write_text(HTML.replace('__MAPS__',json.dumps(maps).replace('</','<\\/')))
    print(f'{len(maps)} maps: {a.directory/"index.html"}')
if __name__=='__main__':main()
