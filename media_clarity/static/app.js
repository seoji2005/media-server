"use strict";
const $ = (id) => document.getElementById(id);
let sessionToken = "", items = [], filter = "all", activeItem = null, upload = null;
let recommendedItems = [], recommendationState = "idle", recommendationError = "", recommendationVersion = 0;
let preferenceVersion = 0, savedPreference = null;
const pendingPreferences = new Map();
const pendingTitles = new Map();
let titleView=null;
const preparingPlayback = new Set();
let playerRequest = 0, entryAwaitingPlay = false;
let pendingItemEntry = null;
let toastTimer, saveTimer;
const positionSaves = new Map();
const video = $("video"), dialog = $("player-dialog");
$("settings-open").addEventListener("click",()=>$("settings-dialog").showModal());
$("settings-close").addEventListener("click",()=>$("settings-dialog").close());
const errors = {
  position_changed:"다른 저장으로 시청 위치가 바뀌었습니다. 지금 위치는 이 창에 남아 있습니다. 다시 재생하거나 이동하면 저장을 시도합니다.",
  invalid_title:"제목을 180자 이내로 입력해 주세요. 줄바꿈과 제어 문자는 사용할 수 없습니다.",
  title_changed:"다른 창에서 제목이 바뀌었습니다. 저장된 제목을 불러와 확인해 주세요.",
  invalid_item_entry:"영상 연결 정보를 확인할 수 없습니다. 보낸 앱에서 다시 열어 주세요.",
  item_reference_changed:"다른 보관함이거나 원본 정보가 바뀌었습니다. 보낸 앱에서 연결을 다시 확인해 주세요.",
  invalid_caption_view:"자막 시간은 10초까지 앞당기거나 늦출 수 있습니다.",
  caption_view_changed:"다른 창에서 자막 설정이 바뀌었습니다. 저장 상태를 다시 확인해 주세요.",
  invalid_moment_entry:"장면의 시점을 확인해 주세요.",
  moment_reference_changed:"원본이나 시간 기준이 바뀌었습니다. 장면 기록을 다시 연결해 주세요.",
  moment_not_available:"이 장면은 현재 열 수 없습니다.",
  moment_timeline_unsupported:"이 재생용 사본의 장면 진입은 아직 지원되지 않습니다.",
  scene_model_missing:"장면 검색 모델이 아직 설치되지 않았습니다. 설치 안내의 로컬 장면 검색 준비를 확인해 주세요.",
  scene_runtime_missing:"장면 검색 실행 패키지가 필요합니다. 설치 안내를 확인해 주세요.",
  scene_model_changed:"장면 검색 모델이 변경됐거나 지원하지 않는 구성입니다. 설치 상태를 확인하고 다시 준비해 주세요.",
  scene_previews_required:"장면 검색 준비를 누르면 미리보기부터 이어서 만듭니다.",
  scene_index_required:"새로 만들거나 변경된 미리보기가 있습니다. 장면 검색을 다시 준비해 주세요.",
  scene_index_changed:"저장된 분석을 확인할 수 없습니다. 장면 검색을 다시 준비해 주세요.",
  scene_failed:"장면 검색을 완료하지 못했습니다. 로컬 모델 설치를 확인하고 다시 시도해 주세요. 저장한 분석과 영상은 유지됩니다.",
  scene_timeout:"장면 검색이 제한 시간을 넘겼습니다. 완료한 분석은 저장됐으니 다시 준비할 수 있습니다.",
  scene_query_invalid:"찾고 싶은 화면을 200자 이내로 입력해 주세요.",
  scene_query_too_long:"검색 문장이 너무 깁니다. 찾고 싶은 대상과 장소를 짧게 적어 주세요.",
  scene_network_disabled:"검색 엔진의 외부 연결 시도를 차단했습니다. 로컬 모델 설치를 확인해 주세요.",
  preview_busy:"다른 미리보기를 준비 중입니다. 잠시 후 이어서 만들어 주세요.",
  preview_changed:"저장된 미리보기를 확인할 수 없습니다. 원본 재생은 계속 사용할 수 있습니다.",
  preview_input_changed:"영상과 미리보기 정보가 일치하지 않습니다. 원본 상태를 확인해 주세요.",
  preview_interrupted:"미리보기 준비가 중단됐습니다. 저장한 프레임부터 이어 만들 수 있습니다.",
  preview_not_found:"이 미리보기를 찾을 수 없습니다. 목록을 다시 열어주세요.",
  preview_timing_unavailable:"이 영상의 미리보기 시점을 확인할 수 없습니다. 원본 재생은 계속 사용할 수 있습니다.",
  invalid_audio_track: "선택할 수 없는 오디오입니다. 영상의 오디오 목록을 다시 확인해 주세요.",
  processing_audio_conflict: "다른 오디오의 자막 작업이 남아 있습니다. 해당 작업을 완료한 뒤 새 자막을 만들어 주세요.",
  preference_changed: "다른 저장으로 선호가 바뀌었습니다. 저장 상태를 다시 확인해 주세요.",
  local_origin_required: "이 기기의 로컬 주소에서 다시 열어주세요.", session_required: "앱이 재시작되었습니다. 페이지를 새로고침해 주세요.",
  unsupported_container: "지원하지 않는 형식입니다. MP4·MKV 또는 WebM 영상을 선택해 주세요.", unsupported_codec: "현재 브라우저 감상용 코덱을 지원하지 않습니다. H.264/AAC MP4 또는 VP8·VP9 WebM이 필요합니다.",
  unsupported_hevc: "HEVC 영상은 아직 재생용 변환을 지원하지 않습니다. 원본을 변경하지 않았습니다.",
  unsupported_video_depth: "10-bit 또는 4:2:0 이외의 영상 색 형식은 아직 지원하지 않습니다.",
  unsupported_audio_codec: "첫 번째 오디오의 코덱을 지원하지 않습니다. 원본을 변경하지 않았습니다.",
  rendition_required: "원본 보관 완료 · 재생용 사본 준비가 필요합니다. 영상을 다시 선택해 준비할 수 있습니다.",
  rendition_validation_failed: "재생용 사본의 길이·형식 검증에 실패했습니다. 원본은 보존했습니다. 영상을 다시 선택해 재시도할 수 있습니다.",
  invalid_media: "영상을 읽을 수 없습니다. 정상적으로 재생되는 파일인지 확인해 주세요.", media_timeout: "영상 확인 시간이 초과되었습니다. 파일 상태를 확인한 뒤 다시 시도해 주세요.",
  ffmpeg_unavailable: "FFmpeg 또는 ffprobe를 찾을 수 없습니다. 설치 후 앱을 다시 시작해 주세요.",
  insufficient_space: "보관 공간이 부족합니다. 원본 크기보다 여유 있는 공간을 확보해 주세요.", import_busy: "다른 영상을 가져오고 있습니다. 완료된 후 다시 시도해 주세요.",
  empty_media: "비어 있는 파일은 가져올 수 없습니다.", incomplete_upload: "가져오기가 끝나지 않았습니다. 원본은 그대로이며 다시 선택할 수 있습니다.",
  storage_unavailable: "보관 공간에 접근할 수 없습니다. 권한과 저장 장치를 확인해 주세요.",
  unsafe_storage: "안전하지 않은 보관 경로가 감지되었습니다. 앱을 닫고 저장 위치를 확인해 주세요.",
  managed_file_missing: "보관된 파일을 찾을 수 없습니다. 원본은 삭제되지 않았습니다. 앱을 닫고 백업에서 해당 보관 파일을 복원해 주세요.",
  managed_file_changed: "보관된 파일이 변경되었습니다. 앱을 닫고 안전한 사본을 복원해 주세요.",
  invalid_position: "이 시청 위치를 저장할 수 없습니다. 유효한 장면으로 이동해 주세요.", destination_collision: "보관 파일 충돌로 가져오기를 중단했습니다. 다시 시도해 주세요.",
  copy_changed: "복사본 검증에 실패했습니다. 다시 가져와 주세요.", source_changed: "가져오는 동안 원본이 변경되었습니다. 파일 변경을 멈춘 뒤 다시 시도해 주세요.",
  item_not_found: "영상을 찾을 수 없습니다. 보관함을 새로고침해 주세요."
};
function message(code) { return errors[code] || "작업을 완료하지 못했습니다. 다시 시도해 주세요."; }
function toast(text, error = false) { const host=$("settings-dialog").open?$("settings-dialog"):dialog.open?dialog:document.body; host.append($("toast")); clearTimeout(toastTimer); $("toast").textContent = text; $("toast").classList.toggle("error", error); $("toast").hidden = false; toastTimer = setTimeout(() => $("toast").hidden = true, error ? 8500 : 4500); }
async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, { ...options, headers: { "X-Media-Token": sessionToken, ...(options.headers || {}) } }); }
  catch { throw new Error("앱에 연결할 수 없습니다. 로컬 서버가 실행 중인지 확인해 주세요."); }
  let result;
  try { result = await response.json(); } catch { throw new Error("앱 응답을 읽을 수 없습니다."); }
  if (!response.ok) throw Object.assign(new Error(subtitleMessages[result.error] || message(result.error)), {code:result.error});
  return result;
}
async function boundedApi(path,options,wait,timeoutMessage){
  const controller=new AbortController();let timer;
  try{
    return await Promise.race([
      api(path,{...options,signal:controller.signal}),
      new Promise((_,reject)=>{timer=setTimeout(()=>{reject(new Error(timeoutMessage));controller.abort();},wait);})
    ]);
  }finally{clearTimeout(timer);}
}
function time(seconds) { seconds = Math.max(0, Math.floor(seconds || 0)); const h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = seconds % 60; return h ? `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}` : `${m}:${String(s).padStart(2,"0")}`; }
function continuing(item) { return item.position > 0 && item.position < Math.max(1, item.duration - 2); }
function render() {
  $("nav-count").textContent = String(items.length);
  const query = $("search").value.trim().normalize("NFKC").toLocaleLowerCase();
  const recommended = filter === "recommended";
  const visible = (recommended ? recommendedItems : items).filter(i => (filter !== "continue" || continuing(i)) && i.title.normalize("NFKC").toLocaleLowerCase().includes(query));
  if (filter === "continue") visible.sort((a,b) => (b.watched_at || "").localeCompare(a.watched_at || ""));
  const heading = recommended ? "추천" : filter === "all" ? "보관함" : "이어보기";
  $("library-heading").firstChild.textContent = heading + " ";
  $("item-count").textContent = String(visible.length);
  $("breadcrumb-current").textContent = heading;
  $("section-description").textContent = recommended ? "추천에 포함한 선호 미지정 영상에서 골랐어요 · 제목과 직접 표시한 선호만 사용" : filter === "all" ? "당신의 다음 감상을 기다리는 영상들" : "머물렀던 장면에서 다시 시작하세요";
  document.querySelector(".sort-label").textContent = recommended ? "선호와 새로운 발견 · 최대 12개" : filter === "all" ? "최근 가져온 순" : "최근 시청한 순";
  $("nav-all").classList.toggle("selected",filter === "all"); $("nav-continue").classList.toggle("selected",filter === "continue");
  $("nav-recommended").classList.toggle("selected",recommended);
  for (const [id, selected] of [["nav-all",filter === "all"],["nav-continue",filter === "continue"],["nav-recommended",recommended]]) { if(selected) $(id).setAttribute("aria-current","page"); else $(id).removeAttribute("aria-current"); }
  const grid = $("library-grid"); grid.replaceChildren();
  for (const item of visible) {
    const card = $("card-template").content.cloneNode(true);
    card.querySelector("h3").textContent = item.title;
    card.querySelector("h3").title = item.title;
    card.querySelector(".duration").textContent = time(item.duration);
    card.querySelector(".card-resolution").textContent = `${item.width} × ${item.height}`;
    const status = card.querySelector(".card-status");
    status.textContent = preparingPlayback.has(item.id) ? "재생용 사본 준비 중…" : item.unavailable_reason === "rendition_required" ? (item.preparation_error ? "재생 준비 실패 · 선택하면 재시도" : "원본 보관됨 · 선택하면 재생 준비") : !item.available ? (item.unavailable_reason === "managed_file_changed" ? "보관 파일이 변경됨" : "파일을 찾을 수 없음") : continuing(item) ? `${time(item.position)}부터 이어보기` : item.position > 0 ? "시청 완료" : "아직 보지 않음";
    status.classList.toggle("missing", !item.available);
    if(recommended) {
      const reason = document.createElement("p"); reason.className = "recommendation-reason";
      reason.textContent = {liked_title:"좋아요한 영상과 제목이 비슷해요",lower_priority:"덜 선호한 제목과 겹쳐 낮은 순위예요",explore:"새롭게 살펴볼 영상"}[item.recommendation_reason] || "추천에 포함한 영상";
      card.querySelector(".card-info").append(reason);
    }
    const progress = card.querySelector("progress"); progress.value = item.position / item.duration * 100; progress.hidden = item.position === 0;
    const image = card.querySelector("img");
    if (item.thumbnail && item.available) { image.src = `/api/media/${item.id}/thumbnail`; image.addEventListener("error", () => image.hidden = true, {once:true}); } else image.hidden = true;
    const button = card.querySelector("button"); button.setAttribute("aria-label", `${item.title}, ${status.textContent}`); button.addEventListener("click", () => openPlayer(item.id));
    grid.append(card);
  }
  const empty = !visible.length; $("empty-state").hidden = !empty;
  $("import-empty").hidden = !!query || filter !== "all"; $("format-note").hidden = !!query || filter !== "all";
  $("empty-title").textContent = recommended && recommendationState === "loading" ? "추천을 불러오고 있어요" : recommended && recommendationState === "error" ? "추천을 불러오지 못했어요" : query ? "일치하는 영상이 없어요" : recommended ? "추천할 영상이 아직 없어요" : filter === "continue" ? "이어볼 영상이 아직 없어요" : "첫 번째 영상을 담아보세요";
  $("empty-description").replaceChildren();
  $("empty-description").textContent = recommended && recommendationState === "loading" ? "이 기기에 저장한 선호를 확인하고 있습니다." : recommended && recommendationState === "error" ? recommendationError + " 추천을 다시 선택하면 재시도합니다." : query ? "다른 제목으로 검색해 보세요." : recommended ? "보관함에서 영상을 열고 ‘추천에 포함’을 켜주세요. 선호를 표시한 영상은 기준으로 사용하고, 선호 미지정 영상을 추천합니다." : filter === "continue" ? "영상을 보기 시작하면 마지막 시청 위치가 여기에 남습니다." : "파일을 선택하거나 이곳에 끌어놓으세요. 원본은 그대로 두고, 감상용 사본을 안전하게 보관합니다.";
}
async function refresh() { const result = await api("/api/library"); items = result.items; invalidateRecommendations(); if(filter === "recommended") await refreshRecommendations(); else render(); }
function invalidateRecommendations() { recommendationVersion++; recommendedItems=[]; recommendationState="idle"; }
async function refreshRecommendations() {
  const version=++recommendationVersion; recommendedItems=[]; recommendationState="loading"; render();
  try {
    const result=await api("/api/recommendations");
    if(version!==recommendationVersion)return;
    recommendedItems=result.items; recommendationState="ready";
  } catch(e) { if(version!==recommendationVersion)return; recommendationState="error"; recommendationError=e.message; }
  render();
}
function resetPreference() {
  preferenceVersion++; savedPreference=null; $("preference-controls").disabled=true;
  $("preference-value").value="neutral"; $("preference-include").checked=false; $("preference-retry").hidden=true;
  $("preference-state").textContent="선호를 불러오고 있어요.";
}
function showPreference(value) {
  savedPreference=value; $("preference-value").value=value.preference; $("preference-include").checked=value.included;
  $("preference-controls").disabled=false; $("preference-retry").hidden=true;
  $("preference-state").textContent=value.included ? "이 기기에 저장됨 · 추천에 사용합니다." : "이 기기에 저장됨 · 이 영상과 선호는 추천에서 제외됩니다.";
}
async function refreshPreference(owner) {
  resetPreference(); const version=preferenceVersion;
  try {
    // Reopening the same item must not read/enable stale settings during its save.
    const pending=pendingPreferences.get(owner.id);
    if(pending)await pending.catch(()=>{});
    if(activeItem!==owner || version!==preferenceVersion)return;
    const value=await api(`/api/library/${owner.id}/preference`);
    if(activeItem!==owner || version!==preferenceVersion)return;
    showPreference(value);
  } catch(e) { if(activeItem!==owner || version!==preferenceVersion)return; $("preference-state").textContent=e.message; $("preference-retry").hidden=false; }
}
async function savePreference() {
  const owner=activeItem, version=preferenceVersion;
  if(!owner || !savedPreference || $("preference-controls").disabled)return;
  const value={included:$("preference-include").checked,preference:$("preference-value").value,revision:savedPreference.revision};
  $("preference-controls").disabled=true; $("preference-state").textContent="선호 저장 중…";
  invalidateRecommendations(); render();
  const pending=api(`/api/library/${owner.id}/preference`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(value)});
  pendingPreferences.set(owner.id,pending);
  try {
    const saved=await pending;
    if(activeItem===owner && version===preferenceVersion)showPreference(saved);
  } catch(e) {
    // A lost response may follow a committed write. Read before permitting another edit.
    if(activeItem===owner && version===preferenceVersion) { savedPreference=null; $("preference-state").textContent=e.message + " 저장 상태를 다시 확인해 주세요."; $("preference-retry").hidden=false; }
  } finally {
    if(pendingPreferences.get(owner.id)===pending)pendingPreferences.delete(owner.id);
    invalidateRecommendations(); if(filter === "recommended") refreshRecommendations();
  }
}
$("preference-value").addEventListener("change",savePreference);
$("preference-include").addEventListener("change",savePreference);
$("preference-retry").addEventListener("click",()=>{if(activeItem)refreshPreference(activeItem);});
function chooseFile() { if(upload) return toast("현재 가져오기가 끝난 뒤 선택해 주세요."); $("file-input").click(); }
async function importFile(file) {
  if(upload) return toast("한 번에 한 개의 영상을 가져올 수 있습니다.");
  if(!file || !file.size) return toast(message("empty_media"),true);
  const xhr = new XMLHttpRequest(); upload = xhr;
  $("upload-status").hidden = false; $("upload-title").textContent = file.name; $("upload-detail").textContent = "원본을 그대로 두고 감상용 사본을 가져오고 있어요";
  $("upload-progress").value = 0; $("upload-percent").textContent = "0%"; $("upload-cancel").hidden = false;
  $("import-top").disabled = true; $("import-empty").disabled = true;
  xhr.open("POST","/api/import"); xhr.setRequestHeader("Content-Type","application/octet-stream"); xhr.setRequestHeader("X-Media-Token",sessionToken); xhr.setRequestHeader("X-Media-Filename",encodeURIComponent(file.name));
  xhr.upload.addEventListener("progress", e => { if(e.lengthComputable){ const percent=Math.round(e.loaded/e.total*100); $("upload-progress").value=percent; $("upload-percent").textContent=`${percent}%`; if(percent===100){ $("upload-detail").textContent="파일 무결성과 재생 형식을 확인하고 있어요. 긴 영상은 잠시 걸릴 수 있습니다."; $("upload-percent").textContent="확인 중"; $("upload-cancel").hidden=true; } } });
  xhr.addEventListener("load", async () => { let result; try {result=JSON.parse(xhr.responseText);} catch {toast("앱 응답을 읽을 수 없습니다.",true); return;} if(xhr.status>=200&&xhr.status<300){ toast(result.duplicate ? "이미 보관함에 있는 영상입니다. 기존 시청 기록을 유지했어요." : "보관함에 영상을 담았습니다."); try {await refresh(); if(result.item?.unavailable_reason === "rendition_required") await preparePlayback(result.item.id);} catch(e){toast(e.message,true);} } else toast(message(result.error),true); });
  xhr.addEventListener("error", () => toast("가져오기가 중단되었습니다. 앱 연결과 원본 파일 상태를 확인해 주세요.",true));
  xhr.addEventListener("abort", () => toast("가져오기를 취소했습니다. 원본은 그대로입니다."));
  xhr.addEventListener("loadend", () => { upload=null; $("upload-status").hidden=true; $("import-top").disabled=false; $("import-empty").disabled=false; $("file-input").value=""; });
  xhr.send(file);
}
async function preparePlayback(id) {
  if(preparingPlayback.has(id)) { toast("재생용 사본을 준비하고 있어요. 완료 후 다시 선택해 주세요."); return false; }
  preparingPlayback.add(id); render(); toast("원본 보관을 마쳤습니다. 재생용 사본을 준비하고 있어요.");
  try { await api(`/api/library/${id}/playback`,{method:"POST"}); toast("재생 준비를 마쳤습니다."); return true; }
  catch(e) { toast(e.message + " 보관된 원본은 유지됩니다.",true); return false; }
  finally { preparingPlayback.delete(id); await refresh(); }
}
async function openPlayer(id, entry=null, entryKind="moment", prepareEntry=false) {
  if(!entry) momentRequest++;
  let request = ++playerRequest;
  pendingItemEntry=null;
  $("item-entry-notice").hidden=true; $("item-entry-prepare").onclick=null;
  try {
    const pending=pendingTitles.get(id);if(pending)await pending.catch(()=>{});
    if(request!==playerRequest)return;
    const itemEntry=entry&&entryKind==="item";
    let item, moment=null;
    if(itemEntry){
      const result=await api(`/api/library/${id}/item-entry`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(entry)});
      if(request!==playerRequest)return;
      item=result.item;
      if(result.version!==1||result.server_id!==entry.server_id||result.library_id!==entry.library_id||!item||item.id!==id||item.file_id!==entry.file_id||item.sha256!==entry.sha256)throw new Error(errors.item_reference_changed);
    }else{
      item=await api(`/api/library/${id}`);
      if(request!==playerRequest)return;
      if(entry){
        moment=await api(`/api/library/${id}/moment-entry`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(entry)});
        if(request!==playerRequest)return;
        if(item.preparation!=="original"||item.audio_index!==0||item.file_id!==entry.timeline.file_id||item.sha256!==entry.timeline.sha256||Math.floor(item.duration*1000)!==entry.duration_ms)return toast(errors.moment_reference_changed,true);
      }
    }
    if(item.unavailable_reason === "rendition_required" || item.audio_tracks === null) {
      if(itemEntry&&!prepareEntry){
        $("item-entry-message").textContent=`${item.title} · 원본은 보관돼 있습니다. 감상하려면 재생용 사본을 준비해 주세요.`;
        $("item-entry-notice").hidden=false; $("item-entry-prepare").hidden=false;
        pendingItemEntry=entry;
        $("item-entry-prepare").onclick=()=>{if(pendingItemEntry===entry)openPlayer(id,entry,"item",true);};
        if(dialog.open)toast("연결한 영상은 재생 준비가 필요합니다. 보관함에서 준비해 주세요.");
        return;
      }
      if(entry&&!itemEntry)return toast(errors.moment_timeline_unsupported,true);
      if(!await preparePlayback(id))return;
      if(request!==playerRequest)return;
      if(itemEntry)return openPlayer(id,entry,"item");
      item = await api(`/api/library/${id}`);
    }
    if(request !== playerRequest)return;
    if(!item.available) return toast(message(item.unavailable_reason || "managed_file_missing"),true);
    // Validate an incoming link before interrupting current playback. Closing can
    // await a history write, so a newer entry must still win afterward.
    if(entry&&dialog.open){
      request++; await closePlayer();
      if(request!==playerRequest)return;
      if(itemEntry){
        // Closing this same video can save a newer position than the entry read.
        return openPlayer(id,entry,"item");
      }
    }
    for(const panel of ["audio-panel","subtitle-preparation","subtitle-search-panel","preference-panel"])$(panel).open=false;
    resetPreviews();
    const positionState=positionSaves.get(id);
    if(positionState&&!positionState.running){
      positionState.revision=item.position_revision??0;
      if(positionState.latest?.saved)positionState.latest=null;
    }
    const pendingPosition=positionState?.latest;
    if(!moment&&pendingPosition&&!pendingPosition.saved&&pendingPosition.audio_index===item.audio_index){
      item.position=Math.min(item.duration,pendingPosition.position);
    }
    entryAwaitingPlay=Boolean(entry); activeItem=item; $("player-title").textContent=item.title; renderAudio(item);resetTitle(item);
    $("video-error").hidden=true; $("save-state").textContent=continuing(item) ? `${time(item.position)}에서 이어보기` : "준비 중";
    if(item.thumbnail) video.poster=`/api/media/${id}/thumbnail`; else video.removeAttribute("poster");
    resetSubtitles(); video.src=`/api/media/${id}/content${audioQuery(item)}`; dialog.showModal(); dialog.scrollTop=0; refreshSubtitles(item);
    refreshPreference(item);
    video.addEventListener("loadedmetadata", function restore(){ if(activeItem!==item) return; const start=moment?moment.start_ms/1000:continuing(item)?item.position:0; if(start>0&&Number.isFinite(video.duration)) video.currentTime=Math.min(start,video.duration); $("save-state").textContent=!moment&&pendingPosition&&!pendingPosition.saved?`${time(start)} · 이 창에 남은 위치 · 저장 미확인`:moment?`${time(start)} 장면 · 재생 버튼을 눌러 시작하세요`:start>0?`${time(start)}에서 이어보기`:"재생 버튼을 눌러 시작하세요"; }, {once:true});
    // Autoplay is optional; browser policy may require the native play button.
    if(!entry) video.play().catch(()=>{});
  } catch(e) {
    if(request!==playerRequest)return;
    if(entryKind==="item"&&entry){
      $("item-entry-message").textContent=e.message; $("item-entry-notice").hidden=false; $("item-entry-prepare").hidden=true;
    }
    toast(e.message,true);
  }
}
function audioQuery(item){return Number.isInteger(item.audio_index)?`?audio_index=${item.audio_index}`:"";}
function resetTitle(owner=null){
  titleView=owner?{owner,expected:owner.title,busy:false,uncertain:false}:null;
  $("title-panel").open=false;$("title-input").value=owner?.title||"";$("title-state").textContent="";
  titleControls();
}
function titleCurrent(view){return titleView===view&&activeItem===view.owner;}
function titleControls(){
  $("title-input").disabled=!titleView||titleView.busy;
  $("title-save").disabled=!titleView||titleView.busy||titleView.uncertain;
  $("title-reload").disabled=!titleView||titleView.busy;
}
function applyTitle(id,title){
  for(const item of items)if(item.id===id)item.title=title;
  invalidateRecommendations();render();
}
$("title-form").addEventListener("submit",async event=>{
  event.preventDefault();const view=titleView;
  if(!view||!titleCurrent(view)||view.busy||view.uncertain)return;
  const title=$("title-input").value.trim();if(!title){$("title-state").textContent=errors.invalid_title;return;}
  view.busy=true;titleControls();$("title-state").textContent="제목 저장 중…";
  const pending=boundedApi(`/api/library/${view.owner.id}/title`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({title,expected_title:view.expected})},30000,"저장 응답을 확인하지 못했습니다. 저장됐을 수 있으니 현재 제목을 다시 확인해 주세요.");
  pendingTitles.set(view.owner.id,pending);
  try{
    const saved=await pending;applyTitle(view.owner.id,saved.title);
    if(!titleCurrent(view))return;
    view.owner.title=view.expected=saved.title;$("player-title").textContent=saved.title;$("title-input").value=saved.title;$("title-state").textContent="제목을 저장했습니다.";
  }catch(e){
    if(titleCurrent(view)){view.uncertain=e.code!=="invalid_title";$("title-state").textContent=e.message+" 입력한 제목은 남겨 두었습니다.";}
  }finally{
    if(pendingTitles.get(view.owner.id)===pending)pendingTitles.delete(view.owner.id);
    if(titleCurrent(view)){view.busy=false;titleControls();}
    if(filter==="recommended")refreshRecommendations();
  }
});
$("title-reload").addEventListener("click",async()=>{
  const view=titleView;if(!view||!titleCurrent(view)||view.busy)return;
  view.busy=true;titleControls();
  try{
    const saved=await boundedApi(`/api/library/${view.owner.id}`,{},30000,"저장된 제목을 확인하지 못했습니다. 서버 연결을 확인한 뒤 다시 눌러 주세요.");
    if(!titleCurrent(view))return;
    view.owner.title=view.expected=saved.title;$("player-title").textContent=saved.title;
    // Keep an unsaved draft after an uncertain write; only its expected title changes.
    if(!view.uncertain)$("title-input").value=saved.title;
    view.uncertain=false;$("title-state").textContent="저장된 제목을 확인했습니다. 입력한 제목을 확인한 뒤 저장해 주세요.";applyTitle(view.owner.id,saved.title);
  }catch(e){if(titleCurrent(view))$("title-state").textContent=e.message;}
  finally{if(titleCurrent(view)){view.busy=false;titleControls();if(filter==="recommended")refreshRecommendations();}}
});
function audioLabel(track){const language={jpn:"일본어",ja:"일본어",eng:"영어",en:"영어",kor:"한국어",ko:"한국어"}[track.language]||track.language;return [`오디오 ${track.index+1}`,language,track.title,track.codec?.toUpperCase(),track.channels?`${track.channels}채널`:"",track.error?"지원되지 않음":""].filter(Boolean).join(" · ");}
function renderAudio(item){
  const tracks=item.audio_tracks||[],select=$("audio-select"),index=item.audio_index||0;
  select.replaceChildren();for(const track of tracks){const option=new Option(audioLabel(track),String(track.index));option.disabled=!!track.error;select.add(option);}
  select.value=String(index);select.disabled=false;$("audio-apply").disabled=true;
  $("audio-panel").hidden=tracks.length<2;$("audio-brief").textContent=tracks[index]?audioLabel(tracks[index]):"";
  $("audio-state").textContent="선택한 음성으로 재생하고 새 자막을 만듭니다. 처음 선택할 때 재생용 사본을 준비하며 추가 저장 공간을 사용합니다.";
  const kind={remux_mp4:"재생용 MP4 · 영상 그대로",audio_mp4:"재생용 MP4 · 영상 그대로 · AAC 스테레오",remux_webm:"재생용 WebM · 영상 그대로",audio_webm:"재생용 WebM · 영상 그대로 · Opus 스테레오"}[item.preparation]||"원본 사본";
  $("player-meta").textContent=`${item.width} × ${item.height} · ${time(item.duration)} · ${kind}${tracks.length?` · 오디오 ${index+1}`:""}`;
}
$("audio-select").addEventListener("change",()=>{$("audio-apply").disabled=!activeItem||Number($("audio-select").value)===(activeItem.audio_index||0);});
$("audio-apply").addEventListener("click",async()=>{
  const owner=activeItem;if(!owner)return;const index=Number($("audio-select").value),hadFocus=document.activeElement===$("audio-apply");
  $("audio-select").disabled=true;$("audio-apply").disabled=true;$("audio-state").textContent="오디오를 준비하고 있어요. 지금 영상은 계속 감상할 수 있습니다.";
  try{
    const ready=await api(`/api/library/${owner.id}/audio/${index}`,{method:"POST"});if(activeItem!==owner)return;
    const position=video.currentTime,playing=!video.paused;video.pause();await waitForPosition(savePosition());if(activeItem!==owner)return;
    // The editor belongs to the library item, including while its audio changes.
    ready.title=owner.title;if(titleView?.owner===owner)titleView.owner=ready;
    activeItem=ready;renderAudio(ready);resetSubtitles();refreshPreference(ready);$("video-error").hidden=true;
    video.addEventListener("loadedmetadata",()=>{if(activeItem!==ready)return;video.currentTime=Math.min(position,ready.duration);savePosition();if(playing)video.play().catch(()=>{});},{once:true});
    video.src=`/api/media/${owner.id}/content${audioQuery(ready)}`;video.load();refreshSubtitles(ready);
    $("audio-state").textContent=`오디오 ${index+1}로 변경했습니다. 진행 중인 자막 작업은 시작할 때 선택한 음성을 유지합니다.`;
    if(hadFocus&&document.activeElement===document.body)$("audio-select").focus();
  }catch(e){if(activeItem===owner){$("audio-state").textContent=e.message+" 현재 재생은 유지됩니다.";$("audio-select").disabled=false;$("audio-apply").disabled=false;if(hadFocus&&document.activeElement===document.body)$("audio-apply").focus();}}
});
function savePosition(keepalive=false) {
  if(entryAwaitingPlay||!activeItem||!Number.isFinite(video.currentTime)||video.readyState<1) return Promise.resolve();
  const owner=activeItem, id=owner.id, audio_index=owner.audio_index;
  const position=Math.min(owner.duration,Math.max(0,video.currentTime));
  let state=positionSaves.get(id);
  if(!state){state={id,revision:owner.position_revision??0,latest:null,pending:null,running:false,promise:Promise.resolve()};positionSaves.set(id,state);}
  if(state.latest?.position===position&&state.latest.audio_index===audio_index&&!state.latest.failed) return state.promise;
  const intent={position,audio_index,owner,saved:false,failed:false};
  state.latest=state.pending=intent;
  $("save-state").textContent="시청 위치 저장 중…";
  // One active write and one newest pending intent per item. Another video never
  // waits for this item's connection, and repeated seeks cannot grow a backlog.
  if(!state.running)state.promise=flushPosition(state);
  return state.promise;
}
async function flushPosition(state){
  state.running=true;
  try{
    while(state.pending){
      const intent=state.pending;state.pending=null;
      try{
        // Abort cannot undo a server write. Re-read after an uncertain response,
        // and let SQLite reject any late write using an older revision.
        if(state.revision===null){
          const current=await boundedApi(`/api/library/${state.id}`,{},5000,"저장된 시청 위치를 확인하지 못했습니다.");
          state.revision=current.position_revision??0;
        }
        const saved=await boundedApi(`/api/library/${state.id}/position`,{method:"PUT",keepalive:true,
          headers:{"Content-Type":"application/json"},body:JSON.stringify({position:intent.position,audio_index:intent.audio_index,expected_revision:state.revision})},
          5000,"시청 위치 저장을 확인하지 못했습니다. 이 창에는 마지막 위치가 남아 있지만 새로고침하면 잃을 수 있습니다.");
        state.revision=saved.position_revision??null;intent.saved=true;
        if(state.latest===intent){
          const item=items.find(i=>i.id===state.id);if(item){item.position=intent.position;item.watched_at=new Date().toISOString();}
          if(activeItem?.id===state.id&&activeItem.audio_index===intent.audio_index)$("save-state").textContent=`${time(intent.position)} 저장됨`;
          if(!dialog.open&&filter!=="recommended")render();
        }
      }catch(e){
        state.revision=null;intent.failed=true;
        if(state.latest===intent){
          if(activeItem?.id===state.id&&activeItem.audio_index===intent.audio_index)$("save-state").textContent="위치 저장 미확인 · 새로고침 전 연결 확인";
          if(!activeItem||activeItem.id===state.id)toast(e.message,true);
        }
      }
    }
  }finally{state.running=false;}
}
async function waitForPosition(pending){
  let timer;
  try{return await Promise.race([pending.then(()=>true),new Promise(resolve=>{timer=setTimeout(()=>resolve(false),1000);})]);}
  finally{clearTimeout(timer);}
}
async function closePlayer() {
  playerRequest++;resetPreviews();video.pause();clearTimeout(saveTimer); saveTimer=null;
  const pending=savePosition();
  activeItem=null;resetSubtitles();resetPreference();resetTitle();video.removeAttribute("src");video.load();dialog.close();
  if(filter === "recommended")refreshRecommendations();else render();
  // Close immediately; only callers that need a fresh history read wait briefly.
  if(!await waitForPosition(pending)&&!dialog.open)toast("시청 위치를 저장하고 있습니다. 저장 확인 전에 새로고침하면 마지막 위치를 잃을 수 있습니다.");
}
$("player-close").addEventListener("click",closePlayer);
dialog.addEventListener("cancel",e=>{e.preventDefault();closePlayer();});
$("restart-video").addEventListener("click",()=>{video.currentTime=0;savePosition();video.play().catch(()=>{});});
video.addEventListener("play",()=>{entryAwaitingPlay=false;});
video.addEventListener("timeupdate",()=>{if(!saveTimer) saveTimer=setTimeout(()=>{saveTimer=null;savePosition();},4000);});
video.addEventListener("pause",()=>savePosition()); video.addEventListener("seeked",()=>savePosition()); video.addEventListener("ended",()=>savePosition());
video.addEventListener("error",async()=>{
  if(!activeItem)return;
  const failedItem=activeItem;
  $("video-error").textContent="이 브라우저에서 영상을 재생할 수 없습니다. 파일 상태와 브라우저의 코덱 지원을 확인해 주세요.";
  $("video-error").hidden=false;$("save-state").textContent="재생할 수 없음";
  try {
    // The media element does not expose a content endpoint's JSON error. Read
    // its newly detected file state once, without changing a newer playback.
    const current=await api(`/api/library/${failedItem.id}`);
    if(activeItem!==failedItem)return;
    const listed=items.find(item=>item.id===failedItem.id);
    if(listed){listed.available=current.available;listed.unavailable_reason=current.unavailable_reason;}
    if(!current.available)$("video-error").textContent=message(current.unavailable_reason||"managed_file_missing");
    render();
  } catch(e) { if(activeItem===failedItem)$("video-error").textContent=e.message; }
});
document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="hidden")savePosition(true);});
window.addEventListener("pagehide",()=>savePosition(true));
for(const id of ["import-top","import-empty"]) $(id).addEventListener("click",chooseFile);
$("upload-cancel").addEventListener("click",()=>upload?.abort());
$("file-input").addEventListener("change",()=>importFile($("file-input").files[0]));
$("search").addEventListener("input",render);
$("nav-all").addEventListener("click",()=>{filter="all";render();});
$("nav-continue").addEventListener("click",()=>{filter="continue";render();});
$("nav-recommended").addEventListener("click",()=>{filter="recommended";refreshRecommendations();});
window.addEventListener("focus",()=>{if(filter === "recommended")refreshRecommendations();});
document.addEventListener("keydown",e=>{if(e.key==="/"&&!dialog.open&&!$("settings-dialog").open&&e.target.tagName!=="INPUT"){e.preventDefault();$("search").focus();}});
let dragDepth=0;
document.addEventListener("dragenter",e=>{if(e.dataTransfer?.types.includes("Files")){e.preventDefault();dragDepth++;if(!dialog.open&&!$("settings-dialog").open)$("drop-overlay").hidden=false;}});
document.addEventListener("dragover",e=>{if(e.dataTransfer?.types.includes("Files"))e.preventDefault();});
document.addEventListener("dragleave",()=>{dragDepth=Math.max(0,dragDepth-1);if(!dragDepth)$("drop-overlay").hidden=true;});
document.addEventListener("drop",e=>{e.preventDefault();dragDepth=0;$("drop-overlay").hidden=true;if(dialog.open||$("settings-dialog").open)return;if(e.dataTransfer.files.length!==1)return toast("한 번에 한 개의 영상을 선택해 주세요.");importFile(e.dataTransfer.files[0]);});
// A fragment carries no token and is removed before any HTTP call. The server
// validates identity. Item links do not opt a video into recommendations.
function takeMomentEntry(){
  const kind=location.hash.startsWith("#item=")?"item":location.hash.startsWith("#moment=")?"moment":null;
  if(!kind)return null;
  const fragment=location.hash.slice(kind==="item"?6:8);history.replaceState(null,"",location.pathname);
  try{
    if(fragment.length>2048)throw new Error();
    const entry=JSON.parse(decodeURIComponent(fragment));
    if(!entry||typeof entry.item_id!=="string"||!/^[a-f0-9]{32}$/.test(entry.item_id))throw new Error();
    if(kind==="item"&&(entry.version!==1||Object.keys(entry).sort().join(",")!=="file_id,item_id,library_id,server_id,sha256,version"||["server_id","library_id","file_id","sha256"].some(key=>typeof entry[key]!=="string"||!(key==="sha256"?/^[a-f0-9]{64}$/:/^[a-f0-9]{32}$/).test(entry[key]))))throw new Error();
    return {kind,value:entry};
  }catch{toast(errors[kind==="item"?"invalid_item_entry":"invalid_moment_entry"],true);return {kind,value:null};}
}
let momentRequest=0, settleMomentSession;
const momentSession=new Promise(resolve=>{settleMomentSession=resolve;});
const initialMoment=takeMomentEntry();
window.addEventListener("hashchange",async()=>{
  const entry=takeMomentEntry();if(!entry)return;
  const request=++momentRequest,player=++playerRequest;
  pendingItemEntry=null;
  $("item-entry-notice").hidden=true; $("item-entry-prepare").onclick=null;
  if(!entry.value)return;
  await momentSession;
  if(!sessionToken||request!==momentRequest||player!==playerRequest)return;
  await openPlayer(entry.value.item_id,entry.value,entry.kind);
});
(async()=>{try{const session=await api("/api/session");sessionToken=session.token;settleMomentSession();const d=session.diagnostics;renderModelSetup(d.models);const notes=[];if(!d.ffprobe||!d.ffmpeg)notes.push("FFmpeg와 ffprobe를 설치한 뒤 앱을 다시 시작해 주세요. 현재 영상 가져오기가 제한될 수 있습니다.");if(d.recovered_copies)notes.push(`중단된 가져오기 사본 ${d.recovered_copies}개를 복구 폴더에 보존했습니다. 보관함에 자동 추가되지 않았으며 원본에서 다시 가져올 수 있습니다.`);if(notes.length){$("diagnostic").textContent=notes.join(" ");$("diagnostic").hidden=false;}await refresh();if(initialMoment?.value&&momentRequest===0)await openPlayer(initialMoment.value.item_id,initialMoment.value,initialMoment.kind);}catch(e){$("diagnostic").textContent=e.message;$("diagnostic").hidden=false;}finally{settleMomentSession();$("loading-state").hidden=true;}})();

let subtitleTimer=null, subtitleJob=null, subtitleLoaded=null, subtitleTracks=[], geminiConfigured=false;
const subtitleCommands=new Map();
let subtitleMonitor=null;
function newSubtitleMonitor(){const now=performance.now();return {started:now,advanced:now,key:null,completed:0,until:0,reads:0,reading:false,confirming:false,stopped:false,error:""};}
function subtitleTaskControls(){
  const command=subtitleCommands.get(activeItem?.id),pending=!!command?.pending;
  const blocked=!captionView||pending||!!command?.uncertain||!!subtitleMonitor?.stopped||!!subtitleMonitor?.confirming;
  for(const action of ["generate","retranslate","resume","restart"])$("subtitle-"+action).disabled=blocked;
  // Pausing remains available when automatic status checks have stopped.
  $("subtitle-pause").disabled=pending;
  $("subtitle-refresh").hidden=!(command?.uncertain||subtitleMonitor?.stopped||subtitleMonitor?.confirming);
  $("subtitle-refresh").disabled=pending||!!subtitleMonitor?.reading;
  $("subtitle-refresh").textContent=subtitleMonitor?.confirming?"상태 확인 중…":"상태 다시 확인";
  const note=command?.pending?"요청을 확인하고 있습니다. 같은 작업을 다시 보내지 않습니다.":subtitleMonitor?.confirming?"저장된 자막 상태를 다시 확인하고 있습니다. 기존 자막은 계속 감상할 수 있습니다.":command?.error||subtitleMonitor?.error;
  if(note)subtitleError(note);
}
function observeSubtitleProgress(monitor,job){
  if(!job||!["queued","running"].includes(job.state))return false;
  if(monitor.stopped)return false;
  const now=performance.now(),key=[job.id,job.attempt,job.state,job.stage].join(":"),completed=job.stage==="translation"?job.completed||0:job.asr_completed||0,until=job.asr_until||0;
  if(key!==monitor.key){monitor.key=key;monitor.completed=completed;monitor.until=until;monitor.advanced=now;}
  else if(completed>monitor.completed||until>monitor.until){monitor.completed=Math.max(monitor.completed,completed);monitor.until=Math.max(monitor.until,until);monitor.advanced=now;}
  const reason=now-monitor.started>=600000||monitor.reads>=400?"상태 자동 확인의 10분·400회 한도에 도달했습니다.":now-monitor.advanced>=300000?"5분 동안 저장된 구간이 늘지 않아 상태 자동 확인을 멈췄습니다.":"";
  if(reason){monitor.stopped=true;monitor.error=reason+" 서버 작업은 계속 진행될 수 있습니다. 상태를 다시 확인해 주세요.";return false;}
  return true;
}
async function subtitleCommand(owner,path,options,{pause=false}={}){
  const previous=subtitleCommands.get(owner.id);
  if(activeItem!==owner||previous?.pending||(!pause&&(previous?.uncertain||subtitleMonitor?.stopped||subtitleMonitor?.confirming||!captionView)))return;
  clearTimeout(subtitleTimer);subtitleReadVersion++;subtitleMonitor=newSubtitleMonitor();
  const command={pending:null,uncertain:false,error:""};subtitleCommands.set(owner.id,command);
  command.pending=boundedApi(path,options,30000,"요청 응답을 확인하지 못했습니다. 서버에서 처리됐을 수 있으니 상태를 다시 확인해 주세요.");
  subtitleTaskControls();
  try{await command.pending;subtitleCommands.delete(owner.id);}
  catch(e){
    command.uncertain=!e.code||["internal_error","storage_unavailable","insufficient_space"].includes(e.code);
    command.error=e.message+(command.uncertain?" 자동으로 다시 요청하지 않습니다.":"");
  }finally{
    command.pending=null;
    if(activeItem?.id===owner.id){
      if(!command.error)await refreshSubtitles(activeItem);
      else subtitleTaskControls();
    }
  }
}
const subtitleMessages={
  asr_truncated:"전사 출력이 잘려 작업을 중단했습니다. 완료한 구간은 보존했습니다.",
  alignment_unresolved:"일부 대사의 시간을 확정하지 못했습니다. 원문과 정렬 결과를 보존했습니다. 기존 영상·자막은 계속 볼 수 있습니다.",
  alignment_text_mismatch:"정렬 결과와 원문이 일치하지 않습니다. 해당 원문을 보존하고 자막 생성을 중단했습니다.",
  alignment_language_unsupported:"이 구간의 언어는 현재 시간 정렬에서 지원되지 않습니다. 원문을 보존했습니다.",
  gemini_key_missing:"Gemini API 키가 설정되지 않았습니다. 설치 안내에 따라 GEMINI_API_KEY를 설정한 뒤 앱을 다시 시작해 주세요.",
  gemini_auth_failed:"Gemini API 키 또는 프로젝트 권한을 확인해 주세요. 완료한 번역은 보존했습니다.",
  gemini_quota:"Gemini 사용 한도에 도달했습니다. 결제·할당량을 확인한 뒤 재개해 주세요. 완료한 번역은 보존했습니다.",
  gemini_unavailable:"Gemini에 연결하지 못했습니다. 연결을 확인한 뒤 재개해 주세요. 완료한 번역은 보존했습니다.",
  gemini_blocked:"Gemini가 이 번역을 거절해 중단했습니다. 원문과 완료한 번역은 보존했습니다.",
  gemini_response_invalid:"Gemini 응답이 완전한 자막 형식이 아니어서 중단했습니다. 완료한 번역은 보존했습니다.",
  model_settings_invalid:"자막 장치 설정이 올바르지 않습니다. 설치 안내의 CPU·GPU 설정을 확인해 주세요.",
  model_torch_unavailable:"자막 실행 엔진을 불러오지 못했습니다. PyTorch 설치와 Windows 런타임을 확인해 주세요.",
  model_cuda_unavailable:"PyTorch에서 NVIDIA GPU를 사용할 수 없습니다. CUDA용 PyTorch와 NVIDIA 드라이버를 확인해 주세요. CPU 사용은 별도로 설정해야 합니다.",
  model_asr_cuda_unavailable:"음성 인식 엔진에서 NVIDIA GPU를 찾지 못했습니다. CTranslate2의 CUDA 지원과 드라이버를 확인해 주세요.",
  model_asr_runtime_unavailable:"음성 인식 실행 환경을 불러오지 못했습니다. CTranslate2와 CUDA 라이브러리 설치를 확인해 주세요.",
  model_asr_precision_unavailable:"음성 인식에 필요한 연산 형식을 이 장치에서 사용할 수 없습니다. 실행 환경 또는 CPU 설정을 확인해 주세요.",
  model_audio_runtime_unavailable:"음성 처리 엔진을 불러오지 못했습니다. PyTorch와 TorchAudio를 같은 버전·CPU/CUDA 구성으로 설치해 주세요.",
  model_runtime_incompatible:"자막 실행 패키지 간 호환성을 확인하지 못했습니다. 안내된 모델 환경으로 다시 설치해 주세요.",
  model_check_failed:"실행 환경 확인을 완료하지 못했습니다. 앱을 다시 시작한 뒤 확인해 주세요.",
  model_check_timeout:"실행 환경 확인이 제한 시간을 넘겨 중단됐습니다. 진행 중인 다른 작업을 확인한 뒤 다시 시도해 주세요.",
  model_privacy_setup_required:"현재 프로세스에 허용되지 않은 추론 엔진이 로드됐습니다. 앱을 종료하고 안내된 로컬 모델 환경으로 다시 실행해 주세요. 가진 자막과 원본은 보존됩니다.",
  processing_worker_active:"이전 처리 프로세스가 종료되는 중입니다. 원본은 감상할 수 있으며, 종료 후 처리를 재개할 수 있습니다.",
  processing_busy:"이 영상의 다른 자막 작업이 있습니다. 현재 작업에서 재개해 주세요.",
  processing_checkpoint_invalid:"저장된 처리 정보가 올바르지 않아 재사용을 중단했습니다. 기존 자막과 원본은 보존했습니다.",
  local_models_missing:"로컬 자막 모델이 준비되지 않았습니다. 설치 안내의 모델 준비를 확인해 주세요. 가진 한국어 SRT는 바로 열 수 있습니다.",
  model_runtime_missing:"자막 실행 패키지가 필요합니다. 설치 안내를 확인해 주세요.",
  processing_interrupted:"앱 종료로 처리가 중단됐습니다.",
  processing_config_changed:"모델이나 실행 설정이 바뀌어 이전 결과를 이어 쓸 수 없습니다. 이전 설정으로 재개하거나 현재 설정으로 처음부터 다시 만들어 주세요.",
  no_speech_detected:"음성을 찾지 못했습니다. 음성 트랙과 영상을 확인해 주세요.",
  translation_input_too_long:"한 구간이 너무 길어 번역을 중단했습니다. 원문은 보존했습니다.",
  translation_truncated:"번역이 끝나지 않아 완료로 처리하지 않았습니다.",
  processing_failed:"자막 처리에 실패했습니다. 모델 설치와 메모리를 확인하고 재개해 주세요.",
  worker_stopped:"처리 프로세스가 종료됐습니다. 완료한 구간부터 재개할 수 있습니다.",
  invalid_subtitles:"자막 형식이나 시간이 올바르지 않습니다. 영상 길이에 맞는 SRT를 선택해 주세요.",
  subtitle_no_usable_cues:"이 영상에 표시할 자막이 없습니다. 빈 구간과 영상 길이 밖의 구간을 제외한 결과입니다. 다른 SRT를 선택해 주세요.",
  subtitle_utf8_required:"UTF-8로 저장한 SRT 파일을 선택해 주세요.",
  subtitle_encoding_unsupported:"UTF-8 또는 CP949·EUC-KR로 저장한 SRT 파일을 선택해 주세요.",
  model_bf16_unavailable:"이 GPU에서 필요한 번역 정밀도를 사용할 수 없습니다. 모델 설정과 드라이버를 확인해 주세요.",
  subtitles_too_large:"자막 파일이 너무 큽니다. 2 MiB 이하 SRT를 선택해 주세요.",
  subtitles_already_available:"이미 사용할 자막이 있습니다. 자막 목록에서 선택해 주세요."
};
function renderModelSetup(result){
  const device=result?.device==="cuda"?"NVIDIA GPU":result?.device==="cpu"?"CPU":"미확인";
  $("model-device").textContent=`선택 장치: ${device}${result?.selection==="configured"?" · 지정한 설정":result?.selection==="default"?" · 기본 설정":""}`;
  $("model-check-state").textContent=result?.error?(subtitleMessages[result.error]||message(result.error)):result?.state==="ready"?"기본 실행 환경을 확인했습니다. 실제 영상의 처리 속도와 메모리 사용은 별도 확인이 필요합니다.":"영상 없이 이 기기의 자막 실행 환경만 확인합니다. 장치를 자동으로 바꾸지 않습니다.";
}
$("model-check").addEventListener("click",async()=>{
  const button=$("model-check"),hadFocus=document.activeElement===button;button.disabled=true;$("model-check-state").textContent="실행 환경 확인 중…";
  try{renderModelSetup(await api("/api/models/diagnostics",{method:"POST"}));}
  catch(e){$("model-check-state").textContent=e.code==="processing_worker_active"?"자막 처리 중에는 진단할 수 없습니다. 작업을 마치거나 일시정지한 뒤 다시 확인해 주세요.":e.message;}
  finally{button.disabled=false;if(hadFocus&&$("settings-dialog").open&&document.activeElement===document.body)button.focus();}
});
let captionView=null, captionViewVersion=0, captionSaving=false, captionSaveError="", captionNativeHidden=false, subtitleReadVersion=0;
const pendingCaptionViews=new Map();
function captionKey(owner){return `${owner.id}:${owner.audio_index||0}`;}
function renderCaptionView(){
  const offset=captionView?.offset_ms||0,disabled=!captionView||captionSaving||!!captionSaveError;
  $("subtitle-select").disabled=disabled;
  $("caption-earlier").disabled=disabled||!subtitleLoaded||captionNativeHidden||offset<=-10000;
  $("caption-later").disabled=disabled||!subtitleLoaded||captionNativeHidden||offset>=10000;
  $("caption-reset").disabled=disabled||!subtitleLoaded||captionNativeHidden||!offset;
  $("caption-auto").disabled=disabled;
  $("caption-offset-brief").textContent=offset?`${Math.abs(offset/1000).toFixed(1)}초 ${offset<0?"앞당김":"늦춤"}`:"원래 시간";
  $("caption-view-state").textContent=captionSaving?"자막 설정 저장 중…":captionSaveError?captionSaveError+" 현재 감상에는 적용했지만 저장 여부를 확인하지 못했습니다.":!captionView?"자막 설정을 확인하고 있어요.":captionView.selection===null?"다시 열면 최신 자막을 자동으로 선택합니다.":`오디오 ${(activeItem?.audio_index||0)+1}의 자막 설정을 이 기기에 저장했습니다. 다른 자막을 선택하면 원래 시간으로 시작합니다.`;
  $("caption-view-retry").hidden=!captionSaveError;
}
async function saveCaptionView(selection,offset_ms=0,keepNative=false){
  const owner=activeItem;
  if(!owner||!captionView||captionSaving||captionSaveError)return;
  const version=++captionViewVersion,key=captionKey(owner);
  const value={selection,offset_ms,revision:captionView.revision};
  captionView=value;captionSaving=true;renderCaptionView();
  if(selection===null)subtitleLoaded=null;
  const chosen=selection===null?(subtitleTracks.find(t=>(t.audio_index||0)===(owner.audio_index||0))?.id||""):selection;
  $("subtitle-select").value=chosen;
  if(!keepNative)loadSubtitle(chosen,true);
  const pending=boundedApi(`/api/library/${owner.id}/caption-view`,{method:"PUT",keepalive:true,headers:{"Content-Type":"application/json"},body:JSON.stringify({...value,audio_index:owner.audio_index||0})},30000,"자막 설정 저장 응답을 확인하지 못했습니다. 저장 상태를 다시 확인해 주세요.");
  pendingCaptionViews.set(key,pending);
  try{
    const saved=await pending;
    if(activeItem===owner&&captionViewVersion===version)captionView=saved;
  }catch(e){
    if(activeItem===owner&&captionViewVersion===version)captionSaveError=e.message;
  }finally{
    if(pendingCaptionViews.get(key)===pending)pendingCaptionViews.delete(key);
    if(activeItem===owner&&captionViewVersion===version){captionSaving=false;renderCaptionView();syncNativeCaptionView();refreshSubtitles(owner);}
  }
}
for(const [id,delta] of [["caption-earlier",-500],["caption-later",500],["caption-reset",0]])$(id).addEventListener("click",()=>{
  if(subtitleLoaded&&captionView)saveCaptionView(subtitleLoaded,delta?Math.min(10000,Math.max(-10000,captionView.offset_ms+delta)):0);
});
$("caption-auto").addEventListener("click",()=>saveCaptionView(null));
$("caption-view-retry").addEventListener("click",()=>{
  if(!activeItem)return;captionViewVersion++;captionView=null;captionSaveError="";subtitleLoaded=null;renderCaptionView();refreshSubtitles(activeItem,{confirm:true});
});
function resetSubtitles(){clearTimeout(subtitleTimer);subtitleTimer=null;subtitleMonitor=newSubtitleMonitor();subtitleJob=null;subtitleLoaded=null;subtitleTracks=[];captionViewVersion++;captionView=null;captionSaving=false;captionSaveError="";captionNativeHidden=false;renderCaptionView();geminiConfigured=false;renderSubtitleNotes();resetSubtitleSearch(true);video.querySelectorAll("track").forEach(t=>t.remove());$("subtitle-select").replaceChildren(new Option("자막 끄기",""));$("subtitle-state").textContent="자막 확인 중…";subtitleTaskControls();}
function selectedSubtitle(){const [id,view]=(subtitleLoaded||"").split(":");return {track:subtitleTracks.find(t=>t.id===id),transcript:view==="transcript"};}
function renderSubtitleNotes(){
  const {track,transcript}=selectedSubtitle(),notes=[];
  if(transcript)notes.push("음성 인식으로 만든 원문 자막입니다. 실제 대사와 다를 수 있습니다.");
  if(!transcript&&track?.review_count)notes.push(`가독성 확인이 필요한 표시 구간 ${track.review_count}개${track.fast_count?` · 읽기 속도가 빠른 구간 ${track.fast_count}개`:""}. 번역 내용을 생략하지 않고 표시했습니다.`);
  if(track?.timing_review_count)notes.push(`시간 정렬 확인이 필요한 음성 구간 ${track.timing_review_count}개. 원문과 원래 시간값을 보존했습니다.`);
  const imported=track?.import_notes;
  if(imported){
    if(imported.empty)notes.push(`빈 자막 ${imported.empty}개 제외`);
    if(imported.outside)notes.push(`영상 밖 자막 ${imported.outside}개 제외`);
    if(imported.clipped)notes.push(`영상 끝에 맞춘 자막 ${imported.clipped}개`);
    if(imported.reordered)notes.push("시간순으로 정렬");
    if(imported.settings)notes.push(`파일 위치 설정 ${imported.settings}개 생략`);
    if(notes.length)notes.push("가져온 자막 원본은 그대로 보존했습니다.");
  }
  if(track&&(track.audio_index||0)!==(activeItem?.audio_index||0))notes.unshift(`오디오 ${(track.audio_index||0)+1}에서 만든 자막입니다. 현재 음성과 다를 수 있습니다.`);
  $("subtitle-notes").textContent=notes.join(" · ");$("subtitle-notes").hidden=!notes.length;
  renderRetranslation();renderPreparationSummary();
}
function renderRetranslation(){
  const {track}=selectedSubtitle();
  $("subtitle-retranslate").hidden=!(track?.can_retranslate??track?.has_transcript)||!!(subtitleJob&&["queued","running","paused"].includes(subtitleJob.state));
  $("subtitle-translator-panel").hidden=!!(subtitleJob&&["queued","running","paused"].includes(subtitleJob.state));
  $("subtitle-generate").textContent="Gemini로 자막 만들기";
  $("subtitle-retranslate").textContent="Gemini로 다시 번역";
  $("subtitle-cloud-note").hidden=false;
  $("subtitle-cloud-note").textContent=`새 자막의 음성 인식은 이 기기에서 Qwen으로 실행하고 시간에 맞춥니다. 인식·저장된 대사와 앞뒤 문맥 텍스트를 Google로 보내 한국어로 번역합니다. 영상·음성 파일은 보내지 않습니다. API 사용료가 발생합니다. ${geminiConfigured?"API 키가 설정되어 있습니다. 연결은 번역을 시작할 때 확인합니다.":"API 키 설정이 필요합니다. 설치 안내를 확인해 주세요."} 중단 후 재개하면 처리 중이던 요청이 다시 전송되어 과금될 수 있습니다. 재개·처음부터 다시는 기존 작업의 번역 엔진을 유지합니다.`;
}
function renderPreparationSummary(){
  const j=subtitleJob,{track,transcript}=selectedSubtitle();
  let label=subtitleTracks.some(t=>(t.audio_index||0)===(activeItem?.audio_index||0))?"자막 준비됨":"파일 열기 · 자동 생성";
  if(track?.import_notes&&Object.values(track.import_notes).some(Boolean))label="가져온 자막 보정 내역";
  if(track?.fallback_count)label=`원문 ${track.fallback_count}구간`;
  if(track?.review_count)label=`표시 확인 ${track.review_count}구간`;
  if(transcript)label="원문 · 자동 전사";
  if(track&&(track.audio_index||0)!==(activeItem?.audio_index||0))label=`다른 오디오의 자막 · ${(track.audio_index||0)+1}`;
  if(j?.state==="paused")label="일시정지";
  if(j?.state==="queued")label="대기 중";
  if(j?.state==="running")label=j.stage==="translation"?`번역 중 · ${j.completed}/${j.total}`:"음성 인식 중";
  if(j?.error)label="처리 확인 필요";
  if(j&&["queued","running","paused"].includes(j.state)&&(j.audio_index||0)!==(activeItem?.audio_index||0))label=`오디오 ${(j.audio_index||0)+1} · ${label}`;
  if($("subtitle-brief").textContent!==label)$("subtitle-brief").textContent=label;
}
function subtitleError(text){$("subtitle-state").textContent=text;$("subtitle-brief").textContent="자막 확인 필요";}
function loadSubtitle(id,force=false){
  if(!activeItem)return;
  if(subtitleLoaded===id&&!force){renderSubtitleNotes();renderCaptionView();return;}
  captionNativeHidden=false;
  video.querySelectorAll("track").forEach(t=>t.remove());subtitleLoaded=id;
  renderSubtitleNotes();renderCaptionView();
  resetSubtitleSearch(false, id ? "loading" : "empty");
  if(!id)return;
  const owner=activeItem,{track:chosen,transcript}=selectedSubtitle();
  if(!chosen||(transcript&&!chosen.has_transcript))return;
  const query=new URLSearchParams();if(transcript)query.set("transcript","true");if(captionView?.offset_ms)query.set("offset_ms",String(captionView.offset_ms));
  const track=document.createElement("track");track.kind="subtitles";track.srclang=transcript?"und":chosen.language||"ko";track.label=transcript?"원문 · 자동 전사":chosen.language&&chosen.language!=="ko"?chosen.language:"한국어";track.default=true;track.src=`/api/library/${owner.id}/subtitles/${chosen.id}.vtt${query.size?"?"+query:""}`;
  track.dataset.offsetMs=String(captionView?.offset_ms||0);
  track.addEventListener("load",()=>{
    if(activeItem!==owner||subtitleLoaded!==id||track.parentNode!==video)return;
    subtitleSearch={owner, id, track:track.track, state:"ready", cues:null};
    renderSubtitleSearch();
  });
  track.addEventListener("error",()=>{if(activeItem===owner&&subtitleLoaded===id&&track.parentNode===video){subtitleError("자막을 불러올 수 없습니다. 파일 상태와 앱 연결을 확인해 주세요.");resetSubtitleSearch(false,"error");}});
  video.append(track);
  // Select now; a later load must preserve any native Off chosen while loading.
  if(track.track)track.track.mode="showing";
}
async function refreshSubtitles(owner,{confirm=false}={}){
  clearTimeout(subtitleTimer);
  if(activeItem!==owner)return;
  if(confirm){subtitleMonitor=newSubtitleMonitor();subtitleMonitor.confirming=true;}
  const monitor=subtitleMonitor,version=captionViewVersion,readVersion=++subtitleReadVersion;
  monitor.reading=true;subtitleTaskControls();
  try{
    const pending=[pendingCaptionViews.get(captionKey(owner)),subtitleCommands.get(owner.id)?.pending].filter(Boolean);
    await Promise.all(pending.map(p=>p.catch(()=>{})));
    if(activeItem!==owner||version!==captionViewVersion||readVersion!==subtitleReadVersion)return;
    monitor.reads++;
    const data=await boundedApi(`/api/library/${owner.id}/subtitles${audioQuery(owner)}`,{},30000,"자막 상태 응답을 확인하지 못했습니다. 기존 영상과 자막은 유지됩니다. 상태를 다시 확인해 주세요.");if(activeItem!==owner||version!==captionViewVersion||readVersion!==subtitleReadVersion)return;
    const command=subtitleCommands.get(owner.id);
    if(confirm||(command&&!command.pending&&!command.uncertain))subtitleCommands.delete(owner.id);
    if(!monitor.stopped)monitor.error="";
    if(!captionView){captionView=data.view||{selection:null,offset_ms:0,revision:0};captionSaveError="";}
    subtitleTracks=data.tracks;geminiConfigured=!!data.gemini_configured;
    const select=$("subtitle-select"),was=select.value;
    select.replaceChildren(new Option("자막 끄기",""));
    for(const [i,t] of data.tracks.entries()){
      const version=` · ${data.tracks.length-i}${(owner.audio_tracks||[]).length>1?` · 오디오 ${(t.audio_index||0)+1}`:""}`;
      select.add(new Option(`${t.source==="supplied"?`가져온 자막 · ${t.language||"ko"}`:t.provider==="gemini"?"한국어 · Gemini":"한국어 · 자동 번역"}${version}${t.fallback_count?` · 원문 ${t.fallback_count}구간`:""}`,t.id));
      if(t.has_transcript)select.add(new Option(`원문 · 자동 전사${version}`,`${t.id}:transcript`));
    }
    const matching=data.tracks.filter(t=>(t.audio_index||0)===(owner.audio_index||0));
    const chosen=captionView.selection!==null?captionView.selection:subtitleLoaded===null?(matching[0]?.id||""):was;
    select.value=[...select.options].some(o=>o.value===chosen)?chosen:"";if(!(captionNativeHidden&&chosen==="")&&(chosen||subtitleLoaded!==null||captionView.selection!==null))loadSubtitle(select.value);
    renderCaptionView();
    if(chosen&&select.value!==chosen)$("caption-view-state").textContent="저장한 자막을 찾을 수 없습니다. 사용할 자막을 직접 선택해 주세요.";
    subtitleJob=data.jobs.find(j=>["queued","running","paused"].includes(j.state))||data.jobs.find(j=>(j.audio_index||0)===(owner.audio_index||0))||null;
    const j=subtitleJob,busy=j&&["queued","running"].includes(j.state);
    const generate=$("subtitle-generate");
    generate.hidden=!!(j&&["queued","running","paused"].includes(j.state));
    generate.textContent=matching.length?"새 자막 만들기":"한국어 자막 만들기";
    generate.dataset.regenerate=matching.length?"true":"false";
    $("subtitle-pause").hidden=!busy;$("subtitle-resume").hidden=!j||!["paused","failed"].includes(j.state);$("subtitle-restart").hidden=$("subtitle-resume").hidden;
    $("subtitle-restart").textContent=j?.source_track_id?"번역 처음부터 다시":"처음부터 다시 만들기";
    renderRetranslation();
    const progress=$("subtitle-progress");progress.hidden=!busy;if(j?.stage==="translation"&&j.total)progress.value=j.completed/j.total*100;else progress.removeAttribute("value");
    const paused=j?.state==="paused"&&(!j.error||j.error==="processing_interrupted");
    const asrNote=j?.asr_completed?`음성 인식 ${j.asr_completed}구간을 저장했습니다. 재개하면 저장된 다음 말소리 구간부터 이어갑니다.`:"아직 저장된 말소리 구간이 없어 재개하면 음성 인식을 처음부터 다시 합니다.";
    const resumeNote=j?.stage==="asr"?`${asrNote} 현재 구간은 다시 처리할 수 있으며 기존 자막은 보존됩니다.`:`전사와 번역 ${j?.completed||0}구간을 저장했습니다. 재개하면 저장된 다음 구간부터 이어갑니다.`;
    $("subtitle-state").textContent=paused?`${j.error?subtitleMessages[j.error]:"자막 처리를 일시정지했습니다."} ${resumeNote}`:j?.error?(subtitleMessages[j.error]||message(j.error)):busy?(j.stage==="translation"?`한국어 번역 중 · ${j.completed}/${j.total} 구간 저장됨${j.fallback_count?` · 원문 ${j.fallback_count}구간`:""}`:`음성 인식 중 · ${j.asr_completed||0}구간 저장됨. 중단하면 현재 말소리 구간을 다시 처리합니다. 원본은 계속 감상할 수 있습니다.`):data.tracks.length?"자막이 준비됐습니다. 번역하지 못한 구간은 [원문]으로 표시합니다. 새로 만들어도 기존 자막은 보존됩니다.":"가진 한국어 SRT를 열거나 이 기기에서 자막을 만들 수 있습니다.";
    if(observeSubtitleProgress(monitor,j)&&!subtitleCommands.get(owner.id)?.uncertain){clearTimeout(subtitleTimer);subtitleTimer=setTimeout(()=>refreshSubtitles(owner),1500);}
    if(j&&(j.audio_index||0)!==(owner.audio_index||0))$("subtitle-state").textContent=`오디오 ${(j.audio_index||0)+1}의 자막 작업입니다. `+$("subtitle-state").textContent;
    if(j?.provider==="gemini")$("subtitle-state").textContent="Gemini · "+$("subtitle-state").textContent+(["queued","running","paused","failed"].includes(j.state)?" 완료한 구간은 재사용합니다. 처리 중이던 요청은 재개할 때 다시 전송되어 과금될 수 있습니다.":"");
    renderPreparationSummary();
  }catch(e){if(activeItem===owner&&version===captionViewVersion&&readVersion===subtitleReadVersion){monitor.stopped=true;monitor.error=e.message+" 상태 자동 확인을 멈췄습니다. 서버 작업은 계속 진행될 수 있습니다.";if(!captionView){captionSaveError=e.message;renderCaptionView();}}}
  finally{if(activeItem===owner&&version===captionViewVersion&&readVersion===subtitleReadVersion){monitor.reading=false;monitor.confirming=false;subtitleTaskControls();}}
}
$("subtitle-refresh").addEventListener("click",()=>{if(activeItem&&!$("subtitle-refresh").disabled)refreshSubtitles(activeItem,{confirm:true});});
$("subtitle-select").addEventListener("change",()=>saveCaptionView($("subtitle-select").value));
$("subtitle-import").addEventListener("click",()=>$("subtitle-input").click());
$("subtitle-input").addEventListener("change",async()=>{
  const owner=activeItem,version=captionViewVersion,file=$("subtitle-input").files[0],language=$("subtitle-import-language").value;if(!owner||!file)return;
  try{if(file.size>2*1024*1024)throw new Error(subtitleMessages.subtitles_too_large);
    const extension=file.name.split(".").pop().toLowerCase();
    if(!["srt","vtt"].includes(extension))throw new Error("SRT 또는 VTT 자막 파일을 선택해 주세요.");
    const query=new URLSearchParams({audio_index:String(owner.audio_index||0),language,format:extension==="vtt"?"webvtt":"srt"});
    const imported=await api(`/api/library/${owner.id}/subtitles?${query}`,{method:"POST",headers:{"Content-Type":"application/octet-stream"},body:file});
    if(activeItem===owner&&version===captionViewVersion){
      await refreshSubtitles(owner);
      if(activeItem===owner&&version===captionViewVersion)await saveCaptionView(imported.id);
    }
  }catch(e){toast(e.message,true);}finally{$("subtitle-input").value="";}
});
$("subtitle-generate").addEventListener("click",()=>{const owner=activeItem;if(!owner)return;const suffix=$("subtitle-generate").dataset.regenerate==="true"?"/regenerate":"";subtitleCommand(owner,`/api/library/${owner.id}/subtitle-jobs${suffix}${audioQuery(owner)}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({provider:"gemini"})});});
$("subtitle-retranslate").addEventListener("click",async()=>{
  const owner=activeItem,{track}=selectedSubtitle();if(!owner||!(track?.can_retranslate??track?.has_transcript))return;
  await subtitleCommand(owner,`/api/library/${owner.id}/subtitles/${track.id}/retranslate`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({provider:"gemini"})});
});
for(const action of ["pause","resume","restart"])$("subtitle-"+action).addEventListener("click",()=>{const owner=activeItem,job=subtitleJob;if(!owner||!job)return;subtitleCommand(owner,`/api/subtitle-jobs/${job.id}/${action}`,{method:"POST"},{pause:action==="pause"});});

let subtitleSearch={state:"empty",cues:[]}, subtitleSearchTimer=null,subtitleSearchRender=0;
const SUBTITLE_PAGE_SIZE=50;
function subtitleSearchText(value){return value.normalize("NFKC").toLocaleLowerCase().replace(/\s+/gu," ").trim();}
function subtitleSearchMatches(cues,query){
  const matches=[];
  for(let i=0;i<cues.length;i++){
    const cue=cues[i];
    if(cue.searchText.includes(query)){matches.push(cue);continue;}
    const next=cues[i+1];
    // Only two consecutive, non-overlapping cues separated by at most 0.5 s.
    // Overlapping speakers and longer pauses must not become one sentence.
    if(!next||!Number.isFinite(cue.end)||next.start<cue.end||next.start-cue.end>0.5+1e-9)continue;
    if(!cue.searchText||!next.searchText)continue;
    // A display boundary may split either words (Japanese) or a spaced phrase.
    // The match must actually consume text on both sides of that boundary.
    const crosses=[" ",""].some(separator=>{
      const joined=cue.searchText+separator+next.searchText,index=joined.indexOf(query);
      return index>=0&&index<cue.searchText.length&&index+query.length>cue.searchText.length+separator.length;
    });
    if(crosses)matches.push({...cue,text:cue.text+"\n"+next.text});
  }
  return matches;
}
function resetSubtitleSearch(clearQuery=false,state="empty"){
  clearTimeout(subtitleSearchTimer);subtitleSearchTimer=null;
  subtitleSearch={state,cues:[]};
  if(clearQuery){$("subtitle-query").value="";$("subtitle-search-panel").open=false;}
  renderSubtitleSearch();
}
function renderSubtitleSearch(){
  const results=$("subtitle-results"),status=$("subtitle-search-status"),version=++subtitleSearchRender;results.replaceChildren();results.scrollTop=0;
  $("subtitle-pages").hidden=true;$("subtitle-page-previous").disabled=true;$("subtitle-page-next").disabled=true;
  const notices={empty:"자막을 선택해 주세요.",loading:"자막을 불러오는 중입니다.",error:"자막을 불러오지 못했습니다. 자막을 다시 선택해 주세요."};
  if(subtitleSearch.state!=="ready"){status.textContent=notices[subtitleSearch.state];return;}
  if(subtitleSearch.owner!==activeItem||subtitleSearch.id!==subtitleLoaded)return;
  if(subtitleSearch.track.mode!=="showing"){subtitleSearch.page=0;status.textContent="플레이어에서 선택한 자막을 켜 주세요.";return;}
  // Search only the selected, already-loaded text track. No query/history API.
  const query=subtitleSearchText($("subtitle-query").value);
  if(!query){subtitleSearch.query=null;subtitleSearch.matches=[];subtitleSearch.page=0;status.textContent="대사나 단어를 입력하면 해당 장면으로 이동할 수 있어요.";return;}
  const selected=subtitleSearch;
  // Disabled native tracks expose null cues, including when loading finishes Off.
  // Read after the loaded track is showing; keep plain text only for this selection.
  if(selected.cues===null)selected.cues=Array.from(selected.track.cues||[]).map(cue=>{
    const text=cue.getCueAsHTML().textContent;return {start:cue.startTime,end:cue.endTime,text,searchText:subtitleSearchText(text)};
  });
  if(selected.query!==query){selected.query=query;selected.matches=subtitleSearchMatches(selected.cues,query);selected.page=0;}
  const count=selected.matches.length;
  selected.page=Math.max(0,Math.min(selected.page||0,Math.ceil(count/SUBTITLE_PAGE_SIZE)-1));
  const start=selected.page*SUBTITLE_PAGE_SIZE,end=Math.min(start+SUBTITLE_PAGE_SIZE,count);
  $("subtitle-pages").hidden=count<=SUBTITLE_PAGE_SIZE;
  $("subtitle-page-previous").disabled=start===0;$("subtitle-page-next").disabled=end===count;
  for(const cue of selected.matches.slice(start,end)){
    const row=document.createElement("li"),button=document.createElement("button"),stamp=document.createElement("span"),text=document.createElement("span");
    button.type="button";button.className="subtitle-result";
    stamp.className="subtitle-result-time";stamp.textContent=time(cue.start);
    text.textContent=cue.text;button.append(stamp,text);
    button.setAttribute("aria-label",`${time(cue.start)} 장면으로 이동, ${cue.text}`);
    button.addEventListener("click",()=>{
      if(version!==subtitleSearchRender||subtitleSearch!==selected||activeItem!==selected.owner||subtitleLoaded!==selected.id||selected.track.mode!=="showing")return;
      if(video.readyState<1||!Number.isFinite(video.duration))return toast("영상이 준비된 뒤 다시 선택해 주세요.");
      if(!Number.isFinite(cue.start)||cue.start<0||cue.start>=video.duration)return toast("이 장면으로 이동할 수 없습니다.",true);
      try{video.currentTime=cue.start;video.play().catch(()=>toast("장면을 찾았습니다. 재생 버튼을 눌러 주세요."));video.scrollIntoView({block:"center"});}
      catch{toast("장면으로 이동하지 못했습니다. 영상 상태를 확인해 주세요.",true);}
      // The existing seeked handler persists the completed seek, not a speculative position.
    });
    row.append(button);results.append(row);
  }
  status.textContent=count?`${count}개 일치 · ${start+1}–${end}번째 · 선택하면 해당 장면을 재생합니다.`:"일치하는 자막이 없습니다.";
}
for(const [id,delta] of [["subtitle-page-previous",-1],["subtitle-page-next",1]])$(id).addEventListener("click",()=>{
  if($(id).disabled||$("subtitle-pages").hidden)return;
  subtitleSearch.page+=delta;renderSubtitleSearch();
  const first=$("subtitle-results").querySelector("button");if(first){first.focus({preventScroll:true});first.scrollIntoView({block:"nearest"});}
});
$("subtitle-query").addEventListener("input",()=>{
  clearTimeout(subtitleSearchTimer);
  // Invalidate retained buttons immediately, before the debounced replacement.
  subtitleSearchRender++;$("subtitle-results").replaceChildren();$("subtitle-pages").hidden=true;
  $("subtitle-page-previous").disabled=true;$("subtitle-page-next").disabled=true;
  if(subtitleSearch.state==="ready")$("subtitle-search-status").textContent="자막에서 찾고 있어요.";
  subtitleSearchTimer=setTimeout(()=>{subtitleSearchTimer=null;renderSubtitleSearch();},150);
});
function syncNativeCaptionView(){
  const element=video.querySelector("track");
  if(!element?.track||!subtitleLoaded||!captionView||captionSaving||captionSaveError)return;
  if(element.track.mode==="disabled"&&captionView.selection!==""){
    captionNativeHidden=true;saveCaptionView("",0,true);
  }else if(element.track.mode==="showing"&&captionNativeHidden){
    captionNativeHidden=false;saveCaptionView(subtitleLoaded,Number(element.dataset.offsetMs)||0,true);
  }
}
video.textTracks?.addEventListener?.("change",()=>{
  // Native caption controls also invalidate retained result callbacks.
  subtitleSearch={...subtitleSearch};renderSubtitleSearch();
  syncNativeCaptionView();
});

function preparationRun(current){
  const started=performance.now(),progress=new Map();let requests=0;
  function remaining(){
    if(!current())throw new Error("준비를 멈췄습니다. 완료한 내용은 보존됩니다.");
    const left=600000-(performance.now()-started);
    if(left<=0||requests>=256)throw new Error("한 번의 준비가 10분 또는 요청 한도에 도달해 멈췄습니다. 완료한 내용은 보존되며 다시 준비하면 이어집니다.");
    return left;
  }
  return {
    async request(path,options={}){
      const wait=Math.min(150000,remaining());
      requests++;
      return boundedApi(path,options,wait,"응답 대기 시간을 넘겨 멈췄습니다. 서버의 현재 묶음은 마무리될 수 있습니다. 상태를 확인한 뒤 다시 준비해 주세요.");
    },
    observe(stage,data,initial=false){
      if(!data||!['empty','partial','ready'].includes(data.state)||
          !Number.isSafeInteger(data.completed)||!Number.isSafeInteger(data.total)||
          data.completed<0||data.total<0||data.total>120||data.completed>data.total||
          (data.state==='ready'&&(data.total===0||data.completed!==data.total)))
        throw new Error("준비 진행 상태를 확인할 수 없어 멈췄습니다. 저장된 내용은 보존됩니다.");
      const before=progress.get(stage)||{completed:0,stalled:0};
      const stalled=initial||data.completed>before.completed?0:before.stalled+1;
      progress.set(stage,{completed:Math.max(before.completed,data.completed),stalled});
      if(data.state!=='ready'&&stalled>=2)
        throw new Error("두 번 연속 준비가 진행되지 않아 멈췄습니다. 완료한 내용은 보존됩니다. 상태를 확인한 뒤 다시 준비해 주세요.");
    }
  };
}

let previewView={version:0,data:null,building:false,paused:false,owner:null,readVersion:0};
function resetPreviews(){
  resetScenes();
  previewView={version:previewView.version+1,data:null,building:false,paused:false,owner:null,readVersion:0};
  $("preview-panel").open=false;$("preview-grid").replaceChildren();$("preview-state").textContent="이 영상의 미리보기를 확인합니다.";$("preview-build").hidden=false;$("preview-build").disabled=false;$("preview-build").textContent="미리보기 만들기";$("preview-pause").hidden=true;
}
function previewCurrent(view){return previewView===view&&activeItem?.id===view.owner;}
function renderPreviews(view){
  if(!previewCurrent(view))return;
  const data=view.data,grid=$("preview-grid"),build=$("preview-build");
  build.hidden=data?.state==="ready";build.disabled=view.building;build.textContent=data?.completed?"이어서 만들기":"미리보기 만들기";$("preview-pause").hidden=!view.building;
  $("preview-state").textContent=view.building?`${data?.completed||0}/${data?.total||"…"}개 저장됨 · 닫거나 멈추면 현재 묶음까지 저장합니다.`:data?.state==="ready"?`${data.completed}개 준비됨${data.failed?` · ${data.failed}개는 프레임을 만들지 못했습니다`:""} · 선택하면 해당 시점으로 이동합니다.`:data?.completed?`${data.completed}/${data.total}개 저장됨 · 이어서 만들 수 있습니다.`:"필요할 때 이 기기에서 최대 120개의 작은 미리보기를 만듭니다.";
  // Append checkpoints without replacing focused/visible earlier tiles on every batch.
  for(const frame of data?.frames||[]){
    let row=grid.querySelector(`[data-ordinal="${frame.ordinal}"]`);
    if(row&&row.dataset.available===String(frame.available))continue;
    const wasFocused=row?.contains(document.activeElement);
    const next=document.createElement("li");next.dataset.ordinal=frame.ordinal;next.dataset.available=frame.available;
    function addRetry(){if(next.querySelector(".preview-retry"))return;const retry=document.createElement("button");retry.type="button";retry.className="button button-quiet preview-retry";retry.textContent="다시 만들기";retry.setAttribute("aria-label",`${time(frame.time)} 미리보기 다시 만들기`);retry.disabled=view.building;retry.addEventListener("click",()=>{if(previewCurrent(view))buildPreviews(frame.ordinal);});next.append(retry);}
    const button=document.createElement("button");button.type="button";button.className="preview-frame";button.setAttribute("aria-label",`${time(frame.time)} 시점으로 이동`);
    const picture=document.createElement("span");picture.className="preview-picture";
    if(frame.available){const img=document.createElement("img");img.alt="";img.loading="lazy";img.src=frame.image;img.addEventListener("error",()=>{img.hidden=true;picture.textContent="미리보기 표시 실패";addRetry();});picture.append(img);}
    else picture.textContent="프레임 없음";
    const stamp=document.createElement("span");stamp.className="preview-time";stamp.textContent=time(frame.time);button.append(picture,stamp);
    button.addEventListener("click",()=>{
      if(!previewCurrent(view))return;
      if(video.readyState<1||!Number.isFinite(video.duration))return toast("영상이 준비된 뒤 다시 선택해 주세요.");
      if(!Number.isFinite(frame.time)||frame.time<0||frame.time>=video.duration)return toast("현재 재생 구간 밖의 미리보기입니다.");
      try{video.currentTime=frame.time;video.play().catch(()=>toast("시점을 찾았습니다. 재생 버튼을 눌러 주세요."));video.scrollIntoView({block:"center"});}
      catch{toast("이 시점으로 이동하지 못했습니다.",true);}
    });next.append(button);
    if(!frame.available)addRetry();
    if(row)row.replaceWith(next);else grid.append(next);
    if(wasFocused)button.focus();
  }
  grid.querySelectorAll(".preview-retry").forEach(button=>button.disabled=view.building);
}
$("preview-panel").addEventListener("toggle",async()=>{
  if(!$("preview-panel").open){previewView.paused=true;return;}
  if(!activeItem)return;
  const view=previewView;view.owner=activeItem.id;
  if(view.building)return;
  const readVersion=++view.readVersion;
  $("preview-state").textContent="저장된 미리보기를 불러오고 있어요.";
  try{const data=await api(`/api/library/${view.owner}/previews`);if(!previewCurrent(view)||view.readVersion!==readVersion)return;view.data=data;renderPreviews(view);}
  catch(e){if(previewCurrent(view)&&view.readVersion===readVersion)$("preview-state").textContent=e.message;}
});
async function buildPreviews(retry=null){
  const view=previewView;if(!activeItem||view.building)return;view.owner=activeItem.id;view.building=true;view.paused=false;
  const run=preparationRun(()=>previewCurrent(view)&&!view.paused);
  view.readVersion++;
  const hadFocus=$("preview-build")===document.activeElement||document.activeElement?.classList.contains("preview-retry");renderPreviews(view);
  try{
    if(view.data)run.observe('previews',view.data,true);
    do{
      const suffix=retry===null?"":`/${retry}/retry`;
      const data=await run.request(`/api/library/${view.owner}/previews${suffix}`,{method:"POST"});
      if(!previewCurrent(view))return;
      run.observe('previews',data,retry!==null);
      if(retry!==null){const row=$("preview-grid").querySelector(`[data-ordinal="${retry}"]`);if(row)row.dataset.available="refresh";}
      view.data=data;renderPreviews(view);
    }while(retry===null&&view.data.state!=="ready"&&!view.paused&&$("preview-panel").open&&$("subtitle-search-panel").open);
  }catch(e){if(previewCurrent(view)){view.building=false;renderPreviews(view);$("preview-state").textContent=e.message+" 저장된 미리보기와 원본 재생은 유지됩니다.";}return;}
  finally{
    if(previewCurrent(view)){view.building=false;$("preview-build").disabled=false;$("preview-pause").hidden=true;}
    if(hadFocus&&previewCurrent(view)&&document.activeElement===document.body)$("preview-panel").querySelector("summary").focus();
  }
  renderPreviews(view);
}
$("preview-build").addEventListener("click",()=>buildPreviews());
$("preview-pause").addEventListener("click",()=>{previewView.paused=true;$("preview-state").textContent="현재 묶음을 저장한 뒤 멈춥니다.";});

let sceneView={owner:null,busy:false,ready:false,paused:false,version:0};
function sceneCurrent(view){return sceneView===view&&activeItem?.id===view.owner;}
function sceneControls(view){
  if(!sceneCurrent(view))return;
  $("scene-prepare").disabled=view.busy;$("scene-prepare").hidden=view.ready;
  $("scene-pause").hidden=!view.building;$("scene-search").disabled=view.busy||!view.ready;
}
function resetScenes(){
  sceneView={owner:null,busy:false,ready:false,paused:false,version:0};
  $("scene-panel").open=false;$("scene-query").value="";$("scene-results").replaceChildren();
  $("scene-prepare").hidden=false;$("scene-prepare").disabled=false;$("scene-pause").hidden=true;$("scene-search").disabled=true;
  $("scene-state").textContent="검색 준비와 검색은 이 기기에서만 실행합니다.";
}
$("scene-panel").addEventListener("toggle",async()=>{
  if(!$("scene-panel").open){sceneView.paused=true;return;}
  if(!activeItem||sceneView.busy)return;
  const view=sceneView;view.owner=activeItem.id;const readVersion=view.readVersion=(view.readVersion||0)+1;
  try{const data=await api(`/api/library/${view.owner}/scenes`);
    if(!sceneCurrent(view)||view.readVersion!==readVersion)return;
    view.ready=data.state==="ready";$("scene-state").textContent=`${data.completed}/${data.total}개 화면 분석 준비됨 · 검색어는 저장하지 않습니다.`;sceneControls(view);
  }catch(e){if(sceneCurrent(view)&&view.readVersion===readVersion){view.ready=false;sceneControls(view);$("scene-state").textContent=e.message;}}
});
$("scene-prepare").addEventListener("click",async()=>{
  const view=sceneView;if(!sceneCurrent(view)||view.busy)return;
  view.busy=true;view.building=true;view.paused=false;view.version++;view.readVersion=(view.readVersion||0)+1;sceneControls(view);
  const run=preparationRun(()=>sceneCurrent(view)&&!view.paused);
  $("scene-results").replaceChildren();$("scene-state").textContent="저장된 미리보기부터 확인하고 있어요.";
  try{
    // Detect missing models before spending time making a new preview grid.
    try{const data=await run.request(`/api/library/${view.owner}/scenes`);run.observe('scenes',data,true);}catch(e){if(e.code!=="scene_previews_required")throw e;}
    let grid=await run.request(`/api/library/${view.owner}/previews`);run.observe('previews',grid,true);
    while(sceneCurrent(view)&&!view.paused&&grid.state!=="ready"){
      grid=await run.request(`/api/library/${view.owner}/previews`,{method:"POST"});
      if(!sceneCurrent(view))return;
      run.observe('previews',grid);
      if(sceneCurrent(view))$("scene-state").textContent=`미리보기 ${grid.completed}/${grid.total}개 저장됨 · 닫거나 멈추면 현재 묶음까지 저장합니다.`;
    }
    while(sceneCurrent(view)&&!view.paused){
      $("scene-state").textContent="화면을 분석하고 있어요. 영상은 계속 감상할 수 있습니다.";
      const data=await run.request(`/api/library/${view.owner}/scenes/prepare`,{method:"POST"});
      if(!sceneCurrent(view))return;
      run.observe('scenes',data);
      view.ready=data.state==="ready";$("scene-state").textContent=`${data.completed}/${data.total}개 화면 분석 저장됨`;
      if(view.ready){$("scene-state").textContent+=` · 준비됐어요. 찾고 싶은 화면을 적어 주세요.`;break;}
    }
    if(sceneCurrent(view)&&view.paused)$("scene-state").textContent+=" · 멈췄습니다. 다시 준비하면 이어집니다.";
  }catch(e){if(sceneCurrent(view))$("scene-state").textContent=e.message;}
  finally{if(sceneCurrent(view)){view.busy=false;view.building=false;sceneControls(view);}}
});
$("scene-pause").addEventListener("click",()=>{sceneView.paused=true;$("scene-state").textContent="현재 묶음을 저장한 뒤 멈춥니다.";});
$("subtitle-search-panel").addEventListener("toggle",()=>{if(!$("subtitle-search-panel").open)sceneView.paused=true;});
$("scene-query").addEventListener("input",()=>{sceneView.version++;$("scene-results").replaceChildren();});
$("scene-form").addEventListener("submit",async event=>{
  event.preventDefault();const view=sceneView,query=$("scene-query").value.trim();
  if(!sceneCurrent(view)||view.busy||!view.ready||!query)return;
  view.busy=true;view.readVersion=(view.readVersion||0)+1;const version=++view.version;sceneControls(view);$("scene-results").replaceChildren();$("scene-state").textContent="이 영상에서 비슷한 화면을 찾고 있어요.";
  try{
    const data=await api(`/api/library/${view.owner}/scenes/search`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query})});
    if(!sceneCurrent(view)||view.version!==version||!$("scene-panel").open)return;
    for(const [index,frame] of data.candidates.entries()){
      const row=document.createElement("li"),button=document.createElement("button"),picture=document.createElement("span"),img=document.createElement("img"),stamp=document.createElement("span");
      button.type="button";button.className="preview-frame";button.setAttribute("aria-label",`후보 ${index+1}, ${time(frame.time)} 시점으로 이동`);
      picture.className="preview-picture";img.alt="";img.src=frame.image;picture.append(img);
      img.addEventListener("error",()=>{picture.textContent="이미지 확인 실패";button.disabled=true;});
      stamp.className="preview-time";stamp.textContent=`후보 ${index+1} · ${time(frame.time)}`;button.append(picture,stamp);
      button.addEventListener("click",()=>{
        if(!sceneCurrent(view)||view.version!==version)return;
        if(video.readyState<1||!Number.isFinite(video.duration))return toast("영상이 준비된 뒤 다시 선택해 주세요.");
        if(!Number.isFinite(frame.time)||frame.time<0||frame.time>=video.duration)return toast("현재 재생 구간 밖의 후보입니다.");
        try{video.currentTime=frame.time;video.play().catch(()=>toast("시점을 찾았습니다. 재생 버튼을 눌러 주세요."));video.scrollIntoView({block:"center"});}
        catch{toast("이 시점으로 이동하지 못했습니다.",true);}
      });row.append(button);$("scene-results").append(row);
    }
    $("scene-state").textContent=data.searched?`${data.searched}/${data.sampled}개 화면에서 찾은 후보${data.black_skipped?` · 검은 화면 ${data.black_skipped}개 제외`:""} · 이미지로 확인하고 선택하세요.`:"저장된 미리보기가 모두 검은 화면이라 비교할 이미지가 없습니다. 영상 전체에 장면이 없다는 뜻은 아닙니다. 직접 재생하거나 시간별 미리보기로 확인해 주세요.";
  }catch(e){if(sceneCurrent(view)&&view.version===version){$("scene-state").textContent=e.message;if(["scene_index_required","scene_model_changed","scene_previews_required"].includes(e.code))view.ready=false;}}
  finally{if(sceneCurrent(view)){view.busy=false;sceneControls(view);if(view.version!==version)$("scene-state").textContent="검색어가 바뀌었습니다. 후보 찾기를 다시 눌러 주세요.";}}
});
