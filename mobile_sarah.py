from flask import Flask, request, render_template_string, jsonify
from openai import OpenAI
from collections import deque
from datetime import datetime, timezone
import base64
import os

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Temporary server memory: Render Free may clear this after sleeping/restarting.
call_reports = deque(maxlen=100)

SYSTEM = """Your name is Sarah. You are Khodor's personal work and maintenance assistant.
Speak to Khodor in natural everyday Lebanese Arabic. Understand Lebanese Arabic,
English and mixed Arabic-English. Be practical, concise and helpful with restaurant
maintenance, troubleshooting, planning, writing, and identifying photographed parts.
If Khodor requests a message to an English-speaking person, write natural English.
When asked to find a part or product, identify it carefully; distinguish a visual
match from confirmed compatibility, ask for model/part number when necessary, and
provide prices and purchase links only when you actually found them via web search.
Prepare a purchase list, but never buy, place orders, or make payments.
You have no access to Gmail, WhatsApp, private computer files or Google Sheets.
Never claim to have performed an action without a connected tool. Do not invent links.
"""

HTML = r'''<!doctype html>
<html lang="ar"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sarah</title>
<style>
*{box-sizing:border-box}body{font-family:Arial,sans-serif;max-width:740px;margin:0 auto;padding:14px;background:#f3f5f7;color:#17212b}
h1{text-align:center;margin:8px 0 14px}.box{background:white;border-radius:16px;padding:15px;margin-bottom:12px}
textarea{width:100%;min-height:95px;padding:12px;font-size:17px;border:1px solid #cbd5e1;border-radius:10px;resize:vertical}
button,.upload{font:inherit;border:0;border-radius:10px;padding:12px;background:#1966d2;color:white;cursor:pointer}
button:disabled{opacity:.55}button.secondary,.upload{background:#e8eef6;color:#15253b}
.controls{display:flex;gap:8px;flex-wrap:wrap;margin-top:9px}.controls>*{flex:1;min-width:90px;text-align:center}
#chat{white-space:pre-wrap;overflow-wrap:anywhere;direction:auto}.bubble{border-radius:12px;padding:11px;margin:9px 0;background:#edf3fb;white-space:pre-wrap;overflow-wrap:anywhere}
.bubble.me{background:#e8f5e9}.meta{font-size:12px;opacity:.7;margin-bottom:4px}
.report{border:1px solid #d4dce5;border-radius:10px;padding:10px;margin:8px 0;white-space:pre-wrap;overflow-wrap:anywhere;direction:auto}
small{display:block;margin:9px 0;color:#526070}#preview{max-width:100%;max-height:170px;display:none;margin:8px 0;border-radius:8px}
#status{font-size:13px;color:#445}details summary{cursor:pointer;font-weight:bold}
</style></head><body>
<h1>ساره 🎙️</h1>
<div class="box"><div id="chat" aria-live="polite"></div>
<textarea id="message" placeholder="احكي مع ساره أو ابعت صورة قطعة..."></textarea>
<img id="preview" alt="الصورة المختارة">
<input id="photo" type="file" accept="image/jpeg,image/png,image/webp,image/gif" hidden>
<div class="controls"><button class="secondary" id="mic" type="button">🎙️ احكي</button>
<label class="upload" for="photo">📷 صورة</label><button id="send" type="button">إبعث</button></div>
<div class="controls"><button class="secondary" id="speak" type="button">🔊 الرد بصوت: مطفّي</button>
<button class="secondary" id="clear" type="button">🗑️ محادثة جديدة</button></div>
<small id="status">الصوت بيعتمد على دعم المتصفح؛ إذا المايك ما اشتغل، استعمل مايك كيبورد الآيفون.</small></div>
<div class="box"><details open><summary>📞 تقارير المكالمات <span id="count"></span></summary>
<small>بيطلع تنبيه جوّا الصفحة لما يوصل تقرير جديد وهي مفتوحة. إشعارات الآيفون وهو مقفّل بدها إعداد Push منفصل.</small>
<div id="reports">ما في تقارير بهالجلسة.</div></details></div>
<script>
const $ = id => document.getElementById(id);
const CHAT_KEY='sarah_chat_v2', REPORT_KEY='sarah_reports_v2';
function load(key){try{return JSON.parse(localStorage.getItem(key)||'[]')}catch(e){return []}}
let chat=load(CHAT_KEY), reports=load(REPORT_KEY), photo=null, autoSpeak=false, busy=false;
function save(){localStorage.setItem(CHAT_KEY,JSON.stringify(chat.slice(-60)))}
function bubble(role,text){const d=document.createElement('div');d.className='bubble '+(role==='user'?'me':'');
 const m=document.createElement('div');m.className='meta';m.textContent=role==='user'?'إنت':'ساره';
 const t=document.createElement('div');t.textContent=text;d.append(m,t);$('chat').append(d)}
function renderChat(){$('chat').replaceChildren();chat.forEach(x=>bubble(x.role,x.content))}
function status(t){$('status').textContent=t}
function speak(text){if(!('speechSynthesis' in window))return;window.speechSynthesis.cancel();
 const u=new SpeechSynthesisUtterance(text);u.lang=/[\u0600-\u06ff]/.test(text)?'ar-LB':'en-US';u.rate=.95;
 const voices=window.speechSynthesis.getVoices();const v=voices.find(v=>v.lang.toLowerCase()==='ar-lb')||voices.find(v=>v.lang.startsWith('ar'));
 if(v&&u.lang==='ar-LB')u.voice=v;window.speechSynthesis.speak(u)}
$('speak').onclick=()=>{autoSpeak=!autoSpeak;$('speak').textContent='🔊 الرد بصوت: '+(autoSpeak?'شغّال':'مطفّي');if(!autoSpeak&&'speechSynthesis'in window)speechSynthesis.cancel()};
$('photo').onchange=()=>{photo=$('photo').files[0]||null;if(photo){$('preview').src=URL.createObjectURL(photo);$('preview').style.display='block';status('الصورة جاهزة للإرسال: '+photo.name)}else $('preview').style.display='none'};
$('clear').onclick=()=>{if(!confirm('نبلّش محادثة جديدة؟'))return;chat=[];save();renderChat();status('محادثة جديدة')};
function imageData(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file)})}
async function send(){if(busy)return;const text=$('message').value.trim();if(!text&&!photo)return;
 if(photo&&photo.size>8*1024*1024){status('الصورة أكبر من 8 MB. اختار صورة أصغر.');return}
 busy=true;$('send').disabled=true;status('ساره عم ترد...');let img=null;
 try{if(photo)img=await imageData(photo);const shown=text||'شو هيدي القطعة؟';
 const context=chat.slice(-10).map(x=>({role:x.role,content:x.content}));
 bubble('user',shown+(img?' 📷':''));
 const res=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text||'شو هيدي القطعة؟',image:img,history:context})});
 const data=await res.json();if(!res.ok)throw Error(data.error||'فشل الاتصال');
 chat.push({role:'user',content:shown+(img?' [صورة]':'')},{role:'assistant',content:data.answer});save();bubble('assistant',data.answer);
 if(autoSpeak)speak(data.answer);$('message').value='';$('photo').value='';photo=null;$('preview').style.display='none';status('جاهزة');
 }catch(e){bubble('assistant','صار خطأ: '+e.message);status('جرّب من جديد')}finally{busy=false;$('send').disabled=false}}
$('send').onclick=send;
$('message').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();send()}});
const SpeechRecognition=window.SpeechRecognition||window.webkitSpeechRecognition;
if(SpeechRecognition){const rec=new SpeechRecognition();rec.lang='ar-LB';rec.interimResults=false;rec.maxAlternatives=1;
 $('mic').onclick=()=>{try{rec.start();status('عم بسمعك...')}catch(e){status('المايك مش جاهز: '+e.message)}};
 rec.onresult=e=>{const said=e.results[0][0].transcript;$('message').value=said;status('سمعت: '+said+' — اكبس إبعث');};
 rec.onerror=e=>status('المايك: '+e.error+' — فيك تستعمل مايك الكيبورد');rec.onend=()=>{$('mic').disabled=false};
}else $('mic').onclick=()=>status('المتصفح ما بيدعم هالمايك. استعمل مايك كيبورد الآيفون.');
function renderReports(){$('count').textContent=reports.length?'('+reports.length+')':'';$('reports').replaceChildren();
 if(!reports.length){$('reports').textContent='ما في تقارير بهالجلسة.';return}
 reports.slice().reverse().forEach(r=>{const d=document.createElement('div');d.className='report';d.textContent=(r.received_at||'')+'\n'+r.message;$('reports').append(d)})}
async function poll(){try{const res=await fetch('/call-history',{cache:'no-store'});if(!res.ok)return;
 const data=await res.json();let changed=false;
 for(const r of data.reports||[]){if(!reports.some(old=>old.id===r.id)){reports.push(r);changed=true}}
 if(changed){reports=reports.slice(-100);localStorage.setItem(REPORT_KEY,JSON.stringify(reports));renderReports();status('📞 وصل تقرير مكالمة جديد');
 if(navigator.vibrate)navigator.vibrate(200)}
 }catch(e){}}
renderChat();renderReports();poll();setInterval(poll,15000);
</script></body></html>'''

@app.get('/')
def home():
    return render_template_string(HTML)

@app.post('/chat')
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get('message') or '').strip()[:4000]
    image = data.get('image')
    history = data.get('history') or []
    if not message and not image:
        return jsonify(error='اكتب رسالة أو اختار صورة'), 400
    content = [{'type': 'input_text', 'text': message or 'شو هيدي القطعة؟'}]
    if image:
        if not isinstance(image, str) or not image.startswith(('data:image/jpeg;base64,', 'data:image/png;base64,', 'data:image/webp;base64,', 'data:image/gif;base64,')) or len(image)>12_000_000:
            return jsonify(error='صيغة الصورة غير مدعومة أو حجمها كبير'), 400
        content.append({'type': 'input_image', 'image_url': image})
    inputs = []
    for item in history[-10:]:
        if isinstance(item, dict) and item.get('role') in ('user', 'assistant') and isinstance(item.get('content'), str):
            inputs.append({'role': item['role'], 'content': item['content'][:4000]})
    inputs.append({'role': 'user', 'content': content})
    wants_search = any(term in message.lower() for term in ('ابحث','بحث','دور','سعر','أسعار','شراء','اشتري','أمازون','amazon','buy','price','search','find','رابط','لينك'))
    try:
        kwargs = {'model': 'gpt-5.6-luna', 'instructions': SYSTEM, 'input': inputs, 'store': False}
        if wants_search:
            kwargs['tools'] = [{'type': 'web_search'}]
        response = client.responses.create(**kwargs)
        return jsonify(answer=response.output_text or 'ما قدرت جهّز جواب. جرّب من جديد.')
    except Exception as exc:
        app.logger.exception('Sarah chat failed')
        return jsonify(error='صار خطأ بالاتصال مع ساره. جرّب بعد شوي.'), 502

@app.post('/call-report')
def call_report():
    data = request.get_json(silent=True) or {}
    message = str(data.get('message') or 'No report received')[:10000]
    now = datetime.now(timezone.utc)
    call_reports.append({'id': now.isoformat() + '-' + str(len(call_reports)), 'message': message,
                         'received_at': now.strftime('%Y-%m-%d %H:%M UTC')})
    return jsonify(status='ok')

@app.get('/latest-call')
def latest_call():
    return jsonify(message=call_reports[-1]['message'] if call_reports else '')

@app.get('/call-history')
def call_history():
    return jsonify(reports=list(call_reports))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
