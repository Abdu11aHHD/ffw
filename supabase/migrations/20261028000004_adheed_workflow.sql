-- Python report IDs must reference Python report records, not legacy Flutter rows.
alter table public.followup_requests drop constraint if exists followup_requests_report_id_fkey;
alter table public.followup_requests add constraint followup_requests_report_id_fkey
  foreign key (report_id) references public.sukkar_reports(id) on delete set null;
alter table public.appointments add constraint appointments_report_id_fkey
  foreign key (report_id) references public.sukkar_reports(id) on delete set null;
alter table public.appointments add constraint appointments_followup_id_fkey
  foreign key (followup_id) references public.followup_requests(id) on delete set null;

-- Python validates the transition and builds the decision, appointment and notices.
-- This service-role-only RPC persists them in one database transaction, with a
-- row lock and revision check: a retry cannot create another appointment.
create or replace function public.adheed_commit_review(
  p_request jsonb, p_expected_at timestamptz, p_history jsonb, p_note jsonb,
  p_appointment jsonb, p_notifications jsonb
) returns void language plpgsql security definer set search_path = public as $$
declare current_request public.followup_requests; n jsonb; uid uuid; rid uuid;
begin
  rid := (p_request->>'id')::uuid;
  select * into current_request from public.followup_requests where id = rid for update;
  if not found or current_request.status <> 'under_review' or current_request.updated_at <> p_expected_at then
    raise exception 'ADHEED_CONFLICT' using errcode = '40001';
  end if;
  uid := current_request.user_id;
  if (p_request->>'user_id')::uuid <> uid then raise exception 'owner_mismatch'; end if;
  if p_request->>'status' not in ('reviewed', 'more_info_requested')
     or p_request->>'decision' not in ('review_required','data_completion','no_further_action_demo') then
    raise exception 'invalid_decision';
  end if;
  if (p_request->>'decision' = 'review_required') <> (p_appointment is not null and p_appointment <> 'null'::jsonb) then
    raise exception 'appointment_decision_mismatch';
  end if;
  if p_appointment is not null and p_appointment <> 'null'::jsonb then
    if (p_appointment->>'user_id')::uuid <> uid or (p_appointment->>'followup_id')::uuid <> rid then
      raise exception 'appointment_owner_mismatch';
    end if;
    insert into public.appointments (id,user_id,scheduled_at,clinic_label,specialty_ar,is_simulated,status,source,followup_id,report_id,provenance)
    values ((p_appointment->>'id')::uuid, uid, (p_appointment->>'scheduled_at')::timestamptz,
      p_appointment->>'clinic_label',p_appointment->>'specialty_ar',true,'upcoming','prototype',rid,
      (p_appointment->>'report_id')::uuid,'synthetic');
  end if;
  update public.followup_requests set status=p_request->>'status', decision=p_request->>'decision',
    appointment_id=(p_request->>'appointment_id')::uuid, updated_at=(p_request->>'updated_at')::timestamptz where id=rid;
  insert into public.followup_status_history(request_id,from_status,to_status,actor_role,note,created_at)
    values(rid,'under_review',p_history->>'to_status','reviewer',p_history->>'note',(p_history->>'created_at')::timestamptz);
  if p_note is not null and p_note <> 'null'::jsonb then
    insert into public.review_notes(request_id,body,author_label,created_at)
      values(rid,p_note->>'body',p_note->>'author_label',(p_request->>'updated_at')::timestamptz);
  end if;
  for n in select * from jsonb_array_elements(p_notifications) loop
    insert into public.notifications(id,user_id,kind,channel,title,body,sender,link,dedupe_key,created_at)
      values((n->>'id')::uuid,uid,n->>'kind',n->>'channel',n->>'title',n->>'body',n->>'sender',n->>'link',n->>'dedupe_key',(n->>'created_at')::timestamptz)
      on conflict do nothing;
  end loop;
end;
$$;
revoke all on function public.adheed_commit_review(jsonb,timestamptz,jsonb,jsonb,jsonb,jsonb) from public, anon, authenticated;
grant execute on function public.adheed_commit_review(jsonb,timestamptz,jsonb,jsonb,jsonb,jsonb) to service_role;
