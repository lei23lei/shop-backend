from rest_framework import serializers
from .models import Item, Category, ItemCategory, ItemImage, ItemDetail, ItemSize

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['name']

class ItemImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemImage
        fields = ['id', 'image_url', 'is_primary']

class ItemSerializer(serializers.ModelSerializer):
    categories = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    
    class Meta:
        model = Item
        fields = ['id', 'name', 'price', 'description', 'categories', 'image', 'created_at']
    
    def get_categories(self, obj):
        return [category.name for category in obj.categories.all()]
    
    def get_image(self, obj):
        # Get only the first low quality image
        low_image = obj.images.filter(quality='low').first()
        return low_image.image_url if low_image else None

class RecentItemSerializer(serializers.ModelSerializer):
    low_quality_image = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = ['id', 'name', 'price', 'description', 'low_quality_image']
    
    def get_low_quality_image(self, obj):
        low_image = obj.images.filter(quality='low').first()
        return low_image.image_url if low_image else None
    
    
    