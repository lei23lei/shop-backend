from django.core.management.base import BaseCommand
from items.models import Category

class Command(BaseCommand):
    help = 'Insert initial categories and subcategories'

    def handle(self, *args, **kwargs):
        # Create main categories
        men = Category.objects.create(name='men')
        women = Category.objects.create(name='women')
        food = Category.objects.create(name='food')
        others = Category.objects.create(name='others')

        # Create subcategories for men
        Category.objects.create(name='top', parent_category=men)
        Category.objects.create(name='bottom', parent_category=men)
        Category.objects.create(name='shoes', parent_category=men)

        # Create subcategories for women
        Category.objects.create(name='top', parent_category=women)
        Category.objects.create(name='bottom', parent_category=women)
        Category.objects.create(name='shoes', parent_category=women)

        # Create subcategories for food
        Category.objects.create(name='drink', parent_category=food)
        Category.objects.create(name='eat', parent_category=food)

        # Create subcategories for others
        Category.objects.create(name='furniture', parent_category=others)
        Category.objects.create(name='Electronics', parent_category=others)

        self.stdout.write(self.style.SUCCESS('Successfully inserted all categories')) 