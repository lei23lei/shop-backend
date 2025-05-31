from django.db import migrations

def insert_initial_data(apps, schema_editor):
    Category = apps.get_model('items', 'Category')
    Item = apps.get_model('items', 'Item')
    ItemCategory = apps.get_model('items', 'ItemCategory')

    # Insert main categories first
    categories = {
        'Men': Category.objects.create(name='Men'),
        'Women': Category.objects.create(name='Women'),
        'Food': Category.objects.create(name='Food'),
        'Other': Category.objects.create(name='Other'),
    }

    # Insert subcategories
    subcategories = {
        'Men Top': Category.objects.create(name='Men Top', parent_category=categories['Men']),
        'Men Bottom': Category.objects.create(name='Men Bottom', parent_category=categories['Men']),
        'Men Shoes': Category.objects.create(name='Men Shoes', parent_category=categories['Men']),
        'Women Top': Category.objects.create(name='Women Top', parent_category=categories['Women']),
        'Women Bottom': Category.objects.create(name='Women Bottom', parent_category=categories['Women']),
        'Women Shoes': Category.objects.create(name='Women Shoes', parent_category=categories['Women']),
        'Eat': Category.objects.create(name='Eat', parent_category=categories['Food']),
        'Drink': Category.objects.create(name='Drink', parent_category=categories['Food']),
    }

    # Insert items and their categories
    items_data = [
        # Men Top
        {'name': 'Cotton T-Shirt', 'price': 19.99, 'description': 'Basic crew neck tee', 'category': 'Men Top'},
        {'name': 'Polo Shirt', 'price': 29.95, 'description': 'Classic fit pique polo', 'category': 'Men Top'},
        {'name': 'Flannel Shirt', 'price': 39.50, 'description': 'Warm plaid button-down', 'category': 'Men Top'},
        # Men Bottom
        {'name': 'Denim Jeans', 'price': 59.99, 'description': 'Slim fit blue jeans', 'category': 'Men Bottom'},
        {'name': 'Chino Pants', 'price': 49.95, 'description': 'Khaki casual trousers', 'category': 'Men Bottom'},
        {'name': 'Shorts', 'price': 34.99, 'description': 'Cargo shorts with pockets', 'category': 'Men Bottom'},
        # Men Shoes
        {'name': 'Running Shoes', 'price': 89.99, 'description': 'Lightweight mesh sneakers', 'category': 'Men Shoes'},
        {'name': 'Leather Boots', 'price': 129.95, 'description': 'Waterproof work boots', 'category': 'Men Shoes'},
        {'name': 'Loafers', 'price': 79.50, 'description': 'Slip-on dress shoes', 'category': 'Men Shoes'},
        # Women Top
        {'name': 'Blouse', 'price': 34.99, 'description': 'Silky floral top', 'category': 'Women Top'},
        {'name': 'Tank Top', 'price': 22.50, 'description': 'Sleeveless summer top', 'category': 'Women Top'},
        {'name': 'Sweater', 'price': 45.95, 'description': 'Knit cashmere sweater', 'category': 'Women Top'},
        # Women Bottom
        {'name': 'Skinny Jeans', 'price': 64.99, 'description': 'Stretch denim jeans', 'category': 'Women Bottom'},
        {'name': 'Summer Skirt', 'price': 39.95, 'description': 'Floral print midi skirt', 'category': 'Women Bottom'},
        {'name': 'Leggings', 'price': 29.99, 'description': 'Yoga pants with pocket', 'category': 'Women Bottom'},
        # Women Shoes
        {'name': 'High Heels', 'price': 79.99, 'description': 'Stiletto pumps', 'category': 'Women Shoes'},
        {'name': 'Sandals', 'price': 49.95, 'description': 'Leather strappy sandals', 'category': 'Women Shoes'},
        {'name': 'Ankle Boots', 'price': 89.50, 'description': 'Suede fashion boots', 'category': 'Women Shoes'},
        # Eat
        {'name': 'Granola Bars', 'price': 4.99, 'description': 'Oats & honey snack', 'category': 'Eat'},
        {'name': 'Apple Chips', 'price': 3.49, 'description': 'Dehydrated fruit snack', 'category': 'Eat'},
        # Drink
        {'name': 'Bottled Water', 'price': 1.99, 'description': '500ml spring water', 'category': 'Drink'},
        {'name': 'Energy Drink', 'price': 2.49, 'description': 'Caffeinated beverage', 'category': 'Drink'},
        # Other
        {'name': 'Phone Charger', 'price': 24.99, 'description': 'USB-C fast charger', 'category': 'Other'},
        {'name': 'Notebook', 'price': 8.95, 'description': '200-page lined journal', 'category': 'Other'},
    ]

    # Create items and their category relationships
    for item_data in items_data:
        category_name = item_data.pop('category')
        item = Item.objects.create(**item_data)
        
        if category_name in subcategories:
            category = subcategories[category_name]
        else:
            category = categories[category_name]
            
        ItemCategory.objects.create(item=item, category=category)

def reverse_initial_data(apps, schema_editor):
    Category = apps.get_model('items', 'Category')
    Item = apps.get_model('items', 'Item')
    ItemCategory = apps.get_model('items', 'ItemCategory')
    
    ItemCategory.objects.all().delete()
    Item.objects.all().delete()
    Category.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
        ('items', '0001_initial'),  # Make sure this matches your previous migration
    ]

    operations = [
        migrations.RunPython(insert_initial_data, reverse_initial_data),
    ] 