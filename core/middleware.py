from django.http import HttpResponse

HEALTH_PATH = "/healthz"


class HealthCheckMiddleware:
    """Responde ``/healthz`` para a sonda do contêiner.

    A sonda chega por ``localhost`` em HTTP puro, então precisa ser atendida
    antes de ``ALLOWED_HOSTS`` e do redirecionamento para HTTPS.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH:
            return HttpResponse("ok", content_type="text/plain")
        return self.get_response(request)
