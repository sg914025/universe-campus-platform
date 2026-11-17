# Author: UniVerse Team. SQLite concurrency regression checks; isolated Django test database only.
import sqlite3,threading
from unittest.mock import patch
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.db import connection,OperationalError
from django.urls import reverse
from accounts.models import StudentImportBatch
from accounts import student_import
from campus.models import StaffAuditEvent
class StudentImportLockTests(TransactionTestCase):
 def setUp(self):
  self.root=User.objects.create_superuser('lock-test-root',password='Test-Root!731')
  self.rows=[{'student_number':'20990001','full_name':'测试同学甲','gender':'other','age':18},{'student_number':'20990002','full_name':'测试同学乙','gender':'other','age':19}]
  self.batch=StudentImportBatch.objects.create(created_by=self.root,original_filename='lock-test.csv',preview_rows=self.rows,total_count=2)
 def test_hashing_is_outside_transaction_and_repeated_confirmation_is_safe(self):
  states=[]
  def hashed(raw):states.append(connection.in_atomic_block);return make_password(raw)
  with patch('django.contrib.auth.hashers.make_password',side_effect=hashed):batch,users,skipped,repeated=student_import.confirm_batch(self.batch.pk,self.root)
  self.assertEqual(states,[False,False]);self.assertEqual(len(users),2);password=users[0].password
  with patch('django.contrib.auth.hashers.make_password',side_effect=AssertionError('must not rehash')):_,created,_,repeated=student_import.confirm_batch(self.batch.pk,self.root)
  self.assertTrue(repeated);self.assertEqual(created,[]);self.assertEqual(User.objects.get(username='20990001').password,password);self.assertEqual(StaffAuditEvent.objects.filter(action='确认导入学生账号').count(),1)
 def test_rollback_then_retry_does_not_leave_partial_students(self):
  original=student_import.import_students;calls=[]
  def fail_once(*args,**kw):
   result=original(*args,**kw);calls.append(1)
   if len(calls)==1:raise OperationalError('database is locked')
   return result
  with patch.object(student_import,'import_students',side_effect=fail_once):_,users,_,_=student_import.confirm_batch(self.batch.pk,self.root)
  self.assertEqual(len(calls),2);self.assertEqual(len(users),2);self.assertEqual(User.objects.filter(username__in=['20990001','20990002']).count(),2)
 def test_real_concurrent_sqlite_writer_is_retried(self):
  if connection.vendor!='sqlite':self.skipTest('SQLite specific')
  locked=threading.Event();errors=[];calls=[];original=student_import._commit_batch
  def writer():
   try:
    other=sqlite3.connect(connection.settings_dict['NAME'],uri=True,timeout=1)
    other.execute('BEGIN IMMEDIATE');other.execute('UPDATE accounts_studentimportbatch SET status=status WHERE id=?',(self.batch.pk,));locked.set()
    threading.Event().wait(.15);other.commit();other.close()
   except BaseException as error:errors.append(error);locked.set()
  thread=threading.Thread(target=writer)
  def commit(*args,**kw):
   calls.append(1)
   if len(calls)==1:thread.start();self.assertTrue(locked.wait(2))
   return original(*args,**kw)
  try:
   with patch.object(student_import,'_commit_batch',side_effect=commit):_,users,_,_=student_import.confirm_batch(self.batch.pk,self.root)
  finally:thread.join(3)
  self.assertFalse(errors);self.assertEqual(len(users),2);self.assertGreaterEqual(len(calls),2)
 def test_busy_failure_is_friendly_and_keeps_preview(self):
  self.client.force_login(self.root)
  with patch.object(student_import,'_commit_batch',side_effect=OperationalError('database is locked')),patch('time.sleep'):
   response=self.client.post(reverse('student-import-confirm',args=[self.batch.pk]))
  self.assertEqual(response.status_code,302);self.assertIn('preview=',response.url);self.batch.refresh_from_db();self.assertEqual(self.batch.status,'preview');self.assertFalse(User.objects.filter(username='20990001').exists())
