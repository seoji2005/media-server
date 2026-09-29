# Windows 로컬 샘플 검증 · 2026-09-29

## 범위와 환경

기준 main은 `d133793d087f6a01bb536ab2fab03b648dd50168`이다. GitHub의 소스 200개를 blob 해시와 대조해 준비했다. 이번 장치는 사용자 소유 PC가 아닌 PC방의 Windows 10 22H2(19045.2006), i5-12400F, RAM 32GB, RTX 3070 8GB다. 목표 Windows 11/다른 GPU의 최종 최적화 결과로 사용하지 않는다.

Python 3.12.14, Node 24.19.0, Chrome 154.0.8037.58, FFmpeg/ffprobe 9.0.2와 저장소의 고정 Python/JS 의존성을 사용했다. 감상 환경과 테스트 환경은 분리했다. 설치·샘플 보관함·임시 파일은 작업 폴더에 두고 PATH는 자식 프로세스에만 지정했다. 시스템 설치·드라이버 변경·자동 시작 등록은 하지 않았다.

NVIDIA 관리 도구는 NVML 초기화 오류를 반환했다. 별도 CUDA Driver API의 cuInit은 0, 장치 수는 1, 장치 이름과 메모리는 RTX 3070/8191 MiB였다. 이는 CUDA 장치 초기화 확인이며 Torch/Qwen 추론, GPU 영상 디코딩 또는 8GB 모델 적합성 증거가 아니다.

## 실행 결과

`python -m unittest discover -s tests -q`: **365개 중 356개 통과, 9개 건너뜀, 실패 0**, 115.052초, exit 0. 건너뜀은 Linux 전용 설치 7개, 미설치 선택 모델 런타임 1개, 선택 장면 검색 실런타임 1개다. HTTPX 관련 deprecation 경고는 남아 있으며 의존성은 임의로 바꾸지 않았다.

- `python scripts/install_runtime.py --viewing-only --data-dir <sample-library> --json`: 새 감상 환경 설치와 기존 환경 재사용 모두 exit 0. FFmpeg/ffprobe 진단 통과.
- `npm test --prefix tests/ui`: 화면 로직 18개 묶음 통과. DOM/HTTP 모의 검사이며 디코딩 증거와 구분한다.
- `python tests/browser_smoke.py`: 실제 Chrome/HTTP/SQLite/FFmpeg 최초 실행·프로세스 재시작 통과. H.264/AAC 재생, 한국어 native 자막·시간 보정·문장 검색, 가져오기 결과 복구, 시청 위치 7초 복원, 원본 해시, VP9 MP4→WebM 재생, 외부 페이지 요청 0을 확인했다. 전사·번역 출력은 합성 fixture다.
- `python tests/codespaces_smoke.py --browser`: 로컬 Chrome/HTTP 최초·재시작, J/K/L, 시청 위치 18.25초와 +500ms 자막 설정 복원 통과. Codespaces 프록시는 모의이며 실제 클라우드 전달 검증이 아니다.
- 별도 30초 1280×720 합성 영상과 한국어 SRT를 실제 감상 환경에 가져와 재생했다. 프레임 디코딩과 활성 한국어 자막을 확인하고 데스크톱/좁은 화면을 시각 확인했다.
- `python scripts/harness.py check`: 문서 링크·하네스 계약 통과.

## 발견과 수정

- CI의 FFmpeg 9.0.1 다운로드 주소가 HTTP 404를 반환했다. 배포처의 버전별 GitHub Release 9.0.2 ZIP으로 고정하고 SHA256 `60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba` 및 실제 바이너리 버전을 검증했다.
- LF 상태의 .cmd가 이 Windows에서 명령 일부를 잘못 해석했다. Git checkout의 .cmd 줄바꿈을 CRLF로 명시했다. 소스 API/ZIP으로 별도 파일을 구성할 때도 배치 파일의 CRLF를 유지해야 한다.
- Python은 있지만 py.exe가 없는 이 환경에서 설치 런처가 실패했다. py.exe가 없을 때 PATH의 python으로 설치기를 실행한다. 기존 Python 3.12/64비트 사전 검증은 그대로다. 인자와 종료 코드 보존을 별도 확인했다.
- 실제 모델 캐시 복원 시간 제한 검사에서 종료 직후 임시 진단 파일의 공유 위반(WinError32)을 재현했다. 소유한 임시 진단 폴더 정리에만 약 1초의 제한된 대기를 추가했다. 다른 오류와 지속 오류는 여전히 실패하고 완료된 진단·원래 오류를 보존한다. 원본/모델 삭제, 네트워크 재시도, 프로세스 격리 정책은 바꾸지 않았다.
- 작업자 종료 검사에서 프로세스 종료 신호 직후 실제 OS 잠금이 잠깐 남는 경우가 나왔다. 기존 3초 종료 관찰 구간 안에서 프로세스 종료와 잠금 해제를 모두 확인하도록 검사했다. 8초 전체 상한·원본 해시·PCM 정리 조건은 유지한다. 즉시 pause→resume API의 무조건 성공을 의미하지 않는다.

초기 실패도 보존했다: 개발 도구의 CET 실행 오류, 초기 테스트 PATH의 Git/Chrome 검색 변수 누락, 배치 파일 줄바꿈/py.exe 문제, 종료 직후 임시 파일·작업자 잠금 경합. 성공한 검사만 골라 전체 성공으로 기록하지 않는다. Windows 설치/정리 변경은 별도 독립 검토에서 actionable finding이 없었다.

## 실제 사용할 PC에서 이어가기

1. 최신 소스를 새로 받고 Python 3.12 64비트와 FFmpeg/ffprobe를 확인한다. 이 PC의 가상환경·경로·GPU 설정을 복사하지 않는다.
2. `install-media-clarity.cmd --viewing-only`부터 실행해 원본 감상, 실제 화면 배율/오디오, 자막, 탐색·재시작을 확인한다. 사용자 지정 보관함은 설치·진단·실행에 같은 `--data-dir`을 사용한다.
3. 해당 PC의 GPU/VRAM/드라이버를 확인한 뒤 전체 자막 런타임과 고정 모델을 설치한다. 이번에는 모델 가중치·개인 영상·API 키를 저장하지 않았다. Gemini 키는 감상 PC에서 숨김 세션 입력으로 준비한다.
4. 실제 영상으로 Qwen→정렬→Gemini, 중단/재개, 40–120분 감상 품질과 메모리 사용을 검증한다. 이후 처리 스레드/해상도 등은 실제 기기 측정에 따라 조정한다. 모델·프롬프트 기본값은 이번에 변경하지 않았다.

실제 Fetch 확장 다운로드→정확한 영상 열기, 장편 자막 품질, 향상·검색/추천 품질, Qwen/Torch/Gemini 실추론은 이번 샘플 기능 검증의 완료 항목이 아니다.
