from django.db import models
from django.contrib.auth.models import AbstractUser
from items.models import Item, ItemSize

# Create your models here.
# CREATE TABLE users (
#     id SERIAL PRIMARY KEY,
#     phone_number VARCHAR(20),  -- Optional phone number
#     address TEXT,  -- Optional address for orders
#     created_at TIMESTAMP NOT NULL,
#     updated_at TIMESTAMP NOT NULL
# );

# -- Password reset tokens table
# CREATE TABLE password_reset_tokens (
#     id SERIAL PRIMARY KEY,
#     user_id INT NOT NULL,
#     token VARCHAR(255) NOT NULL,
#     created_at TIMESTAMP NOT NULL,
#     expires_at TIMESTAMP NOT NULL,
#     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
# );

# -- Social accounts table (managed by django-allauth)
# CREATE TABLE social_accounts (
#     id SERIAL PRIMARY KEY,
#     user_id INT NOT NULL,
#     provider VARCHAR(50) NOT NULL,  -- e.g., 'google', 'facebook'
#     uid VARCHAR(255) NOT NULL,  -- Unique ID from the provider
#     extra_data JSONB,  -- Additional data from provider
#     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
# );

# -- Social accounts table (managed by django-allauth)
# CREATE TABLE social_accounts (
#     id SERIAL PRIMARY KEY,
#     user_id INT NOT NULL,
#     provider VARCHAR(50) NOT NULL,  -- e.g., 'google', 'facebook'
#     uid VARCHAR(255) NOT NULL,  -- Unique ID from the provider
#     extra_data JSONB,  -- Additional data from provider
#     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
# );

# -- Carts table (one per user, holds cart items)
# CREATE TABLE carts (
#     id SERIAL PRIMARY KEY,
#     user_id INT NOT NULL UNIQUE,  -- One cart per user
#     created_at TIMESTAMP NOT NULL,
#     updated_at TIMESTAMP NOT NULL,
#     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
# );

# -- Cart items table (items in a user's cart)
# CREATE TABLE cart_items (
#     id SERIAL PRIMARY KEY,
#     cart_id INT NOT NULL,
#     item_id INT NOT NULL,
#     size_id INT NOT NULL,
#     quantity INT NOT NULL,  -- Quantity of this item/size
#     created_at TIMESTAMP NOT NULL,
#     updated_at TIMESTAMP NOT NULL,
#     FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
#     FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
#     FOREIGN KEY (size_id) REFERENCES sizes(id) ON DELETE CASCADE
# );

# -- Orders table
# CREATE TABLE orders (
#     id SERIAL PRIMARY KEY,
#     user_id INT,  -- Optional, allows guest orders
#     status VARCHAR(50) NOT NULL,  -- e.g., 'Pending', 'Processing', 'Shipped', 'Delivered'
#     total_price DECIMAL(10, 2) NOT NULL,  -- Total cost of order
#     shipping_address TEXT NOT NULL,  -- Address for delivery
#     shipping_phone VARCHAR(20) NOT NULL,  -- Contact phone for delivery
#     shipping_name VARCHAR(255) NOT NULL,  -- Name of the person receiving the order
#     shipping_email VARCHAR(255) NOT NULL,  -- Email for order updates
#     first_name VARCHAR(150) NOT NULL,  -- First name for shipping
#     last_name VARCHAR(150) NOT NULL,  -- Last name for shipping
#     zip_code VARCHAR(20) NOT NULL,  -- ZIP/Postal code
#     city VARCHAR(100) NOT NULL,  -- City for shipping
#     guest_email VARCHAR(255),  -- Optional email for guest users to track orders
#     created_at TIMESTAMP NOT NULL,
#     updated_at TIMESTAMP NOT NULL,
#     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
# );

# -- Order items table
# CREATE TABLE order_items (
#     id SERIAL PRIMARY KEY,
#     order_id INT NOT NULL,
#     item_id INT NOT NULL,
#     size_id INT NOT NULL,
#     quantity INT NOT NULL,
#     price_at_time DECIMAL(10, 2) NOT NULL,  -- Price at time of order
#     primary_image VARCHAR(255) NOT NULL,  -- Primary image URL of the item
#     created_at TIMESTAMP NOT NULL,
#     updated_at TIMESTAMP NOT NULL,
#     FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
#     FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
#     FOREIGN KEY (size_id) REFERENCES sizes(id) ON DELETE CASCADE
# );

class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
        

class User(AbstractUser, BaseModel):
    username = models.CharField(max_length=150, unique=True, null=False, blank=False)
    email = models.EmailField(unique=True, null=False, blank=False)
    first_name = models.CharField(max_length=150, null=True, blank=True)
    last_name = models.CharField(max_length=150, null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    is_superuser = models.BooleanField(default=False, help_text='Designates whether this user has all permissions without explicitly assigning them.')

    def __str__(self):
        return self.username


class PasswordResetToken(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255)
    expires_at = models.DateTimeField()

    def __str__(self):
        return self.token


class SocialAccount(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    provider = models.CharField(max_length=50)  # e.g., 'google', 'facebook'
    uid = models.CharField(max_length=255)  # Unique ID from the provider
    extra_data = models.JSONField(null=True, blank=True)  # Additional data from provider

    def __str__(self):
        return f"{self.provider} - {self.uid}"


class Cart(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)  # One cart per user

    def __str__(self):
        return f"Cart for {self.user.username}"


class CartItem(BaseModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    size = models.ForeignKey(ItemSize, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantity}x {self.item.name} ({self.size.name})"


class Order(BaseModel):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        null=True,  # Allow null for guest orders
        blank=True  # Allow blank in forms
    )
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Shipping information
    shipping_address = models.TextField(default='')
    shipping_phone = models.CharField(max_length=20, default='0000000000')
    shipping_name = models.CharField(max_length=255, default='Guest')
    shipping_email = models.EmailField(default='guest@example.com')
    
    # New shipping fields with defaults
    first_name = models.CharField(max_length=150, default='')
    last_name = models.CharField(max_length=150, default='')
    zip_code = models.CharField(max_length=20, default='')
    city = models.CharField(max_length=100, default='')
    
    # Optional fields for guest users
    guest_email = models.EmailField(null=True, blank=True)

    def __str__(self):
        if self.user:
            return f"Order {self.id} - {self.user.username}"
        return f"Order {self.id} - Guest ({self.shipping_email})"


class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    size = models.ForeignKey(ItemSize, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order
    primary_image = models.URLField(default='')  # Store the primary image URL with default empty string

    def __str__(self):
        return f"{self.quantity}x {self.item.name} ({self.size.name})"

