from django.core.management.base import BaseCommand
from items.models import Category

class Command(BaseCommand):
    help = 'Update the name of the accessory category to accessories'

    def handle(self, *args, **kwargs):
        try:
            # Find the 'others' category
            others = Category.objects.get(name='others')
            # Find the accessory category under others
            accessory = Category.objects.get(name='accessory', parent_category=others)
            
            # Update the name
            accessory.name = 'accessories'
            accessory.save()
            
            self.stdout.write(
                self.style.SUCCESS('Successfully updated category name from "accessory" to "accessories"')
            )
        except Category.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Could not find the category to update')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            ) 