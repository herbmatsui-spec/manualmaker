from js import Response

async def on_request(request):
    return Response('Hello World', status=200)
