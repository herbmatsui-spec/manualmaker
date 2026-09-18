from js import Response

async def on_request(request):
    return Response('{"status":"ok"}', status=200, headers={'Content-Type': 'application/json'})
