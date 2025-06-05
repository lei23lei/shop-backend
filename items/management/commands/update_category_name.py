from django.core.management.base import BaseCommand
from items.models import Category

class Command(BaseCommand):
    help = 'Update the name of the Electronics category to electronics'

    def handle(self, *args, **kwargs):
        try:
            # Find the category with name 'Electronics' under 'others'
            others = Category.objects.get(name='others')
            electronics = Category.objects.get(name='Electronics', parent_category=others)
            
            # Update the name
            electronics.name = 'electronics'
            electronics.save()
            
            self.stdout.write(self.style.SUCCESS('Successfully updated category name from "Electronics" to "electronics"'))
        except Category.DoesNotExist:
            self.stdout.write(self.style.ERROR('Could not find the category to update')) 