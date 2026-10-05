"""Offline same-ID rescheduling safety. No real API, credentials or Root keys."""
import base64
import copy
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
import facebook_card_update as shared
import facebook_post_reschedule as scheduler
import affiliate_post_policy as affiliate


class Fake:
 def __init__(self,root,post):self.root=root;self.value=copy.deepcopy(post);self.calls=[];self.error=None;self.change_content=False
 def identity(self):return {'id':'111','name':'Fixture'}
 def post(self,id):return copy.deepcopy(self.value)
 def request(self,method,id,**kwargs):
  assert shared.read(self.root/'design_revision/reschedule_ledger.json')[id]['state']=='reserved'
  self.calls.append((method,id,kwargs))
  if self.error:raise self.error
  self.value['scheduled_publish_time']=int(kwargs['data']['scheduled_publish_time'])
  if self.change_content:self.value['message']='Unexpected changed content'
  return {'success':True}


class Reschedule(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.now=datetime.now(timezone.utc);self.key=Ed25519PrivateKey.generate()
  self.channel={'platform':'facebook','page_id':'111','name':'Fixture','editor_public_key':self.key.public_key().public_bytes(Encoding.PEM,PublicFormat.SubjectPublicKeyInfo).decode()}
  self.post={'id':'111_222','from':{'id':'111'},'message':'Unchanged caption','is_published':False,
   'scheduled_publish_time':int((self.now+timedelta(days=2)).timestamp()),'attachments':{'data':[{'type':'photo','target':{'id':'333'}}]}}
  inventory=self.root/'design_revision/inventory.json';shared.atomic(inventory,[{'post_id':'111_222','channel':'kram_fb','kind':'root_signed_native_release'}])
  self.payload={'action':'reschedule_unpublished_same_photo_post','channel':'kram_fb','page_id':'111','page_name':'Fixture','post_id':'111_222',
   'reviewed_at':self.now.isoformat(),'before':shared.snapshot(self.post,'111'),'after_schedule':{'present':True,'value':int((self.now+timedelta(days=30)).timestamp())},
   'inventory_sha256':shared.sha(inventory.read_bytes()),'root_monthly_plan_confirmed':True}
  self.digest=shared.sha(shared.canonical(self.payload));self.api=Fake(self.root,self.post)
 def signed(self):
  digest=shared.sha(shared.canonical(self.payload))
  return {'payload':self.payload,'payload_sha256':digest,'root_signature':base64.b64encode(self.key.sign(digest.encode())).decode()}
 def run_plan(self,mode='apply',sync=None):return scheduler.reschedule(self.payload,self.digest,self.channel,self.root,self.api,mode,sync)
 def test_signed_plan_binds_after_schedule_and_known_card_inventory(self):
  scheduler.verify_plan(self.signed(),'kram_fb',self.channel,self.root,self.now)
  plan=self.signed();plan['payload']['after_schedule']['value']+=3600
  with self.assertRaises(shared.UpdateError):scheduler.verify_plan(plan,'kram_fb',self.channel,self.root,self.now)
  self.payload['post_id']='111_999';self.payload['before']['post_id']='111_999'
  with self.assertRaises(shared.UpdateError):scheduler.verify_plan(self.signed(),'kram_fb',self.channel,self.root,self.now)
 def test_dry_run_is_get_only_and_no_ledger(self):
  self.assertEqual(self.run_plan('audit')['external_writes_this_run'],0)
  self.assertEqual(self.api.calls,[]);self.assertFalse((self.root/'design_revision/reschedule_ledger.json').exists())
 def test_schedule_only_post_preserves_caption_photo_and_same_id(self):
  synced=[]
  def sync(root,paths):synced.append(shared.read(paths[0])['111_222']['state'])
  result=self.run_plan(sync=sync)
  self.assertEqual(result['status'],'verified');self.assertEqual(synced,['reserved','verified'])
  self.assertEqual(self.api.calls,[('POST','111_222',{'data':{'scheduled_publish_time':str(self.payload['after_schedule']['value'])}})])
  self.assertEqual(self.api.value['message'],self.post['message']);self.assertEqual(self.api.value['attachments'],self.post['attachments'])
  self.assertFalse(self.api.value['is_published'])
 def test_published_and_video_posts_rejected_without_write(self):
  for mutation in ['published','video']:
   self.api.value=copy.deepcopy(self.post)
   if mutation=='published':self.api.value['is_published']=True
   else:self.api.value['attachments']['data'][0]['type']='video'
   with self.subTest(mutation=mutation),self.assertRaises(shared.UpdateError):self.run_plan()
   self.assertEqual(self.api.calls,[])
 def test_timeout_never_retries_and_ui_slot_reconcile_is_get_only(self):
  self.api.error=shared.UpdateError('timeout',ambiguous=True)
  with self.assertRaises(shared.UpdateError):self.run_plan()
  self.assertEqual(self.run_plan()['status'],'held_reschedule_reconcile_required');self.assertEqual(len(self.api.calls),1)
  self.api.value['scheduled_publish_time']=self.payload['after_schedule']['value']
  result=self.run_plan('reconcile');self.assertEqual(result['status'],'verified_reconciled');self.assertEqual(result['external_writes_this_run'],0)
  self.assertEqual(len(self.api.calls),1)
 def test_known_4xx_and_mismatched_readback_hold_without_retry(self):
  self.api.error=shared.UpdateError('rejected',400,100)
  with self.assertRaises(shared.UpdateError):self.run_plan()
  self.assertEqual(self.run_plan()['status'],'held_reschedule_reconcile_required');self.assertEqual(len(self.api.calls),1)
 def test_content_changed_by_platform_is_not_a_verified_reschedule(self):
  self.api.change_content=True
  with self.assertRaises(shared.UpdateError):self.run_plan()
  self.assertEqual(shared.read(self.root/'design_revision/reschedule_ledger.json')['111_222']['state'],'unknown')
 def test_changed_live_before_or_durable_push_failure_prevents_post(self):
  self.api.value['message']='Another editor changed this'
  with self.assertRaises(shared.UpdateError):self.run_plan()
  self.assertEqual(self.api.calls,[])
  self.api.value=copy.deepcopy(self.post)
  def fail(root,paths):raise RuntimeError('private remote response')
  with self.assertRaises(shared.UpdateError) as error:self.run_plan(sync=fail)
  self.assertNotIn('private',str(error.exception));self.assertEqual(self.api.calls,[])
 def test_apply_window_and_root_monthly_review_required(self):
  self.payload['root_monthly_plan_confirmed']=False
  with self.assertRaises(shared.UpdateError):scheduler.verify_plan(self.signed(),'kram_fb',self.channel,self.root,self.now)
  self.payload['root_monthly_plan_confirmed']=True
  for delta in [5/1440,61]:
   self.payload['after_schedule']['value']=int((self.now+timedelta(days=delta)).timestamp())
   with self.assertRaises(shared.UpdateError):scheduler.verify_plan(self.signed(),'kram_fb',self.channel,self.root,self.now)


class SelectedAffiliate(unittest.TestCase):
 def setUp(self):self.cfg={'account_id':'111','affiliate_mode':'selected_only','monthly_sales_limit':2,
  'selected_affiliate_posts':{'2026-10':['111_222']},'post_products':{'111_222':{'affiliate_enabled':True,'name':'Root reviewed fixture','url':'https://s.shopee.co.th/fixture'}}}
 def test_unselected_posts_skip_even_with_old_mapping_or_keywords(self):
  self.cfg['post_products']['111_333']={'affiliate_enabled':True}
  self.assertEqual(affiliate.affiliate_skip_reason({'id':'111_333','text':'many matching keywords'},self.cfg),'affiliate_not_selected')
 def test_selected_requires_explicit_root_enabled_mapping_and_optout_wins_alias(self):
  self.assertIsNone(affiliate.affiliate_skip_reason({'id':'111_222'},self.cfg))
  self.cfg['post_products']['111_222'].pop('affiliate_enabled')
  self.assertEqual(affiliate.affiliate_skip_reason({'id':'111_222'},self.cfg),'affiliate_reviewed_mapping_missing')
  self.cfg['post_products']['111_222']['affiliate_enabled']=True;self.cfg['post_products']['222']={'affiliate_enabled':False}
  self.assertEqual(affiliate.affiliate_skip_reason({'id':'111_222'},self.cfg),'affiliate_explicit_opt_out')
 def test_zero_sales_almost_and_monthly_max_two(self):
  self.cfg.update(monthly_sales_limit=0,selected_affiliate_posts={'2026-10':[]})
  self.assertEqual(affiliate.affiliate_skip_reason({'id':'111_222'},self.cfg),'affiliate_not_selected')
  self.cfg['selected_affiliate_posts']['2026-10']=['111_222']
  with self.assertRaises(ValueError):affiliate.affiliate_skip_reason({'id':'111_222'},self.cfg)
 def test_legacy_and_crosspage_duplicate_policy(self):
  self.assertIsNone(affiliate.affiliate_skip_reason({'id':'111_222'},{'account_id':'111'}))
  for groups in [{'2026-10':['999_222']},{'2026-10':['111_222'],'2026-11':['111_222']}]:
   self.cfg['selected_affiliate_posts']=groups
   with self.assertRaises(ValueError):affiliate.validate_affiliate_policy(self.cfg)


if __name__=='__main__':unittest.main()
