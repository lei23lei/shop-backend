from django.urls import path
from .views import ItemView

urlpatterns = [
    path('items/', ItemView.as_view(), name='items'),
]