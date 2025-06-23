from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.hashers import make_password, check_password
from .models import User, PasswordResetToken, Cart, CartItem, Item, ItemSize, Order, OrderItem
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
import os
from datetime import datetime, timedelta
import secrets
import resend
import logging
from django.db import models
from decimal import Decimal

logger = logging.getLogger(__name__)

class UserView(APIView):
    def get(self, request):
        return Response({"message": "Hello, World!"}, status=status.HTTP_200_OK)

class RegisterView(APIView):
    permission_classes = []  # Allow public access for registration
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def post(self, request):
        try:
            data = request.data
            
            # Check required fields
            if not data.get('email') or not data.get('password'):
                return Response(
                    {"error": "Email and password are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if email already exists
            if User.objects.filter(email=data.get('email')).exists():
                return Response(
                    {"error": "Email already exists"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create new user
            user = User.objects.create(
                username=data.get('email'),  # Use email as username
                email=data.get('email'),
                password=make_password(data.get('password')),
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                phone_number=data.get('phone_number', ''),
                address=data.get('address', '')
            )
            
            return Response({
                "message": "User created successfully"
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class LoginView(APIView):
    permission_classes = []  # Allow public access for login
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def post(self, request):
        try:
            data = request.data
            logger.info(f"Login attempt with data: {data}")
            
            # Check required fields
            if not data.get('email') or not data.get('password'):
                logger.warning(f"Missing email or password in login request")
                return Response(
                    {"error": "Email and password are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Find user by email
            try:
                user = User.objects.get(email=data.get('email'))
                logger.info(f"User found: {user.email}")
            except User.DoesNotExist:
                logger.warning(f"User not found for email: {data.get('email')}")
                return Response(
                    {"error": "Invalid email or password"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Check password
            if not check_password(data.get('password'), user.password):
                logger.warning(f"Invalid password for user: {user.email}")
                return Response(
                    {"error": "Invalid email or password"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Handle cart merging if guest cart is provided
            guest_cart = data.get('guest_cart')
            merged_cart_info = None
            
            if guest_cart and guest_cart.get('items'):
                try:
                    merged_cart_info = self.merge_guest_cart_with_user_cart(user, guest_cart)
                    logger.info(f"Cart merged successfully for user: {user.email}")
                except Exception as cart_error:
                    logger.error(f"Error merging cart for user {user.email}: {str(cart_error)}")
                    # Don't fail login if cart merge fails, just log the error
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            logger.info(f"Login successful for user: {user.email}")
            
            response_data = {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "address": user.address,
                    "is_superuser": user.is_superuser
                },
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh)
                }
            }
            
            # Add cart merge information if available
            if merged_cart_info:
                response_data["cart_merge"] = merged_cart_info
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def merge_guest_cart_with_user_cart(self, user, guest_cart):
        """
        Merge guest cart with user's existing cart
        Returns information about the merge operation
        """
        # Get or create user's cart
        user_cart, created = Cart.objects.get_or_create(user=user)
        
        # Get existing cart items
        existing_cart_items = CartItem.objects.filter(cart=user_cart).select_related('item', 'size')
        
        # Create a lookup dict for existing items (item_id + size_id as key)
        existing_items_dict = {}
        for cart_item in existing_cart_items:
            key = f"{cart_item.item.id}_{cart_item.size.id}"
            existing_items_dict[key] = cart_item
        
        # Process guest cart items
        merged_items = []
        added_items = []
        updated_items = []
        failed_items = []
        
        for guest_item in guest_cart.get('items', []):
            try:
                # Validate item and size exist
                item = Item.objects.get(id=guest_item['id'])
                size = ItemSize.objects.get(id=guest_item['size_id'])
                
                # Check stock availability
                requested_quantity = guest_item['quantity']
                if requested_quantity > size.quantity:
                    failed_items.append({
                        'item_name': item.name,
                        'size': size.size,
                        'requested_quantity': requested_quantity,
                        'available_quantity': size.quantity,
                        'reason': 'insufficient_stock'
                    })
                    continue
                
                key = f"{item.id}_{size.id}"
                
                if key in existing_items_dict:
                    # Item already exists in user cart - merge quantities
                    existing_cart_item = existing_items_dict[key]
                    old_quantity = existing_cart_item.quantity
                    
                    # Strategy: Sum quantities, but respect stock limits
                    new_quantity = old_quantity + requested_quantity
                    
                    if new_quantity > size.quantity:
                        # If sum exceeds stock, use maximum available
                        new_quantity = size.quantity
                        failed_items.append({
                            'item_name': item.name,
                            'size': size.size,
                            'requested_quantity': requested_quantity,
                            'existing_quantity': old_quantity,
                            'final_quantity': new_quantity,
                            'reason': 'partial_merge_due_to_stock'
                        })
                    
                    existing_cart_item.quantity = new_quantity
                    existing_cart_item.save()
                    
                    updated_items.append({
                        'item_name': item.name,
                        'size': size.size,
                        'old_quantity': old_quantity,
                        'added_quantity': requested_quantity,
                        'final_quantity': new_quantity
                    })
                    
                else:
                    # New item - add to user cart
                    new_cart_item = CartItem.objects.create(
                        cart=user_cart,
                        item=item,
                        size=size,
                        quantity=requested_quantity
                    )
                    
                    added_items.append({
                        'item_name': item.name,
                        'size': size.size,
                        'quantity': requested_quantity
                    })
                
                merged_items.append({
                    'item_id': item.id,
                    'item_name': item.name,
                    'size': size.size,
                    'quantity': requested_quantity
                })
                
            except (Item.DoesNotExist, ItemSize.DoesNotExist):
                failed_items.append({
                    'item_id': guest_item.get('id'),
                    'size_id': guest_item.get('size_id'),
                    'quantity': guest_item.get('quantity'),
                    'reason': 'item_not_found'
                })
            except Exception as item_error:
                logger.error(f"Error processing guest cart item: {str(item_error)}")
                failed_items.append({
                    'item_id': guest_item.get('id'),
                    'size_id': guest_item.get('size_id'),
                    'quantity': guest_item.get('quantity'),
                    'reason': 'processing_error'
                })
        
        return {
            'success': True,
            'total_guest_items': len(guest_cart.get('items', [])),
            'added_items': added_items,
            'updated_items': updated_items,
            'failed_items': failed_items,
            'message': f"Cart merge completed. Added {len(added_items)} new items, updated {len(updated_items)} existing items."
        }

class VerifyTokenView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            user = request.user
            return Response({
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "address": user.address,
                    "is_superuser": user.is_superuser
                }
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class ForgotPasswordView(APIView):
    permission_classes = []  # Allow public access for password reset
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def post(self, request):
        try:
            email = request.data.get('email')
            if not email:
                return Response(
                    {"error": "Email is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Find user by email
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response(
                    {"error": "Email is not registered"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate reset token
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=1)  # Token expires in 1 hour
            
            # Save or update reset token
            PasswordResetToken.objects.update_or_create(
                user=user,
                defaults={
                    'token': token,
                    'expires_at': expires_at
                }
            )
            
            # Send email using Resend
            api_key = os.getenv('RESEND_API_KEY')
            if not api_key:
                logger.error("RESEND_API_KEY is not set in environment variables")
                return Response(
                    {"error": "Email service is not configured"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            resend.api_key = api_key
            
            # Get frontend URL from environment variable, default to localhost:3000
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
            reset_url = f"{frontend_url}/reset-password?token={token}"
            
            try:
                params = {
                    "from": "Peter's Shop <no-reply@petershop.shop>",
                    "to": [email],
                    "subject": "Reset Your Password",
                    "html": f"""
                        <h2>Reset Your Password</h2>
                        <p>Click the link below to reset your password. This link will expire in 1 hour.</p>
                        <a href="{reset_url}">Reset Password</a>
                        <p>If you didn't request this, please ignore this email.</p>
                    """
                }
                
                email = resend.Emails.send(params)
                logger.info(f"Password reset email sent to {email}")
            except Exception as email_error:
                logger.error(f"Error sending email: {str(email_error)}")
                return Response(
                    {"error": "Failed to send reset email"}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            return Response({
                "message": "Password reset link has been sent to your email"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in forgot password: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class ResetPasswordView(APIView):
    permission_classes = []  # Allow public access for password reset
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def post(self, request):
        try:
            token = request.data.get('token')
            new_password = request.data.get('new_password')
            
            if not token or not new_password:
                return Response(
                    {"error": "Token and new password are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Find valid reset token
            try:
                reset_token = PasswordResetToken.objects.get(
                    token=token,
                    expires_at__gt=datetime.now()
                )
            except PasswordResetToken.DoesNotExist:
                return Response(
                    {"error": "Invalid or expired reset token"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update user's password
            user = reset_token.user
            user.password = make_password(new_password)
            user.save()
            
            # Delete used token
            reset_token.delete()
            
            return Response({
                "message": "Password has been reset successfully"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class CartView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get the user's cart items"""
        try:
            # Get or create cart for the user
            cart, created = Cart.objects.get_or_create(user=request.user)
            
            # Get all cart items with related item and size information
            cart_items = CartItem.objects.filter(cart=cart).select_related(
                'item', 'size'
            ).prefetch_related(
                'item__images',
                'item__categories'
            ).order_by('-created_at')
            
            # Format the response
            items = []
            for cart_item in cart_items:
                item = cart_item.item
                # Get primary image
                primary_image = item.images.filter(is_primary=True, quality='low').first()
                
                # Get all category names and combine them
                category_names = item.categories.values_list('name', flat=True)
                combined_categories = ', '.join(category_names) if category_names else None
                
                items.append({
                    'id': item.id,
                    'cart_item_id': cart_item.id,
                    'name': item.name,
                    'price': str(item.price),
                    'size': cart_item.size.size,
                    'quantity': cart_item.quantity,
                    'total_available': cart_item.size.quantity,
                    'image_url': primary_image.image_url if primary_image else None,
                    'categories': combined_categories
                })
            
            return Response({
                'cart_id': cart.id,
                'items': items,
                'total_items': len(items)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def post(self, request):
        """Add an item to the cart"""
        try:
            # Validate required fields
            if not all(k in request.data for k in ['item_id', 'size_id', 'quantity']):
                return Response(
                    {"error": "item_id, size_id, and quantity are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get or create cart for the user
            cart, created = Cart.objects.get_or_create(user=request.user)
            
            # Get the item and size
            try:
                item = Item.objects.get(id=request.data['item_id'])
                size = ItemSize.objects.get(id=request.data['size_id'])
            except (Item.DoesNotExist, ItemSize.DoesNotExist):
                return Response(
                    {"error": "Invalid item or size"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate requested quantity against available stock
            requested_quantity = int(request.data['quantity'])
            if requested_quantity <= 0:
                return Response(
                    {"error": "Quantity must be greater than 0"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if requested_quantity > size.quantity:
                return Response(
                    {"error": f"Only {size.quantity} items available in size {size.size}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if item already exists in cart
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                item=item,
                size=size,
                defaults={'quantity': requested_quantity}
            )
            
            # If item exists, handle quantity based on add parameter
            if not created:
                new_quantity = cart_item.quantity + requested_quantity if request.data.get('add', False) else requested_quantity
                
                # Check if new total quantity exceeds available stock
                if new_quantity > size.quantity:
                    return Response(
                        {"error": f"Only {size.quantity} items available in size {size.size}"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                cart_item.quantity = new_quantity
                cart_item.save()
            
            return Response({
                "message": "Item added to cart successfully",
                "cart_item": {
                    "id": cart_item.id,
                    "quantity": cart_item.quantity
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def put(self, request):
        """Update cart item quantity"""
        try:
            # Validate required fields
            if not all(k in request.data for k in ['cart_item_id', 'quantity']):
                return Response(
                    {"error": "cart_item_id and quantity are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the cart item
            try:
                cart_item = CartItem.objects.get(
                    id=request.data['cart_item_id'],
                    cart__user=request.user
                )
            except CartItem.DoesNotExist:
                return Response(
                    {"error": "Cart item not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Update quantity
            cart_item.quantity = int(request.data['quantity'])
            cart_item.save()
            
            return Response({
                "message": "Cart item updated successfully",
                "cart_item": {
                    "id": cart_item.id,
                    "quantity": cart_item.quantity
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def delete(self, request):
        """Remove an item from the cart"""
        try:
            cart_item_id = request.query_params.get('cart_item_id')
            if not cart_item_id:
                return Response(
                    {"error": "cart_item_id is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get the cart item
            try:
                cart_item = CartItem.objects.get(
                    id=cart_item_id,
                    cart__user=request.user
                )
            except CartItem.DoesNotExist:
                return Response(
                    {"error": "Cart item not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Delete the cart item
            cart_item.delete()
            
            return Response({
                "message": "Item removed from cart successfully"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class CartCountView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get the total number of items in the user's cart"""
        try:
            # Get or create cart for the user
            cart, created = Cart.objects.get_or_create(user=request.user)
            
            # Get total quantity of all items in cart
            total_items = CartItem.objects.filter(cart=cart).aggregate(
                total_quantity=models.Sum('quantity')
            )['total_quantity'] or 0
            
            return Response({
                'total_items': total_items
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class OrderView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def post(self, request):
        """Create a new order from cart items"""
        try:
            # Get cart_id from request
            cart_id = request.data.get('cart_id')
            if not cart_id:
                return Response(
                    {"error": "cart_id is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get user's cart
            try:
                cart = Cart.objects.get(id=cart_id, user=request.user)
                cart_items = CartItem.objects.filter(cart=cart).select_related(
                    'item', 'size'
                ).prefetch_related(
                    'item__images'
                )
            except Cart.DoesNotExist:
                return Response(
                    {"error": "Cart not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            if not cart_items.exists():
                return Response(
                    {"error": "Cart is empty"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Calculate total price
            total_price = Decimal('0.00')
            for cart_item in cart_items:
                total_price += cart_item.item.price * cart_item.quantity
            
            # Create order
            order = Order.objects.create(
                user=request.user,
                status='Pending',
                total_price=total_price,
                shipping_address=request.data.get('shipping_address', ''),
                shipping_phone=request.data.get('shipping_phone', '0000000000'),
                shipping_email=request.data.get('shipping_email', 'guest@example.com'),
                first_name=request.data.get('first_name', ''),
                last_name=request.data.get('last_name', ''),
                zip_code=request.data.get('zip_code', ''),
                city=request.data.get('city', '')
            )
            
            # Create order items and update stock
            order_items = []
            for cart_item in cart_items:
                # Get primary image
                primary_image = cart_item.item.images.filter(is_primary=True, quality='low').first()
                
                # Create order item
                order_item = OrderItem.objects.create(
                    order=order,
                    item=cart_item.item,
                    size=cart_item.size,
                    quantity=cart_item.quantity,
                    price_at_time=cart_item.item.price,
                    primary_image=primary_image.image_url if primary_image else None
                )
                
                # Update stock
                cart_item.size.quantity -= cart_item.quantity
                cart_item.size.save()
                
                order_items.append({
                    'id': order_item.id,
                    'item_name': cart_item.item.name,
                    'size': cart_item.size.size,
                    'quantity': cart_item.quantity,
                    'price': str(cart_item.item.price),
                    'image_url': primary_image.image_url if primary_image else None
                })
            
            # Clear the cart
            cart_items.delete()
            
            # Send order confirmation email
            try:
                api_key = os.getenv('RESEND_API_KEY')
                if api_key:
                    resend.api_key = api_key
                    
                    # Format order items for email
                    items_html = ""
                    for item in order_items:
                        items_html += f"""
                            <tr>
                                <td>{item['item_name']}</td>
                                <td>{item['size']}</td>
                                <td>{item['quantity']}</td>
                                <td>${item['price']}</td>
                            </tr>
                        """
                    
                    params = {
                        "from": "Peter's Shop <no-reply@petershop.shop>",
                        "to": [order.shipping_email],
                        "subject": f"Thank You for Your Order #{order.id}",
                        "html": f"""
                            <!DOCTYPE html>
                            <html lang="en">
                            <head>
                                <meta charset="UTF-8">
                                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                <title>Order Confirmation</title>
                                <style>
                                    /* Reset styles */
                                    * {{
                                        margin: 0;
                                        padding: 0;
                                        box-sizing: border-box;
                                    }}
                                    
                                    body {{
                                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                                        line-height: 1.6;
                                        color: #333;
                                        background-color: #f5f5f5;
                                        margin: 0;
                                        padding: 0;
                                    }}
                                    
                                    .email-container {{
                                        max-width: 600px;
                                        margin: 0 auto;
                                        background-color: #ffffff;
                                        padding: 20px;
                                    }}
                                    
                                    .header {{
                                        text-align: center;
                                        margin-bottom: 30px;
                                        padding: 20px 0;
                                    }}
                                    
                                    .header h1 {{
                                        color: #2c3e50;
                                        margin-bottom: 10px;
                                        font-size: 28px;
                                        font-weight: 700;
                                    }}
                                    
                                    .header p {{
                                        color: #7f8c8d;
                                        font-size: 16px;
                                        margin: 0;
                                    }}
                                    
                                    .payment-section {{
                                        background-color: #f8f9fa;
                                        padding: 20px;
                                        border-radius: 8px;
                                        margin-bottom: 30px;
                                        border-left: 4px solid #3498db;
                                    }}
                                    
                                    .payment-section h2 {{
                                        color: #2c3e50;
                                        margin-bottom: 15px;
                                        font-size: 20px;
                                    }}
                                    
                                    .payment-section p {{
                                        font-size: 16px;
                                        margin-bottom: 15px;
                                        line-height: 1.5;
                                    }}
                                    
                                    .email-highlight {{
                                        background-color: #fff;
                                        padding: 15px;
                                        border-radius: 6px;
                                        margin: 15px 0;
                                        text-align: center;
                                        border: 2px solid #3498db;
                                    }}
                                    
                                    .email-highlight p {{
                                        font-size: 18px;
                                        font-weight: bold;
                                        color: #2c3e50;
                                        margin: 0;
                                    }}
                                    
                                    .order-id-note {{
                                        color: #2c3e50;
                                        font-weight: bold;
                                        background-color: #e8f5e9;
                                        padding: 12px;
                                        border-radius: 4px;
                                        text-align: center;
                                        margin-top: 15px;
                                    }}
                                    
                                    .order-summary {{
                                        margin-bottom: 30px;
                                    }}
                                    
                                    .order-summary h3 {{
                                        color: #2c3e50;
                                        border-bottom: 2px solid #eee;
                                        padding-bottom: 10px;
                                        margin-bottom: 20px;
                                        font-size: 18px;
                                    }}
                                    
                                    .order-table {{
                                        width: 100%;
                                        border-collapse: collapse;
                                        margin-top: 15px;
                                        background-color: #fff;
                                        border-radius: 8px;
                                        overflow: hidden;
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                    }}
                                    
                                    .order-table th {{
                                        background-color: #f8f9fa;
                                        padding: 12px 8px;
                                        text-align: left;
                                        border-bottom: 2px solid #ddd;
                                        font-weight: 600;
                                        font-size: 14px;
                                    }}
                                    
                                    .order-table td {{
                                        padding: 12px 8px;
                                        border-bottom: 1px solid #eee;
                                        font-size: 14px;
                                    }}
                                    
                                    .order-table .text-center {{
                                        text-align: center;
                                    }}
                                    
                                    .order-table .text-right {{
                                        text-align: right;
                                    }}
                                    
                                    .order-table .total-row {{
                                        background-color: #f8f9fa;
                                        font-weight: bold;
                                    }}
                                    
                                    .shipping-info {{
                                        background-color: #f8f9fa;
                                        padding: 20px;
                                        border-radius: 8px;
                                        margin-bottom: 30px;
                                    }}
                                    
                                    .shipping-info h3 {{
                                        color: #2c3e50;
                                        margin-bottom: 15px;
                                        font-size: 18px;
                                    }}
                                    
                                    .shipping-info p {{
                                        margin: 8px 0;
                                        font-size: 14px;
                                        line-height: 1.4;
                                    }}
                                    
                                    .footer {{
                                        text-align: center;
                                        margin-top: 30px;
                                        padding-top: 20px;
                                        border-top: 1px solid #eee;
                                    }}
                                    
                                    .footer p {{
                                        color: #7f8c8d;
                                        margin-bottom: 10px;
                                        font-size: 14px;
                                    }}
                                    
                                    .footer a {{
                                        color: #3498db;
                                        text-decoration: none;
                                        font-weight: 500;
                                    }}
                                    
                                    /* Mobile Responsive Styles */
                                    @media only screen and (max-width: 600px) {{
                                        .email-container {{
                                            padding: 15px;
                                            margin: 0;
                                        }}
                                        
                                        .header h1 {{
                                            font-size: 24px;
                                        }}
                                        
                                        .header p {{
                                            font-size: 14px;
                                        }}
                                        
                                        .payment-section {{
                                            padding: 15px;
                                            margin-bottom: 20px;
                                        }}
                                        
                                        .payment-section h2 {{
                                            font-size: 18px;
                                        }}
                                        
                                        .payment-section p {{
                                            font-size: 14px;
                                        }}
                                        
                                        .email-highlight {{
                                            padding: 12px;
                                        }}
                                        
                                        .email-highlight p {{
                                            font-size: 16px;
                                        }}
                                        
                                        .order-id-note {{
                                            padding: 10px;
                                            font-size: 14px;
                                        }}
                                        
                                        .order-table {{
                                            font-size: 12px;
                                        }}
                                        
                                        .order-table th,
                                        .order-table td {{
                                            padding: 8px 4px;
                                            font-size: 12px;
                                        }}
                                        
                                        .order-table th:first-child,
                                        .order-table td:first-child {{
                                            padding-left: 8px;
                                        }}
                                        
                                        .order-table th:last-child,
                                        .order-table td:last-child {{
                                            padding-right: 8px;
                                        }}
                                        
                                        .shipping-info {{
                                            padding: 15px;
                                        }}
                                        
                                        .shipping-info h3 {{
                                            font-size: 16px;
                                        }}
                                        
                                        .shipping-info p {{
                                            font-size: 13px;
                                        }}
                                        
                                        .footer p {{
                                            font-size: 13px;
                                        }}
                                    }}
                                    
                                    @media only screen and (max-width: 480px) {{
                                        .email-container {{
                                            padding: 10px;
                                        }}
                                        
                                        .header {{
                                            padding: 15px 0;
                                            margin-bottom: 20px;
                                        }}
                                        
                                        .header h1 {{
                                            font-size: 22px;
                                        }}
                                        
                                        .payment-section,
                                        .shipping-info {{
                                            padding: 12px;
                                        }}
                                        
                                        .order-table th,
                                        .order-table td {{
                                            padding: 6px 3px;
                                            font-size: 11px;
                                        }}
                                        
                                        .order-summary h3,
                                        .shipping-info h3 {{
                                            font-size: 15px;
                                        }}
                                    }}
                                </style>
                            </head>
                            <body>
                                <div class="email-container">
                                    <div class="header">
                                        <h1>Thank You for Your Order!</h1>
                                        <p>We're excited to process your order #{order.id}</p>
                                    </div>

                                    <div class="payment-section">
                                        <h2>Next Steps: Complete Your Payment</h2>
                                        <p>To complete your order, please send payment via E-transfer to:</p>
                                        <div class="email-highlight">
                                            <p>lei232lei91@gmail.com</p>
                                        </div>
                                        <div class="order-id-note">
                                            Please include Order ID #{order.id} in the transfer message
                                        </div>
                                    </div>

                                    <div class="order-summary">
                                        <h3>Order Summary</h3>
                                        <table class="order-table">
                                            <tr>
                                                <th>Item</th>
                                                <th>Size</th>
                                                <th class="text-center">Qty</th>
                                                <th class="text-right">Price</th>
                                            </tr>
                                            {items_html}
                                            <tr class="total-row">
                                                <td colspan="3" class="text-right">Total:</td>
                                                <td class="text-right">${order.total_price}</td>
                                            </tr>
                                        </table>
                                    </div>

                                    <div class="shipping-info">
                                        <h3>Shipping Information</h3>
                                        <p><strong>Name:</strong> {order.first_name} {order.last_name}</p>
                                        <p><strong>Address:</strong> {order.shipping_address}</p>
                                        <p><strong>City:</strong> {order.city}</p>
                                        <p><strong>ZIP Code:</strong> {order.zip_code}</p>
                                        <p><strong>Phone:</strong> {order.shipping_phone}</p>
                                    </div>

                                    <div class="footer">
                                        <p>Questions about your order?</p>
                                        <a href="mailto:lei23lei91@gmail.com">Contact us at lei23lei91@gmail.com</a>
                                    </div>
                                </div>
                            </body>
                            </html>
                        """
                    }
                    
                    email = resend.Emails.send(params)
                    logger.info(f"Order confirmation email sent to {order.shipping_email}")
            except Exception as email_error:
                logger.error(f"Error sending order confirmation email: {str(email_error)}")
                # Continue with the response even if email fails
            
            return Response({
                "message": "Order created successfully",
                "order": {
                    "id": order.id,
                    "status": order.status,
                    "total_price": str(order.total_price),
                    "shipping_address": order.shipping_address,
                    "shipping_phone": order.shipping_phone,
                    "shipping_email": order.shipping_email,
                    "first_name": order.first_name,
                    "last_name": order.last_name,
                    "zip_code": order.zip_code,
                    "city": order.city,
                    "created_at": order.created_at,
                    "items": order_items
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get the authenticated user's details"""
        try:
            user = request.user
            return Response({
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "address": user.address,
                    "is_superuser": user.is_superuser,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def put(self, request):
        """Update the authenticated user's details"""
        try:
            user = request.user
            data = request.data
            
            # Fields that can be updated
            updateable_fields = [
                'first_name', 
                'last_name', 
                'phone_number', 
                'address'
            ]
            
            # Update only the fields that are provided in the request
            for field in updateable_fields:
                if field in data:
                    setattr(user, field, data[field])
            
            # Save the updated user
            user.save()
            
            return Response({
                "message": "User information updated successfully",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "phone_number": user.phone_number,
                    "address": user.address,
                    "is_superuser": user.is_superuser,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def post(self, request):
        """Change the authenticated user's password"""
        try:
            data = request.data
            
            # Check required fields
            if not data.get('current_password') or not data.get('new_password'):
                return Response(
                    {"error": "Current password and new password are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user = request.user
            
            # Verify current password
            if not check_password(data.get('current_password'), user.password):
                return Response(
                    {"error": "Current password is incorrect"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update password
            user.password = make_password(data.get('new_password'))
            user.save()
            
            return Response({
                "message": "Password changed successfully"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class UserOrdersView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all orders for the authenticated user"""
        try:
            # Get all orders for the user with related items
            orders = Order.objects.filter(user=request.user).prefetch_related(
                'orderitem_set',
                'orderitem_set__item',
                'orderitem_set__size'
            ).order_by('-created_at')
            
            orders_data = []
            for order in orders:
                # Get all items for this order
                order_items = []
                for order_item in order.orderitem_set.all():
                    order_items.append({
                        'id': order_item.id,
                        'item_name': order_item.item.name,
                        'size': order_item.size.size,
                        'quantity': order_item.quantity,
                        'price_at_time': str(order_item.price_at_time),
                        'primary_image': order_item.primary_image
                    })
                
                # Format order data
                orders_data.append({
                    'id': order.id,
                    'status': order.status,
                    'total_price': str(order.total_price),
                    'shipping_address': order.shipping_address,
                    'shipping_phone': order.shipping_phone,
                    'shipping_name': order.shipping_name,
                    'shipping_email': order.shipping_email,
                    'first_name': order.first_name,
                    'last_name': order.last_name,
                    'zip_code': order.zip_code,
                    'city': order.city,
                    'created_at': order.created_at,
                    'updated_at': order.updated_at,
                    'items': order_items
                })
            
            return Response({
                'orders': orders_data,
                'total_orders': len(orders_data)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class GuestCheckoutView(APIView):
    permission_classes = []  # Allow public access for guest checkout
    parser_classes = (MultiPartParser, FormParser, JSONParser)
    
    def post(self, request):
        """Create a new order from guest cart data sent from frontend"""
        try:
            # Get cart data from request - expecting LocalCart structure
            cart_data = request.data.get('cart', {})
            cart_items = cart_data.get('items', [])
            
            if not cart_items:
                return Response(
                    {"error": "Cart is empty"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate required shipping information
            required_fields = [
                'shipping_address', 'shipping_phone', 'shipping_email',
                'first_name', 'last_name', 'zip_code', 'city'
            ]
            
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response(
                    {"error": f"Missing required fields: {', '.join(missing_fields)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate cart items and calculate total
            cart_items_data = []
            total_price = Decimal('0.00')
            
            for cart_item in cart_items:
                try:
                    # Use 'id' instead of 'item_id' to match your LocalCartItem interface
                    item = Item.objects.get(id=cart_item['id'])
                    size = ItemSize.objects.get(id=cart_item['size_id'])
                    
                    # Validate stock availability
                    if cart_item['quantity'] > size.quantity:
                        return Response(
                            {"error": f"Only {size.quantity} items available for {item.name} in size {size.size}"}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    # Calculate item total
                    item_total = item.price * cart_item['quantity']
                    total_price += item_total
                    
                    cart_items_data.append({
                        'item': item,
                        'size': size,
                        'quantity': cart_item['quantity'],
                        'price': item.price
                    })
                    
                except (Item.DoesNotExist, ItemSize.DoesNotExist):
                    return Response(
                        {"error": "One or more items in cart are no longer available"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Create order
            order = Order.objects.create(
                user=None,  # Guest order
                status='Pending',
                total_price=total_price,
                shipping_address=request.data.get('shipping_address'),
                shipping_phone=request.data.get('shipping_phone'),
                shipping_email=request.data.get('shipping_email'),
                first_name=request.data.get('first_name'),
                last_name=request.data.get('last_name'),
                zip_code=request.data.get('zip_code'),
                city=request.data.get('city'),
                guest_email=request.data.get('shipping_email')  # Store guest email
            )
            
            # Create order items and update stock
            order_items = []
            for cart_item_data in cart_items_data:
                # Get primary image
                primary_image = cart_item_data['item'].images.filter(is_primary=True, quality='low').first()
                
                # Create order item
                order_item = OrderItem.objects.create(
                    order=order,
                    item=cart_item_data['item'],
                    size=cart_item_data['size'],
                    quantity=cart_item_data['quantity'],
                    price_at_time=cart_item_data['price'],
                    primary_image=primary_image.image_url if primary_image else None
                )
                
                # Update stock
                cart_item_data['size'].quantity -= cart_item_data['quantity']
                cart_item_data['size'].save()
                
                order_items.append({
                    'id': order_item.id,
                    'item_name': cart_item_data['item'].name,
                    'size': cart_item_data['size'].size,
                    'quantity': cart_item_data['quantity'],
                    'price': str(cart_item_data['price']),
                    'image_url': primary_image.image_url if primary_image else None
                })
            
            # Send order confirmation email
            try:
                api_key = os.getenv('RESEND_API_KEY')
                if api_key:
                    resend.api_key = api_key
                    
                    # Format order items for email
                    items_html = ""
                    for item in order_items:
                        items_html += f"""
                            <tr>
                                <td>{item['item_name']}</td>
                                <td>{item['size']}</td>
                                <td>{item['quantity']}</td>
                                <td>${item['price']}</td>
                            </tr>
                        """
                    
                    params = {
                        "from": "Peter's Shop <no-reply@petershop.shop>",
                        "to": [order.shipping_email],
                        "subject": f"Thank You for Your Order #{order.id}",
                        "html": f"""
                            <!DOCTYPE html>
                            <html lang="en">
                            <head>
                                <meta charset="UTF-8">
                                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                <title>Order Confirmation</title>
                                <style>
                                    /* Reset styles */
                                    * {{
                                        margin: 0;
                                        padding: 0;
                                        box-sizing: border-box;
                                    }}
                                    
                                    body {{
                                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                                        line-height: 1.6;
                                        color: #333;
                                        background-color: #f5f5f5;
                                        margin: 0;
                                        padding: 0;
                                    }}
                                    
                                    .email-container {{
                                        max-width: 600px;
                                        margin: 0 auto;
                                        background-color: #ffffff;
                                        padding: 20px;
                                    }}
                                    
                                    .header {{
                                        text-align: center;
                                        margin-bottom: 30px;
                                        padding: 20px 0;
                                    }}
                                    
                                    .header h1 {{
                                        color: #2c3e50;
                                        margin-bottom: 10px;
                                        font-size: 28px;
                                        font-weight: 700;
                                    }}
                                    
                                    .header p {{
                                        color: #7f8c8d;
                                        font-size: 16px;
                                        margin: 0;
                                    }}
                                    
                                    .payment-section {{
                                        background-color: #f8f9fa;
                                        padding: 20px;
                                        border-radius: 8px;
                                        margin-bottom: 30px;
                                        border-left: 4px solid #3498db;
                                    }}
                                    
                                    .payment-section h2 {{
                                        color: #2c3e50;
                                        margin-bottom: 15px;
                                        font-size: 20px;
                                    }}
                                    
                                    .payment-section p {{
                                        font-size: 16px;
                                        margin-bottom: 15px;
                                        line-height: 1.5;
                                    }}
                                    
                                    .email-highlight {{
                                        background-color: #fff;
                                        padding: 15px;
                                        border-radius: 6px;
                                        margin: 15px 0;
                                        text-align: center;
                                        border: 2px solid #3498db;
                                    }}
                                    
                                    .email-highlight p {{
                                        font-size: 18px;
                                        font-weight: bold;
                                        color: #2c3e50;
                                        margin: 0;
                                    }}
                                    
                                    .order-id-note {{
                                        color: #2c3e50;
                                        font-weight: bold;
                                        background-color: #e8f5e9;
                                        padding: 12px;
                                        border-radius: 4px;
                                        text-align: center;
                                        margin-top: 15px;
                                    }}
                                    
                                    .order-summary {{
                                        margin-bottom: 30px;
                                    }}
                                    
                                    .order-summary h3 {{
                                        color: #2c3e50;
                                        border-bottom: 2px solid #eee;
                                        padding-bottom: 10px;
                                        margin-bottom: 20px;
                                        font-size: 18px;
                                    }}
                                    
                                    .order-table {{
                                        width: 100%;
                                        border-collapse: collapse;
                                        margin-top: 15px;
                                        background-color: #fff;
                                        border-radius: 8px;
                                        overflow: hidden;
                                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                    }}
                                    
                                    .order-table th {{
                                        background-color: #f8f9fa;
                                        padding: 12px 8px;
                                        text-align: left;
                                        border-bottom: 2px solid #ddd;
                                        font-weight: 600;
                                        font-size: 14px;
                                    }}
                                    
                                    .order-table td {{
                                        padding: 12px 8px;
                                        border-bottom: 1px solid #eee;
                                        font-size: 14px;
                                    }}
                                    
                                    .order-table .text-center {{
                                        text-align: center;
                                    }}
                                    
                                    .order-table .text-right {{
                                        text-align: right;
                                    }}
                                    
                                    .order-table .total-row {{
                                        background-color: #f8f9fa;
                                        font-weight: bold;
                                    }}
                                    
                                    .shipping-info {{
                                        background-color: #f8f9fa;
                                        padding: 20px;
                                        border-radius: 8px;
                                        margin-bottom: 30px;
                                    }}
                                    
                                    .shipping-info h3 {{
                                        color: #2c3e50;
                                        margin-bottom: 15px;
                                        font-size: 18px;
                                    }}
                                    
                                    .shipping-info p {{
                                        margin: 8px 0;
                                        font-size: 14px;
                                        line-height: 1.4;
                                    }}
                                    
                                    .footer {{
                                        text-align: center;
                                        margin-top: 30px;
                                        padding-top: 20px;
                                        border-top: 1px solid #eee;
                                    }}
                                    
                                    .footer p {{
                                        color: #7f8c8d;
                                        margin-bottom: 10px;
                                        font-size: 14px;
                                    }}
                                    
                                    .footer a {{
                                        color: #3498db;
                                        text-decoration: none;
                                        font-weight: 500;
                                    }}
                                </style>
                            </head>
                            <body>
                                <div class="email-container">
                                    <div class="header">
                                        <h1>Thank You for Your Order!</h1>
                                        <p>We're excited to process your order #{order.id}</p>
                                    </div>

                                    <div class="payment-section">
                                        <h2>Next Steps: Complete Your Payment</h2>
                                        <p>To complete your order, please send payment via E-transfer to:</p>
                                        <div class="email-highlight">
                                            <p>lei232lei91@gmail.com</p>
                                        </div>
                                        <div class="order-id-note">
                                            Please include Order ID #{order.id} in the transfer message
                                        </div>
                                    </div>

                                    <div class="order-summary">
                                        <h3>Order Summary</h3>
                                        <table class="order-table">
                                            <tr>
                                                <th>Item</th>
                                                <th>Size</th>
                                                <th class="text-center">Qty</th>
                                                <th class="text-right">Price</th>
                                            </tr>
                                            {items_html}
                                            <tr class="total-row">
                                                <td colspan="3" class="text-right">Total:</td>
                                                <td class="text-right">${order.total_price}</td>
                                            </tr>
                                        </table>
                                    </div>

                                    <div class="shipping-info">
                                        <h3>Shipping Information</h3>
                                        <p><strong>Name:</strong> {order.first_name} {order.last_name}</p>
                                        <p><strong>Address:</strong> {order.shipping_address}</p>
                                        <p><strong>City:</strong> {order.city}</p>
                                        <p><strong>ZIP Code:</strong> {order.zip_code}</p>
                                        <p><strong>Phone:</strong> {order.shipping_phone}</p>
                                    </div>

                                    <div class="footer">
                                        <p>Questions about your order?</p>
                                        <a href="mailto:lei23lei91@gmail.com">Contact us at lei23lei91@gmail.com</a>
                                    </div>
                                </div>
                            </body>
                            </html>
                        """
                    }
                    
                    email = resend.Emails.send(params)
                    logger.info(f"Guest order confirmation email sent to {order.shipping_email}")
            except Exception as email_error:
                logger.error(f"Error sending guest order confirmation email: {str(email_error)}")
                # Continue with the response even if email fails
            
            return Response({
                "message": "Order created successfully",
                "order": {
                    "id": order.id,
                    "status": order.status,
                    "total_price": str(order.total_price),
                    "shipping_address": order.shipping_address,
                    "shipping_phone": order.shipping_phone,
                    "shipping_email": order.shipping_email,
                    "first_name": order.first_name,
                    "last_name": order.last_name,
                    "zip_code": order.zip_code,
                    "city": order.city,
                    "created_at": order.created_at,
                    "items": order_items
                }
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
