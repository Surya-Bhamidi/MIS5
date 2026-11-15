"""Small local-service boundary: bounded bodies and no reflected rejected values."""
import asyncio
import ipaddress
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

LOCAL_ORIGINS=tuple(f'http://{host}:{port}' for host in ('127.0.0.1','localhost') for port in (5173,8000,8001))
MAX_BODY_BYTES=2*1024*1024


async def validation_response(request,error: RequestValidationError):
    # The default error input can contain secrets or non-finite JSON numbers.
    # Return only locations and fixed schema messages, never rejected values.
    return JSONResponse(status_code=422,content={'detail':[
        {key:item[key] for key in ('loc','msg','type') if key in item} for item in error.errors()]})


class LocalRequestGuard:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or not scope['path'].startswith('/api'):
            return await self.app(scope,receive,send)
        try:
            address=ipaddress.ip_address(scope.get('client',('',''))[0])
            local=address.is_loopback or bool(getattr(address,'ipv4_mapped',None) and address.ipv4_mapped.is_loopback)
        except (ValueError,TypeError):local=False
        if not local:
            return await JSONResponse({'detail':'This research API accepts loopback clients only'},status_code=403)(scope,receive,send)
        headers={}
        for name,value in scope.get('headers',[]):
            name=name.lower()
            if name in (b'origin',b'content-length') and name in headers:
                return await JSONResponse({'detail':'Ambiguous request headers'},status_code=400)(scope,receive,send)
            headers[name]=value
        if b'origin' in headers and headers[b'origin'].decode('latin-1') not in LOCAL_ORIGINS:
            return await JSONResponse({'detail':'Browser origin is not allowed'},status_code=403)(scope,receive,send)
        if b'origin' not in headers and headers.get(b'sec-fetch-site')==b'cross-site':
            return await JSONResponse({'detail':'Cross-site browser requests are not allowed'},status_code=403)(scope,receive,send)
        if scope['method'] not in ('POST','PUT','PATCH','DELETE'):
            return await self.app(scope,receive,send)
        declared=headers.get(b'content-length')
        if declared is not None:
            if not declared.isdigit() or b'transfer-encoding' in headers:
                return await JSONResponse({'detail':'Invalid request length headers'},status_code=400)(scope,receive,send)
            if len(declared)>10 or int(declared)>MAX_BODY_BYTES:
                return await JSONResponse({'detail':'Request body is too large'},status_code=413)(scope,receive,send)
        body=bytearray()
        try:
            async with asyncio.timeout(10):
                while True:
                    message=await receive()
                    if message['type']=='http.disconnect':return
                    body.extend(message.get('body',b''))
                    if len(body)>MAX_BODY_BYTES:
                        return await JSONResponse({'detail':'Request body is too large'},status_code=413)(scope,receive,send)
                    if not message.get('more_body',False):break
        except TimeoutError:
            return await JSONResponse({'detail':'Request body timed out'},status_code=408)(scope,receive,send)
        if declared is not None and len(body)!=int(declared):
            return await JSONResponse({'detail':'Request length does not match body'},status_code=400)(scope,receive,send)
        used=False
        async def buffered_receive():
            nonlocal used
            if not used:
                used=True
                return {'type':'http.request','body':bytes(body),'more_body':False}
            return await receive()
        await self.app(scope,buffered_receive,send)
