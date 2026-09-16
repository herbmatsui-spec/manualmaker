from js import Response
from datetime import datetime

def on_request(request):
    return Response(f"Current time: {datetime.now()}")
