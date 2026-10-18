"""Read-only integrity checks for the shared historical job ledger."""
import json
from pathlib import Path
from urllib.parse import urlsplit

def main():
    root = Path(__file__).resolve().parent
    data = json.loads((root / 'jobs.json').read_text())
    assert data['schema_version'] == 1
    jobs = data['jobs']
    ids, urls = set(), set()
    for job in jobs:
        assert job['job_id'] not in ids, job['job_id']
        ids.add(job['job_id'])
        for url in [job['canonical_url'], *job['url_aliases']]:
            assert urlsplit(url).scheme == 'https', url
            assert url not in urls, 'Duplicate canonical/alias URL: ' + url
            urls.add(url)
        for field in ['employer', 'title', 'url', 'import_source', 'last_checked',
                      'published_compensation', 'verification', 'eligibility']:
            assert job.get(field), (job['job_id'], field)
        assert set(job['assessments']) == {'anup', 'meena'}
        assert job['report_history']['already_reported'] is True or job['report_history'].get('state') == 'pending_delivery'
    events = [json.loads(line) for line in (root / 'reported.jsonl').read_text().splitlines() if line.strip()]
    historical = set()
    for event in events:
        assert event['job_id'] in ids, event
        assert event['event'] in {'historically_reported', 'alert_delivered', 'correction'}
        if event['event'] == 'historically_reported':
            assert event['job_id'] not in historical
            historical.add(event['job_id'])
    expected_historical = {job['job_id'] for job in jobs if job['report_history']['already_reported'] is True}
    assert expected_historical <= historical or expected_historical <= {event['job_id'] for event in events}, 'Report coverage mismatch'
    for path in root.iterdir():
        if path.suffix in {'.md', '.json', '.jsonl', '.py'}:
            content = path.read_text()
            assert not any(c in content for c in ['\u2013', '\u2014', '\u2015']), path.name
    print(f'PASS: {len(jobs)} jobs, {len(events)} report events, {len(urls)} canonical/alias URLs; no duplicate IDs or broken event references')

if __name__ == '__main__':
    main()
