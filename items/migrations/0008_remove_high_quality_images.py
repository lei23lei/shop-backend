from django.db import migrations

def remove_high_quality_images(apps, schema_editor):
    ItemImage = apps.get_model('items', 'ItemImage')
    # Delete all high quality images
    ItemImage.objects.filter(quality='high').delete()

def reverse_migration(apps, schema_editor):
    # Cannot restore deleted images
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('items', '0007_add_furniture_category'),
    ]

    operations = [
        migrations.RunPython(remove_high_quality_images, reverse_migration),
    ] 