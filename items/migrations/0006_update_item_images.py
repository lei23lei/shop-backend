from django.db import migrations

def update_images(apps, schema_editor):
    Item = apps.get_model('items', 'Item')
    ItemImage = apps.get_model('items', 'ItemImage')
    
    # First, delete all existing images
    ItemImage.objects.all().delete()
    
    # Helper function to create image sets for an item
    def create_image_set(item, img_letter):
        qualities = [
            ('high', '1200/900', True if img_letter == 'A' else False),
            ('medium', '800/600', False),
            ('low', '400/300', False)
        ]
        for quality, dimensions, is_primary in qualities:
            ItemImage.objects.create(
                item=item,
                image_url=f'https://picsum.photos/seed/item{item.id}-img{img_letter}-{quality}/{dimensions}',
                quality=quality,
                is_primary=is_primary
            )

    # Create 12 images for each item (4 sets of 3 qualities each)
    for item_id in range(1, 25):  # Items 1-24
        item = Item.objects.get(id=item_id)
        for letter in ['A', 'B', 'C', 'D']:
            create_image_set(item, letter)

def reverse_images(apps, schema_editor):
    ItemImage = apps.get_model('items', 'ItemImage')
    ItemImage.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('items', '0005_insert_item_details_sizes_images'),
    ]

    operations = [
        migrations.RunPython(update_images, reverse_images),
    ] 