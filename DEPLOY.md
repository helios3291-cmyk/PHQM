# PHQM — 기출 조합 시험지 (Streamlit)

GitHub에는 **코드 + CSV**만 두고, 문항 PNG는 **Google Drive**에서 온디맨드로 불러옵니다.

저장소: https://github.com/helios3291-cmyk/PHQM

## 로컬 실행

```powershell
pip install -r requirements-compose.txt
# 로컬에 output/images 가 있으면 Drive 없이 동작
streamlit run compose_app.py
# 또는
.\run_compose_app.bat
```

## Streamlit Community Cloud 배포

1. 이 저장소를 [Streamlit Cloud](https://share.streamlit.io/)에 연결
2. Main file: `compose_app.py`
3. Python requirements: `requirements.txt` (또는 `requirements-compose.txt` — 둘 다 Google Drive 패키지 포함)
4. **Secrets**에 `.streamlit/secrets.toml.example` 내용을 채워 등록

## Google Drive 연동 (필수 절차)

### A. Drive 폴더 준비

로컬과 **같은 상대 경로**로 업로드하세요.

```
(내 Drive)/PHQM_images/          ← 이 폴더의 ID를 GDRIVE_FOLDER_ID 로 사용
  basic/
    2024_고1_역사_가형_1.png
    ...
  mock/
    ...
  hancert/
    ...
```

CSV의 `이미지경로`는 `output/images/basic/...` 형태입니다.  
앱은 `output/images/` 접두를 제거하고 Drive 루트(`basic/`, `mock/`, `hancert/`) 아래에서 찾습니다.

### B. Google Cloud 서비스 계정

1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. **API 및 서비스 → 라이브러리**에서 **Google Drive API** 사용 설정
3. **사용자 인증 정보 → 서비스 계정** 만들기
4. 키(JSON) 다운로드
5. Drive에서 `PHQM_images` 폴더를 서비스 계정 이메일(`...@....iam.gserviceaccount.com`)에 **뷰어**로 공유  
   (공유하지 않으면 API로 파일을 볼 수 없습니다)

### C. Secrets 설정

| 키 | 값 |
|----|-----|
| `COMPOSE_APP_PASSWORD` | 앱 접속 비밀번호 |
| `GDRIVE_FOLDER_ID` | `PHQM_images` 폴더 ID |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | 서비스 계정 JSON 전체 |

로컬: `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` 복사 후 편집  
Cloud: 앱 설정 → Secrets

### D. 동작 방식

- 목록/필터: CSV만 사용 (Drive 전체 스캔 없음)
- 미리보기·PDF 생성: 필요한 PNG만 Drive에서 받아 **`/tmp/phqm_drive_images`** 에 캐시
  (Streamlit Cloud 앱 폴더는 읽기 전용이라 프로젝트 `.cache`는 쓰지 않음)
- 로컬에 `output/images`가 있으면 **로컬 우선** (Drive 호출 없음)

### E. 이미지가 안 보일 때 체크리스트

사이드바 **Drive 진단 → 연결 테스트**를 누르면 원인 JSON이 표시됩니다.

| 증상 | 조치 |
|------|------|
| `configured: false` | Cloud Secrets에 `GDRIVE_FOLDER_ID`, `GDRIVE_SERVICE_ACCOUNT_JSON` 등록 후 재부팅 |
| `root_children` 비어 있음 | 폴더를 서비스 계정 이메일에 **뷰어 공유**. 폴더 ID가 맞는지 URL로 재확인 |
| children에 `basic` 없음 | Drive 구조를 `PHQM_images/basic|mock|hancert/...png` 로 맞추거나, `output/images`가 루트면 그 상위가 아니라 **images(또는 basic의 부모)** ID 사용 |
| `JSONDecodeError` / Invalid control character | Secrets에 넣은 JSON의 `private_key` 개행 문제. **다운로드한 JSON 파일을 수정 없이** 삼중따옴표 안에 그대로 붙이거나, 아래 TOML 테이블 방식 사용 |
| `private_key` / auth 오류 | JSON 파싱은 됐으나 키 형식 오류. 키가 잘렸는지, 서비스 계정 재발급 여부 확인 |
| `SSLError` / RECORD_LAYER_FAILURE | Streamlit Cloud 일시 SSL. 앱이 재시도함 — 잠시 후 **연결 테스트** 다시. 계속이면 Reboot |

Streamlit Secrets 예시 A (권장 — 다운로드 JSON 통째로):

```toml
COMPOSE_APP_PASSWORD = "...."
GDRIVE_FOLDER_ID = "1abc...."
GDRIVE_SERVICE_ACCOUNT_JSON = """
{다운로드한 service-account.json 내용 그대로 — 직접 개행 편집하지 마세요}
"""
```

예시 B (TOML 테이블 — `private_key` 개행을 자연스럽게 유지):

```toml
GDRIVE_FOLDER_ID = "1abc...."

[GDRIVE_SERVICE_ACCOUNT_JSON]
type = "service_account"
project_id = "your-project"
private_key_id = "...."
private_key = """
-----BEGIN PRIVATE KEY-----
(PEM 줄 그대로)
-----END PRIVATE KEY-----
"""
client_email = "....iam.gserviceaccount.com"
client_id = "...."
token_uri = "https://oauth2.googleapis.com/token"
```

## 주의

- 기출 이미지는 교육·사적 용도로만 사용하고, 공개 저장소에 PNG를 올리지 마세요.
- 서비스 계정 JSON·앱 비밀번호는 git에 커밋하지 마세요.
- 첫 PDF 생성은 문항 수만큼 다운로드가 있어 시간이 걸릴 수 있습니다.
- PDF 한글 제목/라벨용으로 `assets/fonts/NanumGothic.ttf`(Nanum Gothic, OFL)를 저장소에 포함합니다. Cloud에서도 시스템 폰트 없이 동작합니다.
