from django.db import migrations

def insert_additional_data(apps, schema_editor):
    Item = apps.get_model('items', 'Item')
    ItemDetail = apps.get_model('items', 'ItemDetail')
    ItemSize = apps.get_model('items', 'ItemSize')
    ItemImage = apps.get_model('items', 'ItemImage')

    # Insert details
    details_data = [
        {'item_id': 1, 'color': 'White', 'detail': '100% cotton'},
        {'item_id': 2, 'color': 'Blue', 'detail': 'Moisture-wicking fabric'},
        {'item_id': 3, 'color': 'Red/Black', 'detail': 'Brushed flannel interior'},
        {'item_id': 4, 'color': 'Blue', 'detail': 'Stretch denim'},
        {'item_id': 5, 'color': 'Khaki', 'detail': 'Wrinkle-resistant'},
        {'item_id': 6, 'color': 'Olive', 'detail': 'Multiple cargo pockets'},
        {'item_id': 7, 'color': 'Black/Red', 'detail': 'Cushioned insole'},
        {'item_id': 8, 'color': 'Brown', 'detail': 'Steel toe'},
        {'item_id': 9, 'color': 'Black', 'detail': 'Tassel detail'},
        {'item_id': 10, 'color': 'Floral White', 'detail': 'V-neck design'},
        {'item_id': 11, 'color': 'Pink', 'detail': 'Racerback style'},
        {'item_id': 12, 'color': 'Cream', 'detail': 'V-neck cable knit'},
        {'item_id': 13, 'color': 'Black', 'detail': 'High-waist fit'},
        {'item_id': 14, 'color': 'Yellow Floral', 'detail': 'A-line silhouette'},
        {'item_id': 15, 'color': 'Charcoal', 'detail': 'Side phone pocket'},
        {'item_id': 16, 'color': 'Silver', 'detail': '4-inch heel'},
        {'item_id': 17, 'color': 'Tan', 'detail': 'Adjustable straps'},
        {'item_id': 18, 'color': 'Burgundy', 'detail': 'Block heel'},
        {'item_id': 19, 'color': 'Oatmeal', 'detail': 'Gluten-free'},
        {'item_id': 20, 'color': 'Natural', 'detail': 'No added sugar'},
        {'item_id': 21, 'color': 'Clear', 'detail': 'BPA-free bottle'},
        {'item_id': 22, 'color': 'Blue', 'detail': 'Sugar-free'},
        {'item_id': 23, 'color': 'Black', 'detail': '6ft cable'},
        {'item_id': 24, 'color': 'Red', 'detail': 'Hardcover'},
    ]

    for detail_data in details_data:
        item_id = detail_data.pop('item_id')
        item = Item.objects.get(id=item_id)
        ItemDetail.objects.create(item=item, **detail_data)

    # Insert sizes
    sizes_data = [
        (1, [('S', 20), ('M', 30), ('L', 25), ('XL', 15)]),
        (2, [('S', 18), ('M', 22), ('L', 20)]),
        (3, [('M', 12), ('L', 15), ('XL', 10)]),
        (4, [('30', 8), ('32', 15), ('34', 12), ('36', 10)]),
        (5, [('30', 10), ('32', 18), ('34', 15)]),
        (6, [('S', 15), ('M', 20), ('L', 18)]),
        (7, [('8', 15), ('9', 20), ('10', 18), ('11', 12)]),
        (8, [('9', 10), ('10', 15), ('11', 12), ('12', 8)]),
        (9, [('8', 10), ('9', 15), ('10', 12)]),
        (10, [('XS', 5), ('S', 15), ('M', 20), ('L', 12)]),
        (11, [('S', 18), ('M', 22), ('L', 15)]),
        (12, [('S', 10), ('M', 15), ('L', 12)]),
        (13, [('26', 10), ('28', 15), ('30', 20)]),
        (14, [('S', 8), ('M', 12), ('L', 10)]),
        (15, [('XS', 15), ('S', 20), ('M', 25)]),
        (16, [('6', 5), ('7', 8), ('8', 10), ('9', 6)]),
        (17, [('6', 10), ('7', 15), ('8', 12)]),
        (18, [('7', 8), ('8', 10), ('9', 7)]),
        (19, [('Pack', 50)]),
        (20, [('Bag', 75)]),
        (21, [('Bottle', 100)]),
        (22, [('Can', 120)]),
        (23, [('Each', 40)]),
        (24, [('Each', 30)]),
    ]

    for item_id, sizes in sizes_data:
        item = Item.objects.get(id=item_id)
        for size, quantity in sizes:
            ItemSize.objects.create(item=item, size=size, quantity=quantity)

    # Insert images
    for item_id in range(1, 25):  # 1 to 24
        item = Item.objects.get(id=item_id)
        ItemImage.objects.create(
            item=item,
            image_url=f'https://picsum.photos/seed/item{item_id}-1/800/600',
            quality='high',
            is_primary=True
        )
        ItemImage.objects.create(
            item=item,
            image_url=f'https://picsum.photos/seed/item{item_id}-2/600/400',
            quality='medium',
            is_primary=False
        )
        ItemImage.objects.create(
            item=item,
            image_url=f'https://picsum.photos/seed/item{item_id}-3/300/200',
            quality='low',
            is_primary=False
        )

def reverse_additional_data(apps, schema_editor):
    ItemDetail = apps.get_model('items', 'ItemDetail')
    ItemSize = apps.get_model('items', 'ItemSize')
    ItemImage = apps.get_model('items', 'ItemImage')
    
    ItemDetail.objects.all().delete()
    ItemSize.objects.all().delete()
    ItemImage.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('items', '0004_merge_20250530_1709'),  # Make sure this matches your previous migration
    ]

    operations = [
        migrations.RunPython(insert_additional_data, reverse_additional_data),
    ] 