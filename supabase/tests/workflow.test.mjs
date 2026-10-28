import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,readdirSync} from 'node:fs';
import {PGlite} from '@electric-sql/pglite';
import {randomUUID} from 'node:crypto';
const A='00000000-0000-4000-8000-00000000000a',B='00000000-0000-4000-8000-00000000000b';
let db;
before(async()=>{
 db=new PGlite();
 await db.exec(`create role anon nologin; create role authenticated nologin; create role service_role nologin bypassrls;
 create schema auth; create table auth.users(id uuid primary key,email text);
 create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
 grant usage on schema auth,public to anon,authenticated,service_role;
 grant execute on function auth.uid() to anon,authenticated,service_role;
 alter default privileges in schema public grant all on tables to anon,authenticated,service_role;
 alter default privileges in schema public grant all on functions to anon,authenticated,service_role;
 alter default privileges in schema public grant all on sequences to anon,authenticated,service_role;
 create schema storage;
 create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
 create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text,name text);
 alter table storage.objects enable row level security;
 create function storage.foldername(text) returns text[] language sql immutable as $$select (string_to_array($1,'/'))[1:array_length(string_to_array($1,'/'),1)-1]$$;`);
 const directory=new URL('../migrations/',import.meta.url);
 for(const f of readdirSync(directory).filter(x=>x.endsWith('.sql')).sort()) await db.exec(readFileSync(new URL(f,directory),'utf8'));
 await db.query('insert into auth.users(id,email) values($1,$2),($3,$4)',[A,'a@example.test',B,'b@example.test']);
});
after(async()=>{await db?.close();});
async function as(role,uid,fn){await db.query("select set_config('request.jwt.claim.sub',$1,false)",[uid??'']);await db.exec(`set role ${role}`);try{return await fn();}finally{await db.exec('reset role');}}
async function request(){
 const rid=randomUUID(),fid=randomUUID();
 await db.query(`insert into sukkar_reports(id,user_id,status,file_name,file_size_bytes) values($1,$2,'ready','synthetic.pdf',1000)`,[rid,A]);
 await db.query(`insert into followup_requests(id,user_id,report_id,trigger_type,rules_version,reason,shared_snapshot,status,idempotency_key,provenance)
 values($1,$2,$3,'user_request','test','reason','{}','under_review',$4,'synthetic')`,[fid,A,rid,randomUUID()]);
 const f=(await db.query('select * from followup_requests where id=$1',[fid])).rows[0];
 const aid=randomUUID(),at=new Date(Date.now()+1000).toISOString();
 return {fid,rid,aid,args:[JSON.stringify({...f,status:'reviewed',decision:'review_required',appointment_id:aid,updated_at:at}),f.updated_at,
 JSON.stringify({to_status:'reviewed',note:'approved',created_at:at}),JSON.stringify({body:'reason',author_label:'demo reviewer'}),
 JSON.stringify({id:aid,user_id:A,followup_id:fid,report_id:rid,scheduled_at:at,clinic_label:'محاكاة',specialty_ar:'متابعة'}),
 JSON.stringify([{id:randomUUID(),kind:'appointment_created',channel:'personal',title:'محاكاة',body:'synthetic',sender:'عضيد',dedupe_key:aid,created_at:at}])]};
}
const commit=args=>db.query('select public.adheed_commit_review($1::jsonb,$2::timestamptz,$3::jsonb,$4::jsonb,$5::jsonb,$6::jsonb)',args);
test('all four migrations apply and patient report RLS isolates users',async()=>{
 const f=await request();
 const own=await as('authenticated',A,()=>db.query('select id from sukkar_reports where id=$1',[f.rid]));assert.equal(own.rows.length,1);
 const other=await as('authenticated',B,()=>db.query('select id from sukkar_reports where id=$1',[f.rid]));assert.equal(other.rows.length,0);
 await assert.rejects(as('anon',null,()=>db.query('select id from sukkar_reports')),/permission denied/);
});
test('patients and anonymous callers cannot execute privileged review commits',async()=>{
 const f=await request();
 await assert.rejects(as('authenticated',A,()=>commit(f.args)),/permission denied/);
 await assert.rejects(as('anon',null,()=>commit(f.args)),/permission denied/);
});
test('approval persists decision, appointment, reason and notification once',async()=>{
 const f=await request();await as('service_role',null,()=>commit(f.args));
 const row=(await db.query('select status,appointment_id from followup_requests where id=$1',[f.fid])).rows[0];
 assert.equal(row.status,'reviewed');assert.equal(row.appointment_id,f.aid);
 assert.equal((await db.query('select * from appointments where followup_id=$1',[f.fid])).rows.length,1);
 assert.equal((await db.query('select * from review_notes where request_id=$1',[f.fid])).rows.length,1);
 await assert.rejects(as('service_role',null,()=>commit(f.args)),/ADHEED_CONFLICT/);
 assert.equal((await db.query('select * from appointments where followup_id=$1',[f.fid])).rows.length,1);
});
test('a failed notification insert rolls the entire approval back',async()=>{
 const f=await request();const notices=JSON.parse(f.args[5]);notices[0].kind='invalid';f.args[5]=JSON.stringify(notices);
 await assert.rejects(as('service_role',null,()=>commit(f.args)));
 assert.equal((await db.query('select status from followup_requests where id=$1',[f.fid])).rows[0].status,'under_review');
 assert.equal((await db.query('select * from appointments where followup_id=$1',[f.fid])).rows.length,0);
});
