from django.core.management.base import BaseCommand
from items.models import Category

class Command(BaseCommand):
    help = 'Add accessory category under others category'

    def handle(self, *args, **kwargs):
        try:
            # Find the 'others' category
            others = Category.objects.get(name='others')
            
            # Create the accessory category
            accessory = Category.objects.create(
                name='accessory',
                parent_category=others
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully created accessory category under others (ID: {others.id})')
            )
        except Category.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Could not find the "others" category')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            ) 