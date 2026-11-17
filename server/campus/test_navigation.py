from django.test import SimpleTestCase, TestCase, RequestFactory
from django.urls import resolve, reverse
from django.contrib.auth.models import User
from django.utils import timezone
from campus.navigation import page_navigation
from campus.models import SecurityScan


class NavigationTests(SimpleTestCase):
    def nav(self, path, root=False):
        request = RequestFactory().get(path)
        request.resolver_match = resolve(request.path)
        request.user = User(is_superuser=root)
        return page_navigation(request)

    def test_contextual_returns_match_list_or_parent(self):
        cases = {
            '/forum/posts/12/edit/': '/forum/posts/12/',
            '/forum/posts/12/': '/forum/',
            '/forum/profile/edit/': '/forum/profile/',
            '/forum/profile/chat/12/': '/forum/profile/messages/',
            '/errands/12/': '/errands/', '/errands/new/': '/errands/',
            '/errands/questions/12/': '/errands/questions/',
            '/booking/venues/12/': '/booking/',
            '/campus-admin/venues/12/': '/campus-admin/bookings/',
            '/campus-admin/errands/12/': '/campus-admin/errands/',
            '/campus-admin/risks/12/': '/campus-admin/risks/',
            '/doctor/cases/12/': '/doctor/',
            '/doctor/drugs/aspirin/': '/doctor/drugs/',
            '/management/security/twin/': '/management/overview/',
            '/management/accounts/': '/management/overview/',
            '/management/audit/': '/management/overview/',
        }
        for path, parent in cases.items():
            with self.subTest(path=path):
                self.assertEqual(self.nav(path)['url'], parent)

    def test_home_has_no_redundant_return(self):
        self.assertIsNone(self.nav('/'))

    def test_booking_staff_returns_within_its_permissions(self):
        self.assertEqual(self.nav('/campus-admin/waitlist/')['url'],'/campus-admin/bookings/')
        self.assertEqual(self.nav('/campus-admin/bookings/')['url'],'/management/')

    def test_admin_return_respects_existing_roles(self):
        self.assertEqual(self.nav('/campus-admin/')['url'], '/management/')
        self.assertEqual(self.nav('/campus-admin/', True)['url'], '/management/overview/')

    def test_return_ignores_untrusted_query(self):
        self.assertEqual(self.nav('/errands/12/?next=https://example.com')['url'], '/errands/')

    def test_guide_retains_in_page_navigation(self):
        self.assertTrue(self.nav('/guide/')['guide'])


class UnifiedWorkspaceTests(TestCase):
    def test_workspace_contains_real_snapshot_and_twin(self):
        user = User.objects.create_superuser('unified_root', password='test-only')
        self.client.force_login(user)
        SecurityScan.objects.create(day=timezone.localdate(), score=72, coverage=75,
                                    checks=[], inventory={'backup_count': 3})
        response = self.client.get(reverse('staff-overview'))
        for value in ('运营与安全工作台', '运营总览', '72', 'security-twin-data',
                      reverse('security-risks'), reverse('security-database')):
            self.assertContains(response, value)
        self.assertEqual(response.context['latest'].score, 72)
        self.assertEqual(SecurityScan.objects.count(), 1)
        self.assertFalse(response.context['needs_scan'])
