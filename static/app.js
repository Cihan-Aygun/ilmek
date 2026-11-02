'use strict';
const $ = s => document.querySelector(s);
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const format = n => new Intl.NumberFormat('tr-TR', {maximumFractionDigits:3}).format(n);
const kg = g => `${format(g/1000)} kg`;
const money = cents => `${format(cents/100)} ₺`;
let state, view = 'market', filters = {search:'',material:'',city:''}, selectedMatch, toastTimer;
const titles = {
  market:['Malzeme pazarı','Malzemenin ikinci hikâyesi.','Üretimden artan kumaşları keşfet, yeni bir döngünün parçası ol.'],
  requests:['İhtiyaç talepleri','Bir fikrin var. Malzemesini bul.','Atölyelerin ihtiyaçlarını gör veya kendi malzeme talebini oluştur.'],
  matches:['Eşleştirmeler','Doğru parça, doğru tasarım.','Malzeme, renk ve bütçeye uyan seçenekler; miktar ve şehir önceliğiyle.'],
  reservations:['Rezervasyonlar','Döngüyü birlikte tamamlayalım.','Ayrılan malzemeleri takip et, teslimatı kaydet veya rezervasyonu iptal et.'],
  impact:['Döngü raporu','Küçük parçalar. Somut bir değişim.','Tamamlanan teslimatlardan hesaplanan yeniden kullanım ve işlem özeti.']
};
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'İşlem tamamlanamadı.');
  return body;
}
async function refresh(){state = await api('/api/state');render();}
function toast(message){$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,4000);}
function pill(value){return `<span class="pill">${escape(value)}</span>`;}
function empty(message){return `<div class="empty">${escape(message)}</div>`;}
function setView(next){view=next;render();}
function render(){
  const [crumb,title,subtitle]=titles[view];
  $('#breadcrumb').textContent=crumb;$('#page-title').textContent=title;$('#page-subtitle').textContent=subtitle;
  document.querySelectorAll('[data-view]').forEach(x=>{x.classList.toggle('active',x.dataset.view===view);if(x.closest('nav'))x.setAttribute('aria-current',x.dataset.view===view?'page':'false');});
  $('#match-count').textContent=state.matches.length;
  $('#add-button').textContent=view==='requests'?'＋ İhtiyaç talebi ekle':'＋ Malzeme ilanı ekle';
  const reused=state.reservations.filter(r=>r.status==='completed').reduce((a,r)=>a+r.grams,0);
  const active=state.listings.filter(l=>l.grams>0);
  $('#stats').innerHTML=[['Döngüye hazır malzeme',kg(active.reduce((a,l)=>a+l.grams,0)),'Kullanılabilir stok'],['Aktif malzeme ilanı',format(active.length),'Ayrıştırılmış kumaş partileri'],['Uygun eşleştirme',format(state.matches.length),'İlan ve talep çifti'],['Yeniden kullanılan',kg(reused),'Tamamlanan teslimatlar']].map(([label,value,note])=>`<div class="stat"><small>${label}</small><strong>${value}</strong><span>${note}</span></div>`).join('');
  if(view==='market') renderMarket();
  if(view==='requests') renderRequests();
  if(view==='matches') renderMatches();
  if(view==='reservations') renderReservations();
  if(view==='impact') renderImpact();
}
function renderMarket(){
  $('#content').innerHTML=`<div class="market-layout"><section><div class="filters"><div class="search"><input id="search" type="search" placeholder="Kumaş, içerik veya atölye ara…" aria-label="Malzeme ara" value="${escape(filters.search)}"></div>${['material','city'].map(key=>`<div class="filter-select"><select id="filter-${key}" aria-label="${key==='material'?'Malzeme':'Şehir'} filtresi"><option value="">${key==='material'?'Tüm kumaşlar':'Tüm şehirler'}</option>${state.options[key].map(x=>`<option ${filters[key]===x?'selected':''}>${escape(x)}</option>`).join('')}</select></div>`).join('')}</div><div class="section-title"><h2>Yeni bir başlangıca hazır</h2><span id="result-count"></span></div><div class="cards" id="cards"></div></section><aside class="market-aside"><div class="right-panel"><p class="eyebrow">DÖNGÜNÜN BİR PARÇASI OL</p><div class="orb" aria-hidden="true">↻</div><h3>Birinin artığı,<br>senin ilhamın.</h3><p>Kullanılmayan kumaşları yeniden üretime kazandır. İhtiyacın kadar malzeme ile yeni bir hikâye başlat.</p><button class="text-button" data-go="requests">İhtiyaçları keşfet ↗</button><div class="panel-divider"></div><div class="steps"><div><b>01</b> Malzemeni tanımla</div><div><b>02</b> Uygun taleple eşleş</div><div><b>03</b> Teslimatı tamamla</div></div></div><div class="feed"><h3>Döngüden haberler</h3>${state.events.slice(0,3).map(e=>`<p><strong>${escape(e.action)}</strong><br>${escape(e.detail)}</p>`).join('')}</div></aside></div>`;
  $('#search').addEventListener('input',e=>{filters.search=e.target.value;renderCards();});
  ['material','city'].forEach(key=>$(`#filter-${key}`).addEventListener('change',e=>{filters[key]=e.target.value;renderCards();}));
  renderCards();
}
function renderCards(){
  const needle=filters.search.toLocaleLowerCase('tr');
  const listings=state.listings.filter(l=>l.grams>0&&(!filters.material||l.material===filters.material)&&(!filters.city||l.city===filters.city)&&`${l.title} ${l.organization} ${l.composition}`.toLocaleLowerCase('tr').includes(needle));
  $('#result-count').textContent=`${listings.length} malzeme ilanı`;
  const colors={Ekru:'',Mavi:'blue',Siyah:'black',Yeşil:'green',Karışık:'mixed'};
  $('#cards').innerHTML=listings.map(l=>`<article class="card"><div class="fabric ${colors[l.color]}" role="img" aria-label="${escape(l.color)} renkli temsili kumaş dokusu"><span class="tag">${escape(l.kind)}</span><span class="lot">${kg(l.grams)} mevcut</span></div><div class="card-body"><div class="card-topline"><span>${escape(l.organization)}</span><span>⌖ ${escape(l.city)}</span></div><h3>${escape(l.title)}</h3><p class="composition">${escape(l.composition)} · ${l.gsm} g/m² · ${escape(l.color)}</p><div class="card-bottom"><strong>${money(l.price)} <small>/ kg</small></strong><button class="secondary" data-detail="${l.id}" aria-expanded="false">İlanı incele ↗</button></div><div class="card-details" id="detail-${l.id}" hidden>${escape(l.description)}<p>Parti #${l.id} · Görsel temsili dokudur.</p><button class="text-button" data-match-listing="${l.id}">Uygun talepleri gör →</button></div></div></article>`).join('')||empty('Bu filtrelere uygun malzeme bulunamadı. Filtreleri değiştir veya yeni ilan ekle.');
}
function renderRequests(){
  $('#content').innerHTML=`<div class="section-title"><h2>Atölyeler malzeme arıyor</h2><span>${state.requests.length} talep</span></div><div class="list-grid">${state.requests.map(r=>`<article class="record"><small class="muted">${escape(r.organization)} · ${escape(r.city)}</small><h3>${escape(r.title)}</h3><div class="pills">${[r.material,r.color,`En fazla ${money(r.budget)} / kg`].map(pill).join('')}</div><p>Toplam ihtiyaç <strong>${kg(r.grams)}</strong><br>Henüz ayrılmamış <strong>${kg(r.remaining)}</strong></p><div class="progress"><progress value="${r.grams-r.remaining}" max="${r.grams}" aria-label="Talebin ayrılan miktarı"></progress></div><button class="secondary" data-go="matches">${state.matches.filter(m=>m.request_id===r.id).length} uygun ilanı eşleştirmelerde gör ↗</button></article>`).join('')||empty('Henüz ihtiyaç talebi yok. İlk talebi ekleyerek eşleştirmeleri başlat.')}</div>`;
}
function renderMatches(onlyListing){
  const matches=state.matches.filter(m=>!onlyListing||m.listing_id===onlyListing);
  $('#content').innerHTML=`<div class="report-note">Malzeme, renk ve bütçe zorunlu koşullardır. Puan: temel uyum 50 + karşılanabilir miktar 30 + aynı şehir 20. Her seçenek bağımsızdır; rezervasyon sonrası liste yeniden hesaplanır.${onlyListing?' <button class="text-button" data-go="matches">Tüm eşleştirmeleri göster →</button>':''}</div><div class="list-grid">${matches.map(m=>{
    const l=state.listings.find(x=>x.id===m.listing_id),r=state.requests.find(x=>x.id===m.request_id);
    return `<article class="record"><div class="score">%${m.score}</div><small class="muted">${escape(l.organization)} → ${escape(r.organization)}</small><h3>${escape(l.title)}</h3><p>Talep: ${escape(r.title)}<br>${kg(m.grams)} ayrılabilir · ${money(l.price)} / kg</p><div class="pills">${m.reasons.map(pill).join('')}</div><div class="record-actions"><button class="primary" data-reserve="${m.listing_id}:${m.request_id}">Malzemeyi ayır ↗</button></div></article>`;
  }).join('')||empty('Uygun eşleştirme yok. Malzeme, renk, birim bütçe veya kalan miktar koşullarını kontrol et.')}</div>`;
}
function renderReservations(){
  const labels={reserved:'Teslimat bekliyor',completed:'Teslim edildi',cancelled:'İptal edildi'};
  $('#content').innerHTML=`<div class="list-grid">${state.reservations.map(r=>`<article class="record"><div class="pills">${pill(labels[r.status])}${pill(`#${r.id}`)}</div><h3>${escape(r.title)}</h3><p>Alıcı: ${escape(r.buyer)}<br>${kg(r.grams)} · Toplam ${money(Math.round(r.price*r.grams/1000))}</p>${r.status==='reserved'?`<div class="record-actions"><button class="primary" data-status="${r.id}:completed">Teslimatı tamamla</button><button class="secondary" data-status="${r.id}:cancelled">İptal et, stoğa iade et</button></div>`:''}</article>`).join('')||empty('Henüz rezervasyon yok. Eşleştirmeler bölümünden bir malzeme ayır.')}</div>`;
}
function renderImpact(){
  const complete=state.reservations.filter(r=>r.status==='completed');
  const grouped=Object.entries(complete.reduce((a,r)=>{a[r.material]=(a[r.material]||0)+r.grams;return a;},{}));
  $('#content').innerHTML=`<div class="report-note"><strong>Ölçülebilir olanı takip ediyoruz.</strong><br>Yeniden kullanılan miktar yalnızca “teslim edildi” durumundaki rezervasyonlardan hesaplanır. Bu demo karbon, su tasarrufu veya doğrulanmış çevresel etki iddiası üretmez. Tüm başlangıç kayıtları kurgusaldır.</div><div class="section-title"><h2>Malzemeye göre yeniden kullanım</h2><a class="secondary" href="/api/report.csv" download="ilmek-dongu-raporu.csv">↓ İşlem raporu (CSV)</a></div><div class="table-wrap"><table><thead><tr><th>Malzeme</th><th>Teslim edilen miktar</th><th>İşlem sayısı</th></tr></thead><tbody>${grouped.map(([mat,g])=>`<tr><td>${escape(mat)}</td><td>${kg(g)}</td><td>${complete.filter(r=>r.material===mat).length}</td></tr>`).join('')||'<tr><td colspan="3">Henüz tamamlanmış teslimat yok.</td></tr>'}</tbody></table></div><br><div class="section-title"><h2>İşlem günlüğü</h2><span>Son 15 hareket · UTC</span></div><div class="table-wrap"><table><thead><tr><th>İşlem</th><th>Açıklama</th><th>Zaman</th></tr></thead><tbody>${state.events.map(e=>`<tr><td>${escape(e.action)}</td><td>${escape(e.detail)}</td><td>${escape(e.created_at)}</td></tr>`).join('')}</tbody></table></div>`;
}
function field(name,label,type='text',options,wide=false){
  let control;
  if(options)control=`<select name="${name}" required>${options.map(x=>`<option>${escape(x)}</option>`).join('')}</select>`;
  else if(type==='textarea')control=`<textarea name="${name}" maxlength="1000" required></textarea>`;
  else control=`<input name="${name}" type="${type}" ${type==='number'?`min="${['price','budget'].includes(name)?'0':name==='gsm'?'1':'0.001'}" max="1000000" step="${name==='gsm'?'1':name==='kg'?'0.001':'0.01'}"`:'maxlength="120"'} required>`;
  return `<label class="${wide?'wide':''}">${label}${control}</label>`;
}
function openEntry(){
  const request=view==='requests';$('#dialog-title').textContent=request?'İhtiyaç talebi oluştur':'Malzemeni döngüye kat';$('#form-error').textContent='';
  $('#entry-form').dataset.type=request?'requests':'listings';
  $('#fields').innerHTML=field('title',request?'Proje / talep adı':'İlan başlığı')+field('organization','Firma / atölye adı')+field('material','Malzeme','select',state.options.material)+field('color','Renk','select',request?[...state.options.color,'Fark etmez']:state.options.color)+field('city','Şehir','select',state.options.city)+field('kg',request?'İhtiyaç miktarı (kg)':'Kullanılabilir miktar (kg)','number')+field(request?'budget':'price',request?'Azami birim bütçe (₺/kg)':'Birim fiyat (₺/kg)','number')+(request?'':field('kind','Parça türü','select',state.options.kind)+field('gsm','Gramaj (g/m²)','number')+field('composition','Elyaf içeriği (beyan)')+field('description','Parça ölçüsü, durum ve teslimat notları','textarea',null,true));
  $('#form-dialog').showModal();
}
$('#navigation').addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(b&&state)setView(b.dataset.view);});
$('#add-button').addEventListener('click',()=>{if(state)openEntry();});
$('#close-dialog').addEventListener('click',()=>$('#form-dialog').close());
$('#close-reserve').addEventListener('click',()=>$('#reserve-dialog').close());
$('#content').addEventListener('click',async e=>{
  const b=e.target.closest('button');if(!b)return;
  if(b.dataset.go)setView(b.dataset.go);
  if(b.dataset.detail){const panel=$(`#detail-${b.dataset.detail}`);panel.hidden=!panel.hidden;b.setAttribute('aria-expanded',String(!panel.hidden));}
  if(b.dataset.matchListing){setView('matches');renderMatches(Number(b.dataset.matchListing));}
  if(b.dataset.reserve){
    const [lid,rid]=b.dataset.reserve.split(':').map(Number);selectedMatch=state.matches.find(m=>m.listing_id===lid&&m.request_id===rid);
    $('#reserve-summary').textContent=`${state.listings.find(x=>x.id===lid).title} · En fazla ${kg(selectedMatch.grams)}`;
    const input=$('#reserve-form input');input.value=selectedMatch.grams/1000;input.max=selectedMatch.grams/1000;$('#reserve-error').textContent='';$('#reserve-dialog').showModal();
  }
  if(b.dataset.status){
    const [id,status]=b.dataset.status.split(':');b.disabled=true;
    try{await api('/api/reservations/status',{id:Number(id),status});await refresh();toast(status==='completed'?'Teslimat kaydedildi. Yeniden kullanım raporu güncellendi.':'Rezervasyon iptal edildi, malzeme stoğa döndü.');}catch(error){toast(error.message);b.disabled=false;}
  }
});
$('#entry-form').addEventListener('submit',async e=>{
  e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;
  try{await api(`/api/${e.target.dataset.type}`,Object.fromEntries(new FormData(e.target)));$('#form-dialog').close();await refresh();toast('Kayıt eklendi. Eşleştirmeler güncellendi.');}catch(error){$('#form-error').textContent=error.message;}finally{button.disabled=false;}
});
$('#reserve-form').addEventListener('submit',async e=>{
  e.preventDefault();const button=e.target.querySelector('[type=submit]');button.disabled=true;
  try{await api('/api/reservations',{listing_id:selectedMatch.listing_id,request_id:selectedMatch.request_id,kg:e.target.elements.kg.value});$('#reserve-dialog').close();await refresh();toast('Malzeme ayrıldı. Rezervasyonlar bölümünden takip edebilirsin.');}catch(error){$('#reserve-error').textContent=error.message;}finally{button.disabled=false;}
});
refresh().catch(error=>{$('#content').textContent=`Veriler yüklenemedi: ${error.message}. Sunucuyu kontrol edip sayfayı yenileyin.`;});
