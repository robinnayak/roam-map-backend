from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User

from .constants import CHECKLIST_CATEGORY_ORDER
from .models import PackingItem


class ChecklistApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='checklist@example.com',
            password='password123',
            first_name='Checklist',
        )
        self.other_user = User.objects.create_user(
            email='other-checklist@example.com',
            password='password123',
            first_name='Other',
        )

    def authenticate(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {str(RefreshToken.for_user(user).access_token)}'
        )

    def test_seed_endpoint_populates_defaults_only_once(self):
        self.authenticate(self.user)

        first_response = self.client.post('/api/v1/checklist/seed/')
        second_response = self.client.post('/api/v1/checklist/seed/')

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertTrue(first_response.data['seeded'])
        self.assertFalse(second_response.data['seeded'])

        items = PackingItem.objects.filter(user=self.user)
        self.assertTrue(items.exists())
        required_categories = CHECKLIST_CATEGORY_ORDER[:8]
        for category in required_categories:
            self.assertGreaterEqual(items.filter(category=category).count(), 3)

    def test_get_returns_only_current_user_items_grouped_by_category(self):
        PackingItem.objects.create(
            user=self.user,
            category='Safety',
            name='Whistle',
            sort_order=1,
            is_default=True,
        )
        PackingItem.objects.create(
            user=self.user,
            category='Safety',
            name='Headlamp',
            sort_order=2,
            is_checked=True,
        )
        PackingItem.objects.create(
            user=self.other_user,
            category='Safety',
            name='Other user item',
            sort_order=1,
        )

        self.authenticate(self.user)
        response = self.client.get('/api/v1/checklist/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 2)
        self.assertEqual(response.data['packed_count'], 1)
        self.assertEqual(len(response.data['categories']), 1)
        self.assertEqual(response.data['categories'][0]['category'], 'Safety')
        self.assertEqual(len(response.data['categories'][0]['items']), 2)

    def test_create_item_assigns_next_sort_order_for_category(self):
        PackingItem.objects.create(
            user=self.user,
            category='Food and Water',
            name='Water bottle',
            sort_order=1,
        )

        self.authenticate(self.user)
        response = self.client.post(
            '/api/v1/checklist/',
            {
                'name': 'Electrolyte mix',
                'category': 'Food and Water',
                'note': 'One sachet per day',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['sort_order'], 2)
        self.assertEqual(response.data['name'], 'Electrolyte mix')

    def test_patch_and_delete_are_scoped_to_the_authenticated_user(self):
        item = PackingItem.objects.create(
            user=self.user,
            category='Medical',
            name='First aid kit',
            sort_order=1,
            note='Refill before trek',
        )
        other_item = PackingItem.objects.create(
            user=self.other_user,
            category='Medical',
            name='Other kit',
            sort_order=1,
        )

        self.authenticate(self.user)
        patch_response = self.client.patch(
            f'/api/v1/checklist/{item.id}/',
            {'is_checked': True, 'note': 'Packed and sealed'},
            format='json',
        )
        forbidden_response = self.client.patch(
            f'/api/v1/checklist/{other_item.id}/',
            {'is_checked': True},
            format='json',
        )
        delete_response = self.client.delete(f'/api/v1/checklist/{item.id}/')

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertEqual(forbidden_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(PackingItem.objects.filter(id=item.id).exists())

    def test_reset_unchecks_only_the_current_users_items(self):
        PackingItem.objects.create(
            user=self.user,
            category='Documents',
            name='Permit',
            sort_order=1,
            is_checked=True,
        )
        PackingItem.objects.create(
            user=self.user,
            category='Electronics',
            name='Phone',
            sort_order=1,
            is_checked=True,
        )
        PackingItem.objects.create(
            user=self.other_user,
            category='Electronics',
            name='Satellite device',
            sort_order=1,
            is_checked=True,
        )

        self.authenticate(self.user)
        response = self.client.post('/api/v1/checklist/reset/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['reset_count'], 2)
        self.assertEqual(response.data['checklist']['packed_count'], 0)
        self.assertFalse(PackingItem.objects.filter(user=self.user, is_checked=True).exists())
        self.assertTrue(PackingItem.objects.filter(user=self.other_user, is_checked=True).exists())

