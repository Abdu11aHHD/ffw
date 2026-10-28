"""Regressions at the new UI/API integration and workflow persistence boundary."""
from copy import deepcopy
import json
from types import SimpleNamespace

from .conftest import upload
from app.config import Settings
from app.deps import memory_repo
from app.db.repository import ReviewConflictError
from app.domain.report_parser import ReportTextParser
from app.services.gemini import GeminiService


def test_event_links_open_inside_the_team_feature(client, patient_headers, report_pdf):
    report = upload(client, patient_headers, report_pdf).json()['report']
    status = client.get(f"/api/v1/reports/{report['id']}/status",headers=patient_headers).json()
    assert status['ready'] and not status['failed']
    notices = client.get('/api/v1/notifications',headers=patient_headers).json()['items']
    notice = next(n for n in notices if n['kind']=='report_ready')
    assert notice['link']==f"/my-profile/diabetes-journey/reports/{report['id']}"


def test_failed_report_cannot_be_submitted_for_review(client, patient_headers):
    rid = upload(client,patient_headers,b'%PDF-1.4\n' + b'x'*1024 + b'\n%%EOF').json()['report']['id']
    response = client.post('/api/v1/followups',headers=patient_headers,json={'report_id':rid,'reason_ar':'مراجعة'})
    assert response.status_code==400
    assert response.json()['detail']['code']=='report_not_ready'


def test_declining_metric_sharing_hides_report_details_from_reviewer(client,patient_headers,reviewer_headers,report_pdf):
    rid = upload(client,patient_headers,report_pdf).json()['report']['id']
    request = client.post('/api/v1/followups',headers=patient_headers,
        json={'report_id':rid,'reason_ar':'أريد المناقشة','include_metrics':False}).json()
    payload = client.get(f"/api/v1/reviewer/requests/{request['id']}",headers=reviewer_headers).json()
    assert not payload['shared_snapshot']['items']
    assert 'report' not in payload


def test_atomic_review_conflict_leaves_no_appointment_or_notice(client,patient_headers,reviewer_headers,report_pdf,monkeypatch):
    rid=upload(client,patient_headers,report_pdf).json()['report']['id']
    f=client.post('/api/v1/followups',headers=patient_headers,json={'report_id':rid,'reason_ar':'مراجعة'}).json()
    client.post(f"/api/v1/reviewer/requests/{f['id']}/start",headers=reviewer_headers)
    def conflict(*args): raise ReviewConflictError()
    monkeypatch.setattr(memory_repo(),'commit_review',conflict)
    response=client.post(f"/api/v1/reviewer/requests/{f['id']}/decide",headers=reviewer_headers,
        json={'decision':'review_required','note_ar':'للنقاش في الموعد'})
    assert response.status_code==409
    assert memory_repo().get_followup(f['id']).status.value=='under_review'
    assert memory_repo().appointment_for_followup(f['id']) is None
    notices=client.get('/api/v1/notifications',headers=patient_headers).json()['items']
    assert not any(n['kind'] in ('followup_decided','appointment_created') for n in notices)


def test_stale_review_commit_is_rejected(client,patient_headers,reviewer_headers,report_pdf):
    rid=upload(client,patient_headers,report_pdf).json()['report']['id']
    f=client.post('/api/v1/followups',headers=patient_headers,json={'report_id':rid,'reason_ar':'مراجعة'}).json()
    client.post(f"/api/v1/reviewer/requests/{f['id']}/start",headers=reviewer_headers)
    stale=deepcopy(memory_repo().get_followup(f['id']))
    assert client.post(f"/api/v1/reviewer/requests/{f['id']}/decide",headers=reviewer_headers,
        json={'decision':'review_required','note_ar':'موعد للنقاش'}).status_code==200
    try: memory_repo().commit_review(stale,stale.updated_at,None,[])
    except ReviewConflictError: pass
    else: raise AssertionError('stale decision overwrote completed review')
    assert len([a for a in memory_repo().appointments.values() if a.followup_id==f['id']])==1


def test_gemini_never_receives_original_pdf_or_source_identifiers(report_text):
    captured={}
    def generate_content(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text='{"glucose_unit":"mg/dL","fields":[]}')
    client=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    result=ReportTextParser().parse([report_text])
    GeminiService(Settings(gemini_api_key='test'),client=client).cross_check_extraction(result,b'%PDF-PRIVATE-PATIENT-NAME')
    content=json.dumps(captured['contents'])
    assert 'PRIVATE-PATIENT-NAME' not in content
    assert 'source_text' not in content
    assert '168' in content


def test_report_stays_processing_until_the_real_ai_call_finishes(report_pdf):
    from threading import Event, Thread
    from app.db.repository import InMemoryRepository,new_id,now_utc
    from app.db.models import ReportRecord,ReportStatus
    from app.domain.metrics import TargetProfile
    from app.services.report_service import ReportProcessor
    from app.services.gemini import Explanation,ExplanationSource
    entered,release=Event(),Event()
    class SlowAnalysis:
        configured=False
        def explain(self,ctx):
            entered.set();release.wait(5)
            return Explanation('ملخص اصطناعي',ExplanationSource.AI)
    repo=InMemoryRepository()
    r=ReportRecord(id=new_id(),user_id='patient',status=ReportStatus.PROCESSING,created_at=now_utc(),file_name='synthetic.pdf',file_size_bytes=len(report_pdf))
    repo.create_report(r)
    t=Thread(target=ReportProcessor(Settings(ai_provider='local'),gemini=SlowAnalysis()).process,
             args=(repo,r,report_pdf,TargetProfile.GENERAL_ADULT_T1_T2))
    t.start()
    try:
        assert entered.wait(5)
        stored=repo.get_report('patient',r.id)
        assert stored.status==ReportStatus.PROCESSING
        assert stored.ai_summary is None
    finally:
        release.set();t.join(5)
    assert repo.get_report('patient',r.id).ai_summary['source']=='ai'
