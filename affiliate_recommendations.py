"""Two separately tracked recommendations for new Facebook posts only."""
from collections import Counter
from auto_affiliate import (AffiliateReconciler, Selection, ApiError,
    ReconciliationRequired, parse_since, validate_product, build_comment,
    select_product, affiliate_skip_reason, URL_RE)


class RecommendationReconciler(AffiliateReconciler):
    def run(self):
        account, own_ids, username = self._identity()
        cutoff = max(self.since, parse_since(self.config['recommendations_since']))
        limit = self.config['recommendation_count']
        if type(limit) is not int or not 1 <= limit <= 3:
            raise ValueError('recommendation_count must be 1–3')
        pool = self.config['recommendation_pool']
        ids = [p['id'] for p in pool]
        if len(set(ids)) != len(ids) or len({p['category'] for p in pool}) < limit:
            raise ValueError('Unique product IDs and enough different categories required')
        for p in pool:
            validate_product(p)
        records = self.state.data.get(self.platform, {}).get(account, {})
        usage = Counter()
        last = {}
        for record in records.values():
            for slot in record.get('recommendations', []):
                if slot.get('status') != 'failed':
                    usage[slot['product']['id']] += 1
                    last[slot['product']['id']] = max(last.get(slot['product']['id'], ''), record.get('updated_at', ''))
        counts, planned, held = Counter(), [], []
        posts = sorted(self.api.iter_posts(cutoff), key=lambda p: (p.get('created_at', ''), str(p['id'])))
        for post in posts:
            counts['scanned'] += 1
            if self._eligible(post, cutoff) or affiliate_skip_reason(post, self.config):
                counts['ineligible'] += 1
                continue
            pid = str(post['id'])
            prior = self.state.get(self.platform, account, pid)
            if prior and prior.get('status') in {'published', 'existing'}:
                counts['already_done'] += 1
                continue
            if prior and not prior.get('recommendations'):
                # Never reinterpret an unresolved legacy write as an empty post.
                held.append(pid)
                continue
            replies = list(self.api.iter_existing_replies(pid))
            own = [r for r in replies if str(r.get('author_id', '')) in own_ids
                   or (username and str(r.get('author_username', '')).casefold() == username.casefold())]
            slots = [dict(s) for s in (prior or {}).get('recommendations', [])]
            if not slots:
                if self._has_existing(replies, own_ids, username):
                    counts['existing'] += 1
                    if self.publish:
                        self.state.set(self.platform, account, pid, 'existing')
                    continue
                selection = select_product(post, self.config)
                if selection.reason == 'explicit':
                    products = [{**selection.product, 'id': 'explicit:' + pid, 'category': 'explicit'}]
                else:
                    products, categories = [], set()
                    for p in sorted(pool, key=lambda p: (usage[p['id']], last.get(p['id'], ''), p['id'])):
                        if p['category'] in categories:
                            continue
                        products.append(dict(p))
                        categories.add(p['category'])
                        if len(products) == limit:
                            break
                slots = [{'product': p, 'status': 'pending'} for p in products]
            blocked = False
            for slot in slots:
                product = slot['product']
                if slot['status'] == 'published':
                    continue
                # Exact URL recovery: another product's reply cannot complete this slot.
                found = next((r for r in own if product['url'] in URL_RE.findall(r.get('text', ''))), None)
                if found:
                    slot.update(status='published', reply_id=str(found['id']))
                    continue
                if slot['status'] in {'publishing', 'unknown'}:
                    blocked = True
                    held.append(pid)
                    break
                text = build_comment(Selection(validate_product(product), 'explicit' if 'comment' in product else 'fallback'))
                if not self.publish:
                    planned.append({'post_id': pid, 'product': product['name'], 'url': product['url'], 'comment': text})
                    usage[product['id']] += 1
                    last[product['id']] = post['created_at']
                    continue
                slot['status'] = 'publishing'
                self.state.set(self.platform, account, pid, 'partial', recommendations=slots)
                reply_id = ''
                try:
                    reply_id = self.api.publish_reply(pid, text)
                    slot['reply_id'] = reply_id
                    self.state.set(self.platform, account, pid, 'partial', recommendations=slots)
                    if not reply_id or not self.api.verify_reply(pid, reply_id):
                        raise ApiError('GET', 200, code='verification_failed')
                except Exception as exc:
                    slot['status'] = 'failed' if isinstance(exc, ApiError) and exc.rejected and not reply_id else 'unknown'
                    self.state.set(self.platform, account, pid, 'partial', recommendations=slots)
                    raise
                slot['status'] = 'published'
                self.state.set(self.platform, account, pid, 'partial', recommendations=slots)
                usage[product['id']] += 1
                last[product['id']] = post['created_at']
                counts['comments_published'] += 1
            if self.publish and not blocked:
                self.state.set(self.platform, account, pid, 'published', recommendations=slots)
                counts['posts_completed'] += 1
        result = {**counts, 'planned': planned}
        if held:
            raise ReconciliationRequired('Uncertain recommendation writes: ' + ', '.join(held))
        return result
