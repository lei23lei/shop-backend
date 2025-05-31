from django.db import migrations

def add_furniture_category(apps, schema_editor):
    Category = apps.get_model('items', 'Category')
    # Add furniture as subcategory of 'Other' (id=4)
    Category.objects.create(
        name='furniture',
        parent_category_id=4
    )

def remove_furniture_category(apps, schema_editor):
    Category = apps.get_model('items', 'Category')
    Category.objects.filter(name='furniture').delete()

class Migration(migrations.Migration):
    dependencies = [
        ('items', '0006_update_item_images'),
    ]

    operations = [
        migrations.RunPython(add_furniture_category, remove_furniture_category),
    ] 