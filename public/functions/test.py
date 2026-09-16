from js import Response

def on_request(request):
    return Response('hello', status=200)
