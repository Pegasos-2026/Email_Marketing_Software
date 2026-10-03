from django.contrib.auth.models import User
from rest_framework import generics,status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny,IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer,UserSerializer
from app.campaigns.utils import create_default_tags_for_user
class RegisterView(generics.CreateAPIView):
    queryset=User.objects.all()
    permission_classes=(AllowAny,)
    serializer_class=RegisterSerializer
    def create(self,request,*args,**kwargs):
        serializer=self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user=serializer.save()
        create_default_tags_for_user(user)
        refresh=RefreshToken.for_user(user)
        return Response({
            'user':{
                'username':user.username,
                'email':user.email,
                'first_name':user.first_name,
                'last_name':user.last_name,
            },
            'tokens':{
                'refresh':str(refresh),
                'access':str(refresh.access_token),
            },
            'message':'User created successfully'
        },status=status.HTTP_201_CREATED)
class UserProfileView(generics.RetrieveAPIView):
    permission_classes=[IsAuthenticated]
    serializer_class=UserSerializer
    def get_object(self):
        return self.request.user
class LoginView(APIView):
    permission_classes=[AllowAny]
    def post(self,request):
        email=request.data.get("email")
        password=request.data.get("password")
        if not email or not password:
            return Response({"error":"email and password are required"},status=status.HTTP_400_BAD_REQUEST)
        user=authenticate(email=email,password=password)
        if user is not None:
            refresh=RefreshToken.for_user(user)
            return Response({
                "user":{
                    "username":user.username,
                    "email":user.email,
                    "first_name":user.first_name,
                    "last_name":user.last_name,
                },
                "tokens":{
                    "refresh":str(refresh),
                    "access":str(refresh.access_token),
                },
                "message":"Login successful"
            },status=status.HTTP_200_OK)
        return Response({
            "error":"Invalid credentials"
        },status=status.HTTP_401_UNAUTHORIZED)
class LogoutView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request):
        refresh_token=request.data.get("refresh_token") or request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error":"refresh_token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            token=RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message":"Successfully logged out"},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {"error":str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )