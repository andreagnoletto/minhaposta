from django.urls import path

from . import views

app_name = "loterias"

urlpatterns = [
    path("", views.index, name="index"),
    path("como-apostar/", views.legal, name="legal"),
    path("<slug:slug>/", views.detail, name="detail"),
]
