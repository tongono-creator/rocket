import json
import pytest
import auto_affiliate as aa
from affiliate_recommendations import RecommendationReconciler
from test_auto_affiliate import FakeApi, config, post


def setup(tmp_path, api, publish=True):
    cfg = config()
    cfg.update(recommendation_count=2, recommendations_since='2026-09-21T00:00:00Z',
               recommendation_pool=[{'id': str(i), 'name': str(i), 'category': c,
                 'url': 'https://s.shopee.co.th/' + str(i)}
                 for i, c in enumerate(['clothing', 'phone', 'fragrance'])])
    state = aa.StateStore(tmp_path / 'state.json')
    return RecommendationReconciler('facebook', cfg, state, api, publish=publish), state


def test_two_different_categories_rotate_and_never_duplicate(tmp_path):
    api = FakeApi([post('p1'), post('p2')])
    runner, state = setup(tmp_path, api)
    assert runner.run()['comments_published'] == 4
    records = state.data['facebook']['acct-1']
    assert {s['product']['id'] for s in records['p1']['recommendations']} == {'0', '1'}
    assert '2' in {s['product']['id'] for s in records['p2']['recommendations']}
    runner.run()
    assert len(api.published) == 4


def test_dry_run_no_file_or_writes(tmp_path):
    api = FakeApi([post()])
    runner, state = setup(tmp_path, api, False)
    assert len(runner.run()['planned']) == 2
    assert not state.path.exists()
    assert not api.published


def test_second_slot_timeout_is_held_without_repeating_first(tmp_path):
    class TimeoutSecond(FakeApi):
        def publish_reply(self, pid, text):
            if len(self.published) == 1:
                self.published.append((pid, text))
                raise aa.ApiError('POST', 504)
            return super().publish_reply(pid, text)
    api = TimeoutSecond([post()])
    runner, state = setup(tmp_path, api)
    with pytest.raises(aa.ApiError):
        runner.run()
    with pytest.raises(aa.ReconciliationRequired):
        runner.run()
    assert len(api.published) == 2
    slots = state.data['facebook']['acct-1']['p1']['recommendations']
    assert [s['status'] for s in slots] == ['published', 'unknown']
    api.existing = {'p1': [{'id': 'recovered', 'author_id': 'acct-1', 'text': slots[1]['product']['url']}]}
    runner.run()
    assert len(api.published) == 2
    assert state.get('facebook', 'acct-1', 'p1')['status'] == 'published'


def test_existing_comments_and_pre_activation_posts_are_preserved(tmp_path):
    api = FakeApi([post('old', created='2026-09-20T01:00:00Z'), post('existing')],
                  existing={'existing': [{'id': 'r', 'author_id': 'acct-1', 'text': 'https://s.shopee.co.th/old'}]})
    runner, state = setup(tmp_path, api)
    runner.run()
    assert not api.published


def test_definite_rejection_only_retries_failed_slot(tmp_path):
    class RejectSecond(FakeApi):
        def publish_reply(self, pid, text):
            if len(self.published) == 1 and not getattr(self, 'rejected', False):
                self.rejected = True
                raise aa.ApiError('POST', 400)
            return super().publish_reply(pid, text)
    api = RejectSecond([post()])
    runner, state = setup(tmp_path, api)
    with pytest.raises(aa.ApiError):
        runner.run()
    runner.run()
    assert len(api.published) == 2
