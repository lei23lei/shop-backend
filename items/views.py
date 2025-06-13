from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Prefetch
from .models import Item, Category, ItemImage, ItemDetail, ItemSize, DetailImage
from .serializers import ItemSerializer
from django.db import transaction
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny

# Create your views here.
class CustomPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

class ItemView(APIView):
    permission_classes = [AllowAny]  # Allow public access to browse items
    pagination_class = CustomPagination

    def get_all_subcategories(self, category_ids):
        """
        Recursively get all subcategories for given category IDs
        """
        all_categories = set(category_ids)
        to_process = list(category_ids)
        
        while to_process:
            current_ids = to_process
            # Find all direct children of current categories
            subcategories = Category.objects.filter(parent_category_id__in=current_ids)
            to_process = []
            
            for subcat in subcategories:
                if subcat.id not in all_categories:
                    all_categories.add(subcat.id)
                    to_process.append(subcat.id)
                    
        return list(all_categories)

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

        # Category filter with subcategories support
        category_ids = request.query_params.getlist('category')
        if category_ids:
            try:
                # Convert string IDs to integers
                category_ids = [int(cid) for cid in category_ids]
                # Get all subcategories including the original categories
                all_category_ids = self.get_all_subcategories(category_ids)
                queryset = queryset.filter(categories__id__in=all_category_ids).distinct()
            except ValueError:
                pass  # Invalid category ID format, ignore filter

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

    def post(self, request):
        # Check if user is authenticated for creating items
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required to create items'},
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        try:
            # Start a transaction to ensure all related data is created or none
            with transaction.atomic():
                # 1. Create the main item
                item = Item.objects.create(
                    name=request.data['name'],
                    price=request.data['price'],
                    description=request.data['description']
                )

                # 2. Create item details (one-to-one)
                ItemDetail.objects.create(
                    item=item,
                    color=request.data['color'],
                    detail=request.data['detail']
                )

                # 3. Create sizes (one-to-many)
                for size_data in request.data['sizes']:
                    ItemSize.objects.create(
                        item=item,
                        size=size_data['size'],
                        quantity=size_data['quantity']
                    )

                # 4. Create images
                # Create display image (low quality, primary)
                if 'displayImage' in request.data:
                    ItemImage.objects.create(
                        item=item,
                        image_url=request.data['displayImage'],
                        quality='low',
                        is_primary=True
                    )

                # Create other images (medium quality)
                for image_url in request.data['images']:
                    ItemImage.objects.create(
                        item=item,
                        image_url=image_url,
                        quality='medium',
                        is_primary=False
                    )

                # Create detail images if any
                for idx, image_url in enumerate(request.data.get('detailImages', [])):
                    DetailImage.objects.create(
                        item=item,
                        image_url=image_url,
                        display_order=idx
                    )

                # 5. Add categories (many-to-many)
                item.categories.add(*request.data['categories'])

                # 6. Return the created item data
                response_data = {
                    'id': item.id,
                    'name': item.name,
                    'price': str(item.price),
                    'description': item.description,
                    'categories': list(item.categories.values('id', 'name')),
                    'details': {
                        'color': request.data['color'],
                        'detail': request.data['detail']
                    },
                    'sizes': request.data['sizes'],
                    'images': [
                        {
                            'image_url': img.image_url,
                            'is_primary': img.is_primary,
                            'quality': img.quality
                        }
                        for img in item.images.all()
                    ],
                    'detail_images': [
                        {
                            'image_url': img.image_url,
                            'display_order': img.display_order
                        }
                        for img in item.detail_images.all()
                    ]
                }

                return Response(response_data, status=status.HTTP_201_CREATED)

        except KeyError as e:
            return Response(
                {'error': f'Missing required field: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ItemDetailView(APIView):
    permission_classes = [AllowAny]  # Allow public access to view item details

    def get(self, request, item_id):
        try:
            # Get item with all related data in a single query
            item = Item.objects.prefetch_related(
                'details',
                'sizes',
                Prefetch(
                    'images',
                    queryset=ItemImage.objects.filter(quality='medium')
                ),
                'detail_images',
                'categories'
            ).get(id=item_id)

            # Serialize the data
            data = {
                'id': item.id,
                'name': item.name,
                'price': str(item.price),
                'description': item.description,
                'created_at': item.created_at,
                'updated_at': item.updated_at,
                
                # Get categories
                'categories': [
                    {'id': cat.id, 'name': cat.name}
                    for cat in item.categories.all()
                ],
                
                # Get details (one-to-one)
                'details': {
                    'color': item.details.color,
                    'detail': item.details.detail
                } if hasattr(item, 'details') else None,
                
                # Get sizes (one-to-many) with their IDs and quantities
                'sizes': [
                    {
                        'id': size.id,  # Added size ID for cart operations
                        'size': size.size,
                        'quantity': size.quantity
                    }
                    for size in item.sizes.all()
                ],
                
                # Get medium quality images
                'images': [
                    {
                        'id': img.id,
                        'image_url': img.image_url,
                        'is_primary': img.is_primary
                    }
                    for img in item.images.all()
                ],
                
                # Get detail images
                'detail_images': [
                    {
                        'id': img.id,
                        'image_url': img.image_url,
                        'display_order': img.display_order
                    }
                    for img in item.detail_images.all()
                ]
            }
            
            return Response(data)
            
        except Item.DoesNotExist:
            return Response(
                {'error': 'Item not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, item_id):
        """
        Delete an item and all its related data
        """
        try:
            # Start a transaction to ensure all related data is deleted or none
            with transaction.atomic():
                # Get the item
                item = Item.objects.get(id=item_id)
                
                # Store item name for response
                item_name = item.name
                
                # Delete the item (this will cascade delete all related data due to CASCADE in models)
                item.delete()
                
                return Response(
                    {'message': f'Item "{item_name}" has been successfully deleted'},
                    status=status.HTTP_200_OK
                )
                
        except Item.DoesNotExist:
            return Response(
                {'error': 'Item not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminItemView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def check_admin_permission(self, request):
        """Check if the user is a superuser"""
        if not request.user.is_superuser:
            return Response(
                {"error": "Only administrators can perform this action"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return None
    
    def get(self, request, item_id=None):
        """Get item details for admin (with all image qualities)"""
        # Check admin permission
        permission_check = self.check_admin_permission(request)
        if permission_check:
            return permission_check
            
        try:
            if item_id:
                # Get specific item
                item = Item.objects.prefetch_related(
                    'details',
                    'sizes',
                    'images',
                    'detail_images',
                    'categories'
                ).get(id=item_id)
                
                # Format single item response
                data = {
                    'id': item.id,
                    'name': item.name,
                    'price': str(item.price),
                    'description': item.description,
                    'created_at': item.created_at,
                    'updated_at': item.updated_at,
                    'categories': [
                        {'id': cat.id, 'name': cat.name}
                        for cat in item.categories.all()
                    ],
                    'details': {
                        'color': item.details.color,
                        'detail': item.details.detail
                    } if hasattr(item, 'details') else None,
                    'sizes': [
                        {
                            'id': size.id,
                            'size': size.size,
                            'quantity': size.quantity
                        }
                        for size in item.sizes.all()
                    ],
                    'images': [
                        {
                            'id': img.id,
                            'image_url': img.image_url,
                            'quality': img.quality,
                            'is_primary': img.is_primary
                        }
                        for img in item.images.all()
                    ],
                    'detail_images': [
                        {
                            'id': img.id,
                            'image_url': img.image_url,
                            'display_order': img.display_order
                        }
                        for img in item.detail_images.all()
                    ]
                }
                return Response(data)
            else:
                # Get all items with pagination
                items = Item.objects.prefetch_related(
                    'details',
                    'sizes',
                    'images',
                    'detail_images',
                    'categories'
                ).all()
                
                paginator = CustomPagination()
                paginated_items = paginator.paginate_queryset(items, request)
                
                items_data = []
                for item in paginated_items:
                    items_data.append({
                        'id': item.id,
                        'name': item.name,
                        'price': str(item.price),
                        'description': item.description,
                        'created_at': item.created_at,
                        'updated_at': item.updated_at,
                        'categories': [
                            {'id': cat.id, 'name': cat.name}
                            for cat in item.categories.all()
                        ],
                        'details': {
                            'color': item.details.color,
                            'detail': item.details.detail
                        } if hasattr(item, 'details') else None,
                        'sizes': [
                            {
                                'id': size.id,
                                'size': size.size,
                                'quantity': size.quantity
                            }
                            for size in item.sizes.all()
                        ],
                        'total_images': item.images.count(),
                        'total_detail_images': item.detail_images.count()
                    })
                
                return paginator.get_paginated_response({
                    'items': items_data,
                    'total_items': items.count()
                })
                
        except Item.DoesNotExist:
            return Response(
                {'error': 'Item not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def put(self, request, item_id):
        """Update an item's details"""
        # Check admin permission
        permission_check = self.check_admin_permission(request)
        if permission_check:
            return permission_check
            
        try:
            with transaction.atomic():
                # Get the item
                item = Item.objects.get(id=item_id)
                data = request.data
                
                # Update basic item info
                if 'name' in data:
                    item.name = data['name']
                if 'price' in data:
                    item.price = data['price']
                if 'description' in data:
                    item.description = data['description']
                item.save()
                
                # Update details
                if 'color' in data or 'detail' in data:
                    details, _ = ItemDetail.objects.get_or_create(item=item)
                    if 'color' in data:
                        details.color = data['color']
                    if 'detail' in data:
                        details.detail = data['detail']
                    details.save()
                
                # Update sizes
                if 'sizes' in data:
                    # Delete existing sizes
                    item.sizes.all().delete()
                    # Create new sizes
                    for size_data in data['sizes']:
                        ItemSize.objects.create(
                            item=item,
                            size=size_data['size'],
                            quantity=size_data['quantity']
                        )
                
                # Update categories
                if 'categories' in data:
                    item.categories.clear()
                    item.categories.add(*data['categories'])
                
                # Update images
                if 'images' in data:
                    # Delete existing images
                    item.images.all().delete()
                    # Create new images
                    for image_data in data['images']:
                        ItemImage.objects.create(
                            item=item,
                            image_url=image_data['image_url'],
                            quality=image_data.get('quality', 'medium'),
                            is_primary=image_data.get('is_primary', False)
                        )
                
                # Update detail images
                if 'detail_images' in data:
                    # Delete existing detail images
                    item.detail_images.all().delete()
                    # Create new detail images
                    for idx, image_data in enumerate(data['detail_images']):
                        DetailImage.objects.create(
                            item=item,
                            image_url=image_data['image_url'],
                            display_order=image_data.get('display_order', idx)
                        )
                
                return Response({
                    'message': 'Item updated successfully',
                    'item_id': item.id
                }, status=status.HTTP_200_OK)
                
        except Item.DoesNotExist:
            return Response(
                {'error': 'Item not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def delete(self, request, item_id):
        """Delete an item and all its related data"""
        # Check admin permission
        permission_check = self.check_admin_permission(request)
        if permission_check:
            return permission_check
            
        try:
            with transaction.atomic():
                item = Item.objects.get(id=item_id)
                item_name = item.name
                item.delete()
                
                return Response({
                    'message': f'Item "{item_name}" has been successfully deleted'
                }, status=status.HTTP_200_OK)
                
        except Item.DoesNotExist:
            return Response(
                {'error': 'Item not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) 