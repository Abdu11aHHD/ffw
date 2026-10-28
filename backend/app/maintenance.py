"""Explicit report-file retention job. Preview by default; --apply deletes expired files."""
import argparse
from datetime import timedelta
from .config import get_settings
from .db.repository import now_utc

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    settings=get_settings()
    if not settings.supabase_configured:
        raise SystemExit('Supabase is not configured; no files were changed.')
    from supabase import create_client
    client=create_client(settings.supabase_url,settings.supabase_service_role_key)
    cutoff=(now_utc()-timedelta(days=settings.report_retention_days)).isoformat()
    # Limited batches, no report contents, patient identities or object paths in output.
    rows=client.table('sukkar_reports').select('id,storage_path').lt('created_at',cutoff).not_.is_('storage_path','null').limit(100).execute().data or []
    print(f'Expired stored files in this batch: {len(rows)}; mode: {"apply" if args.apply else "preview"}')
    if args.apply:
        for row in rows:
            client.storage.from_(settings.supabase_reports_bucket).remove([row['storage_path']])
            client.table('sukkar_reports').update({'storage_path':None}).eq('id',row['id']).execute()
    else: print('Use --apply to remove these stored PDFs. Analysis records are retained.')

if __name__=='__main__': main()
