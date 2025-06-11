from django.urls import path
from .views import ItemView, ItemDetailView, AdminItemView

urlpatterns = [
    path('items/', ItemView.as_view(), name='items'),
    path('items/<int:item_id>/', ItemDetailView.as_view(), name='item-detail'),
    path('admin/items/', AdminItemView.as_view(), name='admin-items'),
    path('admin/items/<int:item_id>/', AdminItemView.as_view(), name='admin-item-detail'),
]