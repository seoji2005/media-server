"use strict";
const $ = (id) => document.getElementById(id);
let sessionToken = "", items = [], filter = "all", activeItem = null, upload = null;
let toastTimer, saveTimer, saveChain = Promise.resolve(), lastQueuedPosition = null;
const video = $("video"), dialog = $("player-dialog");
const errors = {
  local_origin_required: "이 기기의 로컬 주소에서 다시 열어주세요.", session_required: "앱이 재시작되었습니다. 페이지를 새로고침해 주세요.",
  unsupported_container: "지원하지 않는 형식입니다. MP4 또는 WebM 영상을 선택해 주세요.", unsupported_codec: "현재 브라우저 감상용 코덱을 지원하지 않습니다. H.264/AAC MP4 또는 VP8·VP9 WebM이 필요합니다.",
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
function toast(text, error = false) { clearTimeout(toastTimer); $("toast").textContent = text; $("toast").classList.toggle("error", error); $("toast").hidden = false; toastTimer = setTimeout(() => $("toast").hidden = true, error ? 8500 : 4500); }
async function api(path, options = {}) {
  let response;
  try { response = await fetch(path, { ...options, headers: { "X-Media-Token": sessionToken, ...(options.headers || {}) } }); }
  catch { throw new Error("앱에 연결할 수 없습니다. 로컬 서버가 실행 중인지 확인해 주세요."); }
  let result;
  try { result = await response.json(); } catch { throw new Error("앱 응답을 읽을 수 없습니다."); }
  if (!response.ok) throw new Error(message(result.error));
  return result;
}
function time(seconds) { seconds = Math.max(0, Math.floor(seconds || 0)); const h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60), s = seconds % 60; return h ? `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}` : `${m}:${String(s).padStart(2,"0")}`; }
function continuing(item) { return item.position > 0 && item.position < Math.max(1, item.duration - 2); }
function render() {
  $("nav-count").textContent = String(items.length);
  const query = $("search").value.trim().toLocaleLowerCase();
  const visible = items.filter(i => (filter === "all" || continuing(i)) && i.title.toLocaleLowerCase().includes(query));
  if (filter === "continue") visible.sort((a,b) => (b.watched_at || "").localeCompare(a.watched_at || ""));
  $("library-heading").firstChild.textContent = filter === "all" ? "보관함 " : "이어보기 ";
  $("item-count").textContent = String(visible.length);
  $("breadcrumb-current").textContent = filter === "all" ? "보관함" : "이어보기";
  $("section-description").textContent = filter === "all" ? "당신의 다음 감상을 기다리는 영상들" : "머물렀던 장면에서 다시 시작하세요";
  document.querySelector(".sort-label").textContent = filter === "all" ? "최근 가져온 순" : "최근 시청한 순";
  $("nav-all").classList.toggle("selected",filter === "all"); $("nav-continue").classList.toggle("selected",filter === "continue");
  for (const [id, selected] of [["nav-all",filter === "all"],["nav-continue",filter === "continue"]]) { if(selected) $(id).setAttribute("aria-current","page"); else $(id).removeAttribute("aria-current"); }
  const grid = $("library-grid"); grid.replaceChildren();
  for (const item of visible) {
    const card = $("card-template").content.cloneNode(true);
    card.querySelector("h3").textContent = item.title;
    card.querySelector("h3").title = item.title;
    card.querySelector(".duration").textContent = time(item.duration);
    card.querySelector(".card-resolution").textContent = `${item.width} × ${item.height}`;
    const status = card.querySelector(".card-status");
    status.textContent = !item.available ? (item.unavailable_reason === "managed_file_changed" ? "보관 파일이 변경됨" : "파일을 찾을 수 없음") : continuing(item) ? `${time(item.position)}부터 이어보기` : item.position > 0 ? "시청 완료" : "아직 보지 않음";
    status.classList.toggle("missing", !item.available);
    const progress = card.querySelector("progress"); progress.value = item.position / item.duration * 100; progress.hidden = item.position === 0;
    const image = card.querySelector("img");
    if (item.thumbnail && item.available) { image.src = `/api/media/${item.id}/thumbnail`; image.addEventListener("error", () => image.hidden = true, {once:true}); } else image.hidden = true;
    const button = card.querySelector("button"); button.setAttribute("aria-label", `${item.title}, ${status.textContent}`); button.addEventListener("click", () => openPlayer(item.id));
    grid.append(card);
  }
  const empty = !visible.length; $("empty-state").hidden = !empty;
  $("import-empty").hidden = !!query || filter === "continue"; $("format-note").hidden = !!query || filter === "continue";
  $("empty-title").textContent = query ? "일치하는 영상이 없어요" : filter === "continue" ? "이어볼 영상이 아직 없어요" : "첫 번째 영상을 담아보세요";
  $("empty-description").replaceChildren();
  $("empty-description").textContent = query ? "다른 제목으로 검색해 보세요." : filter === "continue" ? "영상을 보기 시작하면 마지막 시청 위치가 여기에 남습니다." : "파일을 선택하거나 이곳에 끌어놓으세요. 원본은 그대로 두고, 감상용 사본을 안전하게 보관합니다.";
}
async function refresh() { const result = await api("/api/library"); items = result.items; render(); }
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
  xhr.addEventListener("load", async () => { let result; try {result=JSON.parse(xhr.responseText);} catch {toast("앱 응답을 읽을 수 없습니다.",true); return;} if(xhr.status>=200&&xhr.status<300){ toast(result.duplicate ? "이미 보관함에 있는 영상입니다. 기존 시청 기록을 유지했어요." : "보관함에 영상을 담았습니다."); try {await refresh();} catch(e){toast(e.message,true);} } else toast(message(result.error),true); });
  xhr.addEventListener("error", () => toast("가져오기가 중단되었습니다. 앱 연결과 원본 파일 상태를 확인해 주세요.",true));
  xhr.addEventListener("abort", () => toast("가져오기를 취소했습니다. 원본은 그대로입니다."));
  xhr.addEventListener("loadend", () => { upload=null; $("upload-status").hidden=true; $("import-top").disabled=false; $("import-empty").disabled=false; $("file-input").value=""; });
  xhr.send(file);
}
async function openPlayer(id) {
  try {
    const item = await api(`/api/library/${id}`);
    if(!item.available) return toast(message(item.unavailable_reason || "managed_file_missing"),true);
    activeItem=item; lastQueuedPosition=null; $("player-title").textContent=item.title; $("player-meta").textContent=`${item.width} × ${item.height} · ${time(item.duration)} · 원본 사본`;
    $("video-error").hidden=true; $("save-state").textContent=continuing(item) ? `${time(item.position)}에서 이어보기` : "준비 중";
    if(item.thumbnail) video.poster=`/api/media/${id}/thumbnail`; else video.removeAttribute("poster");
    video.src=`/api/media/${id}/content`; dialog.showModal();
    video.addEventListener("loadedmetadata", function restore(){ if(!activeItem||activeItem.id!==id) return; const start=continuing(item)?item.position:0; if(start>0&&Number.isFinite(video.duration)) video.currentTime=Math.min(start,video.duration); $("save-state").textContent=start>0?`${time(start)}에서 이어보기`:"재생 버튼을 눌러 시작하세요"; }, {once:true});
    // Autoplay is optional; browser policy may require the native play button.
    video.play().catch(()=>{});
  } catch(e) { toast(e.message,true); }
}
function savePosition(keepalive=false) {
  if(!activeItem||!Number.isFinite(video.currentTime)||video.readyState<1) return saveChain;
  const id=activeItem.id, position=Math.min(activeItem.duration,Math.max(0,video.currentTime));
  if(lastQueuedPosition===position) return saveChain;
  lastQueuedPosition=position; $("save-state").textContent="시청 위치 저장 중…";
  // Serialize saves so a delayed older write cannot overwrite a later seek/pause.
  saveChain=saveChain.catch(()=>{}).then(()=>api(`/api/library/${id}/position`,{method:"PUT",keepalive,headers:{"Content-Type":"application/json"},body:JSON.stringify({position})})).then(()=>{
    const item=items.find(i=>i.id===id); if(item){item.position=position;item.watched_at=new Date().toISOString();}
    if(activeItem?.id===id) $("save-state").textContent=`${time(position)} 저장됨`;
  }).catch(e=>{lastQueuedPosition=null;if(activeItem?.id===id) $("save-state").textContent="저장 실패 · 연결 확인";toast(e.message,true);});
  return saveChain;
}
async function closePlayer() { video.pause(); clearTimeout(saveTimer); saveTimer=null; await savePosition(); activeItem=null; video.removeAttribute("src"); video.load(); dialog.close(); render(); }
$("player-close").addEventListener("click",closePlayer);
dialog.addEventListener("cancel",e=>{e.preventDefault();closePlayer();});
$("restart-video").addEventListener("click",()=>{video.currentTime=0;savePosition();video.play().catch(()=>{});});
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
document.addEventListener("keydown",e=>{if(e.key==="/"&&!dialog.open&&e.target.tagName!=="INPUT"){e.preventDefault();$("search").focus();}});
let dragDepth=0;
document.addEventListener("dragenter",e=>{if(e.dataTransfer?.types.includes("Files")){e.preventDefault();dragDepth++;if(!dialog.open)$("drop-overlay").hidden=false;}});
document.addEventListener("dragover",e=>{if(e.dataTransfer?.types.includes("Files"))e.preventDefault();});
document.addEventListener("dragleave",()=>{dragDepth=Math.max(0,dragDepth-1);if(!dragDepth)$("drop-overlay").hidden=true;});
document.addEventListener("drop",e=>{e.preventDefault();dragDepth=0;$("drop-overlay").hidden=true;if(dialog.open)return;if(e.dataTransfer.files.length!==1)return toast("한 번에 한 개의 영상을 선택해 주세요.");importFile(e.dataTransfer.files[0]);});
(async()=>{try{const session=await api("/api/session");sessionToken=session.token;const d=session.diagnostics;const notes=[];if(!d.ffprobe||!d.ffmpeg)notes.push("FFmpeg와 ffprobe를 설치한 뒤 앱을 다시 시작해 주세요. 현재 영상 가져오기가 제한될 수 있습니다.");if(d.recovered_copies)notes.push(`중단된 가져오기 사본 ${d.recovered_copies}개를 복구 폴더에 보존했습니다. 보관함에 자동 추가되지 않았으며 원본에서 다시 가져올 수 있습니다.`);if(notes.length){$("diagnostic").textContent=notes.join(" ");$("diagnostic").hidden=false;}await refresh();}catch(e){$("diagnostic").textContent=e.message;$("diagnostic").hidden=false;}finally{$("loading-state").hidden=true;}})();
