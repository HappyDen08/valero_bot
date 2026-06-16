from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

admin.site.site_header = "Veloro — службова адмінка"
admin.site.site_title = "Veloro"

urlpatterns = [
    path("", include("panel.urls")),
    path("django-admin/", admin.site.urls),
    # фото заявок переглядають лише кілька адмінів — віддаємо медіа через Django
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]
