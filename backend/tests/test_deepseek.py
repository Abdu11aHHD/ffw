import json
import httpx
import pytest
from app.config import Settings
from app.services.deepseek import DeepSeekService,ENDPOINT
from app.services.gemini import ExplanationContext,GroundedValue
from app.domain.rules import ReviewOutcome

def context():
    return ExplanationContext(values=[GroundedValue('متوسط السكر',168,'mg/dL')],period_days=14,outcome=ReviewOutcome.REVIEW_SUGGESTED)

def payload(**updates):
    out={'summary_ar':'متوسط السكر 168 mg/dL خلال 14 يومًا، ويمكن مناقشته في الموعد.',
         'observations':[{'text_ar':'المتوسط الموثّق 168 mg/dL.','metric_labels':['متوسط السكر']}],
         'questions_ar':['ما المعلومات الإضافية المفيدة لموعدي؟'],
         'limitations_ar':['الملخص وحده لا يحدد توقيت التغيرات خلال اليوم.']}
    out.update(updates);return out

def service(value=None,status=200,callback=None):
    def handle(request):
        if callback:callback(request)
        return httpx.Response(status,json={'choices':[{'finish_reason':'stop','message':{
            'content':json.dumps(value or payload(),ensure_ascii=False),'reasoning_content':'PRIVATE REASONING'}}]})
    return DeepSeekService(Settings(deepseek_api_key='test-key'),transport=httpx.MockTransport(handle))

def test_uses_official_endpoint_thinking_high_and_only_verified_structured_values():
    def check(request):
        assert str(request.url)==ENDPOINT
        body=json.loads(request.content)
        assert body['model']=='deepseek-flash'
        assert body['thinking']=={'type':'enabled'} and body['reasoning_effort']=='high'
        ctx=json.loads(body['messages'][1]['content'])
        assert set(ctx)=={'verified_values','period_days','outcome','missing','reference_findings'}
        assert 'filename' not in request.content.decode() and '%PDF' not in request.content.decode()
    out=service(callback=check).explain(context()).to_json()
    assert out['source']=='ai' and out['provider']=='deepseek'
    assert out['questions_ar'] and out['observations_ar']
    assert 'PRIVATE REASONING' not in json.dumps(out)

def test_fabricated_numbers_are_rejected():
    out=service(payload(summary_ar='متوسط السكر 999 mg/dL.')).explain(context())
    assert out.source.value=='local_template'
    assert '999' not in out.text

def test_unknown_metric_citations_are_rejected():
    out=service(payload(observations=[{'text_ar':'قيمة موثقة','metric_labels':['مؤشر غير موجود']}])).explain(context())
    assert out.source.value=='local_template'

@pytest.mark.parametrize('status',[401,402,429,500])
def test_provider_errors_are_explicit_and_never_fake_success(status):
    out=service(status=status).explain(context())
    assert out.source.value=='local_template' and out.fallback_reason_ar

def test_dosing_advice_is_rejected():
    out=service(payload(questions_ar=['هل أرفع جرعة الإنسولين؟'])).explain(context())
    assert out.source.value=='local_template'

def test_missing_key_does_not_call_network():
    out=DeepSeekService(Settings(deepseek_api_key='')).explain(context())
    assert out.source.value=='local_template'
