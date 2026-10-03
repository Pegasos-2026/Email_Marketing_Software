from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from app.accounts.models import UserProfile, UserRole


class AuthTests(APITestCase):
    def test_register_creates_user_and_profile(self):
        url = reverse('auth_register')
        response = self.client.post(url, {
            'username': 'new@example.com',
            'email': 'new@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'first_name': 'New',
            'last_name': 'User',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='new@example.com')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_login_with_email(self):
        User.objects.create_user(
            username='login@example.com',
            email='login@example.com',
            password='StrongPass123!',
        )
        url = reverse('login')
        response = self.client.post(url, {
            'email': 'login@example.com',
            'password': 'StrongPass123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)

    def test_first_user_gets_admin_role(self):
        user = User.objects.create_user(
            username='admin@example.com',
            email='admin@example.com',
            password='StrongPass123!',
        )
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.role, UserRole.ADMIN)
