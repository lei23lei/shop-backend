from django.urls import path
from .views import ItemView, ItemDetailView

urlpatterns = [
    path('items/', ItemView.as_view(), name='items'),
    path('items/<int:item_id>/', ItemDetailView.as_view(), name='item-detail'),
    
]