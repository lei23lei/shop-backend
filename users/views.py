from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.hashers import make_password, check_password
from .models import User, PasswordResetToken, Cart, CartItem, Item, ItemSize
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
import os
from datetime import datetime, timedelta
import secrets
import resend
import logging
from django.db import models

logger = logging.getLogger(__name__)

class UserView(APIView):
    def get(self, request):
        return Response({"message": "Hello, World!"}, status=status.HTTP_200_OK)

class RegisterView(APIView):
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
            
            # Find user by email
            try:
                user = User.objects.get(email=data.get('email'))
            except User.DoesNotExist:
                return Response(
                    {"error": "Invalid email or password"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Check password
            if not check_password(data.get('password'), user.password):
                return Response(
                    {"error": "Invalid email or password"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
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
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

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
                    "from": "Peter's Shop <onboarding@resend.dev>",
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
                'item__details'
            )
            
            # Format the response
            items = []
            for cart_item in cart_items:
                item = cart_item.item
                items.append({
                    'id': cart_item.id,
                    'item': {
                        'id': item.id,
                        'name': item.name,
                        'price': str(item.price),
                        'description': item.description,
                        'images': [
                            {
                                'image_url': img.image_url,
                                'is_primary': img.is_primary,
                                'quality': img.quality
                            }
                            for img in item.images.filter(quality='low')
                        ],
                        'details': {
                            'color': item.details.color if hasattr(item, 'details') else None,
                            'detail': item.details.detail if hasattr(item, 'details') else None
                        }
                    },
                    'size': {
                        'id': cart_item.size.id,
                        'size': cart_item.size.size
                    },
                    'quantity': cart_item.quantity
                })
            
            return Response({
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
            
            # Check if item already exists in cart
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                item=item,
                size=size,
                defaults={'quantity': request.data['quantity']}
            )
            
            # If item exists, handle quantity based on add parameter
            if not created:
                if request.data.get('add', False):  # Default to False (replace)
                    cart_item.quantity += int(request.data['quantity'])
                else:
                    cart_item.quantity = int(request.data['quantity'])
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

