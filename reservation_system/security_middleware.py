"""django.middleware.security.SecurityMiddleware の拡張（静的 IP 等は HTTP のまま許可）"""

from django.conf import settings
from django.middleware.security import SecurityMiddleware as DjangoSecurityMiddleware


class SecurityMiddleware(DjangoSecurityMiddleware):
    def process_request(self, request):
        exempt_hosts = getattr(settings, "SECURE_SSL_REDIRECT_EXEMPT_HOSTS", ())
        if exempt_hosts:
            host = request.get_host().split(":")[0]
            if (
                self.redirect
                and not request.is_secure()
                and host in exempt_hosts
            ):
                return None
        return super().process_request(request)
