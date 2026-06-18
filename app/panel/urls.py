from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "panel"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="panel/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="panel:login"), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("participants/", views.participants, name="participants"),
    path("participants/export/", views.participants_export, name="participants_export"),
    path("sales/", views.sales, name="sales"),
    path("sales/export/", views.sales_export, name="sales_export"),
    path("sales/<int:pk>/", views.sale_detail, name="sale_detail"),
    path("tickets/", views.tickets, name="tickets"),
    path("tickets/export/", views.tickets_export, name="tickets_export"),
    path("rating/", views.rating, name="rating"),
    path("broadcasts/", views.broadcasts, name="broadcasts"),
    path("draws/", views.draws, name="draws"),
    path("draws/ceremony/", views.draw_ceremony, name="draw_ceremony"),
    path("draws/perform/", views.draw_perform, name="draw_perform"),
]
