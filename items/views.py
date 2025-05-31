from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Prefetch
from .models import Item, Category, ItemImage
from .serializers import ItemSerializer, CategorySerializer, RecentItemSerializer

# Create your views here.
class CustomPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

class ItemView(APIView):
    pagination_class = CustomPagination

    def get(self, request):
        """
        Get items with optional filtering and only low quality images
        """
        # Optimize query to only fetch low quality images
        queryset = Item.objects.prefetch_related(
            'categories',
            'sizes',
            Prefetch(
                'images',
                queryset=ItemImage.objects.filter(quality='low')
            )
        ).select_related('details').all()

        # Category filter
        category_id = request.query_params.get('category')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)

        # Search filter
        search = request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )

        # Price range filter
        min_price = request.query_params.get('min_price')
        if min_price:
            queryset = queryset.filter(price__gte=float(min_price))

        max_price = request.query_params.get('max_price')
        if max_price:
            queryset = queryset.filter(price__lte=float(max_price))

        # Sorting
        sort_field = request.query_params.get('sort', 'created_at')
        order = request.query_params.get('order', 'desc')
        
        valid_sort_fields = ['created_at', 'price', 'name']
        if sort_field not in valid_sort_fields:
            sort_field = 'created_at'
            
        if order == 'desc':
            sort_field = f'-{sort_field}'

        queryset = queryset.order_by(sort_field)

        # Pagination
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        
        serializer = ItemSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data) 