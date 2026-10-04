"""Offline tests for preserving reviewed comments without a second writer."""
import copy
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
import auto_affiliate as worker


URL = 'https://s.shopee.co.th/offlinefixture'
COMMENT = 'โมเดลรถถังสำหรับผู้สนใจสะสม โปรดเช็กสเกลและอุปกรณ์ในชุดก่อนซื้อครับ\n'+URL+'\n\n'+worker.DISCLOSURE
PRODUCT = {'name':'Offline tank model','url':URL,'comment':COMMENT}
POST = {'id':'111830598532037_1032125096514417','aliases':['1032125096514417'],
        'text':'Turtle tank conceptual post','created_at':'2026-10-05T00:30:00Z','original':True,'published':True}
CONFIG = {'account_id':'111830598532037','rollout_since':'2026-09-27T02:40:00Z',
          'approved_fallback':{'name':'Legacy bicycle','url':'https://s.shopee.co.th/fallbackfixture'},
          'catalog':[], 'post_products':{POST['id']:PRODUCT}}


class FakeApi:
    def __init__(self,replies=None):
        self.replies = replies or []
        self.writes = []
    def get_identity(self):
        return {'id':'111830598532037','username':'Rocket21','aliases':[]}
    def iter_posts(self,since):
        return [POST]
    def iter_existing_replies(self,post_id):
        return self.replies
    def publish_reply(self,post_id,text):
        self.writes.append((post_id,text)); return 'real-looking-offline-id'
    def verify_reply(self,post_id,reply_id):
        return reply_id=='real-looking-offline-id'


class ContextualCommentTests(unittest.TestCase):
    def test_exact_custom_comment_survives_product_resolution(self):
        selection=worker.select_product(POST,CONFIG)
        self.assertEqual(selection.reason,'explicit')
        self.assertEqual(worker.build_comment(selection),COMMENT)

    def test_photo_alias_resolves_same_reviewed_comment(self):
        config={**CONFIG,'post_products':{'1032125096514417':PRODUCT}}
        self.assertEqual(worker.build_comment(worker.select_product(POST,config)),COMMENT)

    def test_missing_disclosure_rejected(self):
        with self.assertRaises(ValueError):
            worker.validate_product({**PRODUCT,'comment':'Book '+URL})

    def test_different_or_second_sales_link_rejected(self):
        for value in (COMMENT+'\nhttps://s.shopee.co.th/second',COMMENT.replace(URL,'https://s.shopee.co.th/wrong')):
            with self.assertRaises(ValueError):
                worker.validate_product({**PRODUCT,'comment':value})

    def test_legacy_product_comment_stays_unchanged(self):
        selection=worker.Selection({'name':'Legacy bicycle','url':'https://s.shopee.co.th/fallbackfixture'},'fallback')
        self.assertEqual(worker.build_comment(selection),'พิกัดสินค้าสำหรับผู้ติดตาม: Legacy bicycle — https://s.shopee.co.th/fallbackfixture\n\n'+worker.DISCLOSURE)

    def test_new_comment_written_once_with_reviewed_text(self):
        with tempfile.TemporaryDirectory() as directory:
            state=worker.StateStore(Path(directory)/'state.json'); api=FakeApi()
            reconcile=worker.AffiliateReconciler('facebook',CONFIG,state,api,publish=True,now=datetime(2026,10,5,tzinfo=timezone.utc))
            self.assertEqual(reconcile.run()['published'],1)
            reconcile.run()
            self.assertEqual(api.writes,[(POST['id'],COMMENT)])

    def test_existing_own_shopee_comment_is_not_duplicated_when_mapping_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            state=worker.StateStore(Path(directory)/'state.json')
            api=FakeApi([{'id':'old-comment','author_id':'111830598532037','text':'จักรยาน https://s.shopee.co.th/fallbackfixture'}])
            reconcile=worker.AffiliateReconciler('facebook',CONFIG,state,api,publish=True,now=datetime(2026,10,5,tzinfo=timezone.utc))
            self.assertEqual(reconcile.run()['existing'],1)
            self.assertEqual(api.writes,[])
            self.assertEqual(state.get('facebook',CONFIG['account_id'],POST['id'])['status'],'existing')

    def test_unknown_prior_write_without_live_comment_stays_held(self):
        with tempfile.TemporaryDirectory() as directory:
            state=worker.StateStore(Path(directory)/'state.json'); api=FakeApi()
            state.set('facebook',CONFIG['account_id'],POST['id'],'unknown')
            reconcile=worker.AffiliateReconciler('facebook',CONFIG,state,api,publish=True,now=datetime(2026,10,5,tzinfo=timezone.utc))
            with self.assertRaises(worker.ReconciliationRequired):
                reconcile.run()
            self.assertEqual(api.writes,[])

    def test_dry_run_does_not_write_remote_or_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'; api=FakeApi()
            reconcile=worker.AffiliateReconciler('facebook',CONFIG,worker.StateStore(path),api,publish=False,now=datetime(2026,10,5,tzinfo=timezone.utc))
            self.assertEqual(reconcile.run()['dry_run'],1)
            self.assertEqual(api.writes,[]); self.assertFalse(path.exists())

    def test_unmapped_post_waits_without_remote_write_or_consuming_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'; api=FakeApi()
            config={**CONFIG,'post_products':{},'require_explicit_mapping':True}
            result=worker.AffiliateReconciler('facebook',config,worker.StateStore(path),api,publish=True,now=datetime(2026,10,5,tzinfo=timezone.utc)).run()
            self.assertEqual(result['pending_product_missing'],1)
            self.assertEqual(api.writes,[]); self.assertFalse(path.exists())

    def test_keyword_hit_does_not_bypass_editor_mapping_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            api=FakeApi(); config={**CONFIG,'post_products':{},'require_explicit_mapping':True,
                'catalog':[{**PRODUCT,'keywords':['Turtle']}]}
            result=worker.AffiliateReconciler('facebook',config,worker.StateStore(Path(directory)/'state.json'),api,publish=True,now=datetime(2026,10,5,tzinfo=timezone.utc)).run()
            self.assertEqual(result['pending_product_missing'],1); self.assertEqual(api.writes,[])

    def test_reviewed_mapping_can_be_added_after_pending_run(self):
        with tempfile.TemporaryDirectory() as directory:
            api=FakeApi(); state=worker.StateStore(Path(directory)/'state.json')
            pending={**CONFIG,'post_products':{},'require_explicit_mapping':True}
            worker.AffiliateReconciler('facebook',pending,state,api,publish=True,now=datetime(2026,10,5,tzinfo=timezone.utc)).run()
            ready={**CONFIG,'require_explicit_mapping':True}
            result=worker.AffiliateReconciler('facebook',ready,state,api,publish=True,now=datetime(2026,10,5,tzinfo=timezone.utc)).run()
            self.assertEqual(result['published'],1); self.assertEqual(api.writes,[(POST['id'],COMMENT)])


if __name__=='__main__':
    unittest.main()
