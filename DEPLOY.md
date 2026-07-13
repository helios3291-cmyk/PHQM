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
3. Python requirements: `requirements-compose.txt`
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
- 미리보기·PDF 생성: 필요한 PNG만 Drive에서 받아 `.cache/drive_images` 또는 `/tmp`에 캐시
- 로컬에 `output/images`가 있으면 **로컬 우선** (Drive 호출 없음)

## 주의

- 기출 이미지는 교육·사적 용도로만 사용하고, 공개 저장소에 PNG를 올리지 마세요.
- 서비스 계정 JSON·앱 비밀번호는 git에 커밋하지 마세요.
- 첫 PDF 생성은 문항 수만큼 다운로드가 있어 시간이 걸릴 수 있습니다.
