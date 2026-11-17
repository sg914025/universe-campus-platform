from datetime import timedelta
from decimal import Decimal
import uuid
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from .models import DemoTopUp
from .demo_payments import SALT
from 帖子.models import profile, recharge

class DemoPaymentTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('payment_test_user')
        self.other=get_user_model().objects.create_user('payment_other_user')
        self.person,_=profile.objects.get_or_create(user=self.user)
        self.person.balance=Decimal('3');self.person.save()
        self.client.force_login(self.user)
        self.url=reverse('campus:recharge')
    def data(self,amount='20.00'):
        return {'amount':amount,'method':'alipay','request_token':signing.dumps({'user':self.user.pk,'key':str(uuid.uuid4())},salt=SALT)}
    def order(self):
        self.client.post(self.url,self.data());return DemoTopUp.objects.get(user=self.user)
    def pay(self,order,action='pay',client=None):
        return (client or self.client).post(reverse('campus:demo-payment-complete',args=[order.pk]),{'action':action})
    def test_only_confirmed_payment_credits_once(self):
        data=self.data();self.client.post(self.url,data);self.client.post(self.url,data)
        self.assertEqual(DemoTopUp.objects.count(),1);order=DemoTopUp.objects.get()
        self.person.refresh_from_db();self.assertEqual(self.person.balance,3)
        self.pay(order);self.pay(order);self.pay(order,'cancel')
        self.person.refresh_from_db();order.refresh_from_db()
        self.assertEqual(self.person.balance,23);self.assertEqual(order.status,'paid')
        self.assertEqual(recharge.objects.filter(code=order.reference,status='approved').count(),1)
    def test_invalid_amounts_create_nothing(self):
        for amount in ['-1','0','500.01','20.001','NaN','Infinity','bad']:
            self.client.post(self.url,self.data(amount))
        self.assertFalse(DemoTopUp.objects.exists())
    def test_amount_and_method_cannot_be_replaced_on_checkout(self):
        order=self.order();self.client.post(reverse('campus:demo-payment-complete',args=[order.pk]),{'action':'pay','amount':'500','method':'wechat'})
        self.person.refresh_from_db();self.assertEqual(self.person.balance,23)
        order.refresh_from_db();self.assertEqual(order.method,'alipay')
    def test_form_token_bound_to_user_and_parameters(self):
        data=self.data();self.client.post(self.url,data);data['amount']='50';self.assertEqual(self.client.post(self.url,data).status_code,400)
        self.client.force_login(self.other);self.client.post(self.url,self.data());self.assertEqual(DemoTopUp.objects.count(),1)
    def test_other_user_cannot_view_or_confirm(self):
        order=self.order();self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('campus:demo-checkout',args=[order.pk])).status_code,404)
        self.assertEqual(self.pay(order).status_code,404)
    def test_cancel_failed_expired_orders_never_credit(self):
        for action in ['cancel','fail','expired']:
            self.client.post(self.url,self.data());order=DemoTopUp.objects.first()
            if action=='expired':DemoTopUp.objects.filter(pk=order.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
            else:self.pay(order,action)
            self.pay(order)
        self.person.refresh_from_db();self.assertEqual(self.person.balance,3);self.assertFalse(recharge.objects.exists())
    def test_balance_overflow_rolls_back_both_states(self):
        order=self.order();self.person.balance=Decimal('9999999999.99');self.person.save();self.pay(order)
        order.refresh_from_db();self.assertEqual(order.status,'pending');self.assertFalse(recharge.objects.exists())
    def test_confirm_requires_post_and_csrf(self):
        order=self.order();url=reverse('campus:demo-payment-complete',args=[order.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        client=Client(enforce_csrf_checks=True);client.force_login(self.user)
        self.assertEqual(client.post(url,{'action':'pay'}).status_code,403)
    @override_settings(DEMO_PAYMENTS_ENABLED=False)
    def test_demo_can_be_disabled(self):
        self.assertEqual(self.client.get(self.url).status_code,403)
    def test_topup_page_is_explicitly_simulated(self):
        self.assertContains(self.client.get(self.url),'不扣真钱')
    def test_forged_token_rejected(self):
        data=self.data();data['request_token']='forged';self.client.post(self.url,data);self.assertFalse(DemoTopUp.objects.exists())
