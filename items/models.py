from django.db import models

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

# -- Categories table
# CREATE TABLE categories (
#     id SERIAL PRIMARY KEY,
#     name VARCHAR(255) NOT NULL
#     parent_category_id INT REFERENCES categories(id) ON DELETE CASCADE
# );

# -- Items table (basic item information)
# CREATE TABLE items (
#     id SERIAL PRIMARY KEY,
#     name VARCHAR(255) NOT NULL,
#     price DECIMAL(10, 2) NOT NULL,
#     description TEXT
#     -- Note: Removed category_id to avoid conflict with many-to-many relationship
# );

# -- Junction table for many-to-many relationship between items and categories
# CREATE TABLE item_categories (
#     item_id INT NOT NULL,
#     category_id INT NOT NULL,
#     PRIMARY KEY (item_id, category_id),
#     FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
#     FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
# );

# -- Item details table (one-to-one with items, for additional details like color)
# CREATE TABLE details (
#     id SERIAL PRIMARY KEY,
#     item_id INT NOT NULL UNIQUE,  -- Ensures one-to-one relationship
#     color VARCHAR(255) NOT NULL,
#     detail TEXT,  -- Optional additional details
#     FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
# );

# -- Item sizes table (one-to-many with items, for sizes and their quantities)
# CREATE TABLE sizes (
#     id SERIAL PRIMARY KEY,
#     item_id INT NOT NULL,
#     size VARCHAR(50) NOT NULL,  -- e.g., 'S', 'M', 'L'
#     quantity INT NOT NULL,  -- Stock for this specific size
#     FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
# );

# -- Item images table (one-to-many with items, for images of different qualities)
# CREATE TABLE images (
#     id SERIAL PRIMARY KEY,
#     item_id INT NOT NULL,
#     image_url VARCHAR(255) NOT NULL,  -- URL to externally stored image
#     quality VARCHAR(10) NOT NULL,  -- 'low', 'medium', 'high'
#     is_primary BOOLEAN DEFAULT FALSE,  -- Marks the main image for display
#     FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
# );

class Category(BaseModel):
    name = models.CharField(max_length=255) # Corresponds to VARCHAR(255) NOT NULL
    parent_category = models.ForeignKey(
        'self',
        on_delete=models.CASCADE, # Or models.SET_NULL if you want subcategories to remain if parent is deleted
        null=True,
        blank=True,
        related_name='subcategories',
        db_constraint=False
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ('name', 'parent_category') # Optional: Ensure unique category names under the same parent
        db_table = 'categories' # Match SQL comment

class Item(BaseModel):
    name = models.CharField(max_length=255) # Corresponds to VARCHAR(255) NOT NULL
    price = models.DecimalField(max_digits=10, decimal_places=2) # Corresponds to DECIMAL(10, 2) NOT NULL
    description = models.TextField(blank=True, null=True) # Corresponds to TEXT (nullable)
    categories = models.ManyToManyField(
        Category,
        through='ItemCategory',
        related_name='items'
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'items' # Match SQL comment

class ItemCategory(BaseModel): # Through model for Item <-> Category
    item = models.ForeignKey(Item, on_delete=models.CASCADE, db_constraint=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, db_constraint=False)

    class Meta:
        unique_together = ('item', 'category') # Corresponds to PRIMARY KEY (item_id, category_id)
        db_table = 'item_categories' # Explicitly name the junction table as in SQL
        verbose_name_plural = "Item Categories"
        
    def __str__(self):
        return f"{self.item.name} - {self.category.name}"

class ItemDetail(BaseModel): # One-to-one with Item
    item = models.OneToOneField(
        Item,
        on_delete=models.CASCADE,
        related_name='details',
        db_constraint=False # User request
    ) # UNIQUE constraint is inherent
    color = models.CharField(max_length=255) # Corresponds to VARCHAR(255) NOT NULL
    detail = models.TextField(blank=True, null=True) # Corresponds to TEXT (nullable)

    def __str__(self):
        return f"{self.item.name} - Details"

    class Meta:
        db_table = 'details' # Match SQL comment

class ItemSize(BaseModel): # One-to-many with Item
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='sizes',
        db_constraint=False # User request
    )
    size = models.CharField(max_length=50) # Corresponds to VARCHAR(50) NOT NULL
    quantity = models.IntegerField() # Corresponds to INT NOT NULL

    def __str__(self):
        return f"{self.item.name} - Size: {self.size} (Qty: {self.quantity})"

    class Meta:
        unique_together = ('item', 'size') # Ensure an item doesn't have duplicate sizes
        verbose_name_plural = "Item Sizes"
        db_table = 'sizes' # Match SQL comment

class ItemImage(BaseModel): # One-to-many with Item
    item = models.ForeignKey(
        Item,
        on_delete=models.CASCADE,
        related_name='images',
        db_constraint=False # User request
    )
    image_url = models.URLField(max_length=255) # Corresponds to VARCHAR(255) NOT NULL
    QUALITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    quality = models.CharField(
        max_length=10,
        choices=QUALITY_CHOICES,
        # NOT NULL is default for CharField
    )
    is_primary = models.BooleanField(default=False) # Corresponds to BOOLEAN DEFAULT FALSE

    def __str__(self):
        return f"{self.item.name} - {self.get_quality_display()} Image"

    class Meta:
        verbose_name_plural = "Item Images"
        db_table = 'images' # Match SQL comment