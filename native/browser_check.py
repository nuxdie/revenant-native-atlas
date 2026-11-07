"""Exercise the local viewer using a disposable Chrome debugging session."""
import asyncio
import base64
import json
from pathlib import Path
import urllib.request
import websockets

async def main():
    request=urllib.request.Request('http://127.0.0.1:9337/json/new?http://127.0.0.1:8766',method='PUT')
    target=json.load(urllib.request.urlopen(request,timeout=3))
    async with websockets.connect(target['webSocketDebuggerUrl'],max_size=10*1024**2) as ws:
        sequence=0
        async def call(method,params=None):
            nonlocal sequence
            sequence+=1;ident=sequence
            await ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
            while True:
                message=json.loads(await ws.recv())
                if message.get('id')==ident:
                    if 'error'in message:raise RuntimeError(message)
                    return message.get('result',{})
        await call('Page.enable')
        await call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
        await asyncio.sleep(2)
        result=await call('Runtime.evaluate',{'expression':"JSON.stringify({status:document.querySelector('#status')?.textContent,levels:document.querySelectorAll('#level option').length,canvas:document.querySelector('canvas')?.width})",'returnByValue':True})
        print(result['result']['value'])
        screenshot=await call('Page.captureScreenshot',{'format':'png'})
        Path('comparisons/live-browser.png').write_bytes(base64.b64decode(screenshot['data']))
        await call('Page.close')

if __name__=='__main__':asyncio.run(main())
