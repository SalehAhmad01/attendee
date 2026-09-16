from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

class AuthTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth-register')
        self.login_url = reverse('auth-login')
        self.refresh_url = reverse('auth-refresh')
        self.me_url = reverse('auth-me')

        self.user_data = {
            'email': 'student@geoqr.edu',
            'password': 'SecurePassword123!',
            'full_name': 'Test Student',
        }

    def test_1_register_valid_user(self):
        """Register with valid email + password -> 201, tokens returned"""
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], self.user_data['email'])
        self.assertEqual(response.data['user']['full_name'], self.user_data['full_name'])

        # Verify password is encrypted in database
        user = User.objects.get(email=self.user_data['email'])
        self.assertTrue(user.check_password(self.user_data['password']))
        self.assertNotEqual(user.password, self.user_data['password'])

    def test_2_register_duplicate_email(self):
        """Register with duplicate email -> 400"""
        User.objects.create_user(
            email=self.user_data['email'],
            password=self.user_data['password']
        )
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error']['code'], 'VALIDATION_ERROR')

    def test_3_login_correct_and_wrong_password(self):
        """Login with correct / wrong password -> 200 / 401"""
        User.objects.create_user(
            email=self.user_data['email'],
            password=self.user_data['password'],
            full_name=self.user_data['full_name']
        )

        # Correct credentials -> 200
        response = self.client.post(
            self.login_url,
            {'email': self.user_data['email'], 'password': self.user_data['password']},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], self.user_data['email'])

        # Wrong password -> 401
        wrong_response = self.client.post(
            self.login_url,
            {'email': self.user_data['email'], 'password': 'WrongPassword999'},
            format='json'
        )
        self.assertEqual(wrong_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', wrong_response.data)
        self.assertEqual(wrong_response.data['error']['code'], 'INVALID_CREDENTIALS')

    def test_token_refresh(self):
        """Refresh token generates new access token"""
        reg_response = self.client.post(self.register_url, self.user_data, format='json')
        refresh_token = reg_response.data['refresh']

        ref_response = self.client.post(self.refresh_url, {'refresh': refresh_token}, format='json')
        self.assertEqual(ref_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', ref_response.data)

    def test_me_endpoint(self):
        """Authenticated user can fetch profile, unauthenticated receives 401"""
        # Unauthenticated
        unauth_response = self.client.get(self.me_url)
        self.assertEqual(unauth_response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticated
        user = User.objects.create_user(
            email='alice@geoqr.edu',
            password='Password123!',
            full_name='Alice Smith'
        )
        self.client.force_authenticate(user=user)
        auth_response = self.client.get(self.me_url)
        self.assertEqual(auth_response.status_code, status.HTTP_200_OK)
        self.assertEqual(auth_response.data['user']['email'], 'alice@geoqr.edu')
        self.assertEqual(auth_response.data['user']['full_name'], 'Alice Smith')
