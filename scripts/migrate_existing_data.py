"""Preview or back up and activate existing transcript/researcher histories.

The preview upgrades a temporary SQLite copy only. Apply requires its exact
plan hash. Existing current values must remain identical; no past authorship
is inferred. Recovery uses the existing verified backup/restore workflow.
"""
import argparse
from contextlib import closing,contextmanager
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests'),str(ROOT)]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--expected-plan')
    parser.add_argument('--backup-dir',type=Path)
    args=parser.parse_args()
    source=args.database.resolve();report=args.report.resolve()
    if not source.is_file() or not report.is_relative_to((ROOT/'output/validation').resolve()): parser.error('existing DB and validation report required')
    if args.apply and (not args.expected_plan or not args.backup_dir): parser.error('apply requires expected-plan and backup-dir')
    from gurumoji.analysis_core import fingerprint
    from gurumoji import transcript_preparation as history
    from gurumoji.services import change_log,data_backup
    from runtime_isolation import application_paths
    import app
    original={key:getattr(app,key) for key in application_paths(source.parent) if hasattr(app,key)}
    @contextmanager
    def exclusive_source():
        from gurumoji.services.instance_lock import InstanceLock
        lock=InstanceLock(lambda:[source.parent/app.DATA_INSTANCE_LOCK_FILE.name])
        if not lock.acquire():raise ValueError('Application is running on this data directory; cutover stopped')
        try:yield
        finally:lock.release()
    def rows(db): return [dict(row) for row in db.execute('SELECT * FROM library_items ORDER BY id')]
    def connection(path,readonly=False):
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) if readonly else sqlite3.connect(path)
        db.row_factory=sqlite3.Row;return db
    with closing(connection(source,True)) as db, tempfile.TemporaryDirectory(prefix='gurumoji-cutover-preview-') as temporary:
        before=rows(db);columns=list(before[0]) if before else []
        target=Path(temporary)/'library.sqlite3'
        with closing(connection(target)) as copy_db: db.backup(copy_db)
        try:
            for key,value in application_paths(temporary).items():
                if hasattr(app,key):setattr(app,key,value)
            app.DATABASE_FILE=target;app.initialize_library()
            with app.database_connection() as copy_db:
                after=[{key:row[key] for key in columns} for row in rows(copy_db)]
                if fingerprint(before)!=fingerprint(after): raise ValueError('Schema initialization would change existing current values; cutover stopped')
                plans=[{'item_id':row['id'],**{key:value for key,value in history.migration_dry_run(copy_db,row).items()
                    if key in {'status','version','source_hash','reason','raw_status'}}} for row in copy_db.execute('SELECT * FROM library_items ORDER BY id')]
                states=change_log.fix_initial_states(copy_db,dry_run=True)
                plan={'source_rows_hash':fingerprint(before),'conversation_count':len(before),'transcripts':plans,'researcher_histories':states}
                plan['plan_hash']=fingerprint(plan)
        finally:
            for key,value in original.items():setattr(app,key,value)
    result={'mode':'preview','plan':plan,'source_values_changed':False}
    if args.apply:
        if plan['plan_hash']!=args.expected_plan or any(row['status']=='conflict' for row in plans): raise ValueError('Plan changed or contains a conflict')
        app.DATABASE_FILE=source
        if args.backup_dir.resolve().is_relative_to(source.parent):raise ValueError('Backup must be outside the data directory')
        with exclusive_source(),app.library_write_lock:
            with closing(connection(source,True)) as db:
                if fingerprint(rows(db))!=plan['source_rows_hash']:raise ValueError('Source changed after preview')
            backup=data_backup.create_backup(source.parent,args.backup_dir.resolve(),include_media=False,app_version=app.APP_VERSION)
            if data_backup.verify_backup(backup['path']):raise ValueError('Backup integrity verification failed')
            app.initialize_library()
            with app.database_connection() as db:
                db.execute('BEGIN IMMEDIATE')
                for row in db.execute('SELECT * FROM library_items').fetchall():history.activate_changes(db,row)
                states=change_log.fix_initial_states(db,dry_run=False)
                after=[{key:row[key] for key in columns} for row in rows(db)]
                if fingerprint(before)!=fingerprint(after):raise ValueError('Current values changed during cutover')
                checks=[history.migration_dry_run(db,row)['status'] for row in db.execute('SELECT * FROM library_items')]
                if any(status!='already_active' for status in checks):raise ValueError('History replay did not verify')
            result.update(mode='applied',backup={**backup,'path':str(backup['path'])},researcher_histories=states)
            with app.database_connection() as db:result['journal_mode']=db.execute('PRAGMA journal_mode').fetchone()[0]
    report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'mode':result['mode'],'conversations':plan['conversation_count'],'plan_hash':plan['plan_hash'],
        'conflicts':sum(row['status']=='conflict' for row in plans),'source_values_changed':False},ensure_ascii=False))


if __name__=='__main__':main()
