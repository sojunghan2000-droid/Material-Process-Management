import streamlit as st
import base64
import time
import json
import os
from PIL import Image
from google.cloud import aiplatform
from google.oauth2 import service_account

# ============================================================
# 1. 설정 (Streamlit Secrets에서 로드)
# ============================================================
PROJECT_ID  = st.secrets.get("PROJECT_ID",  os.environ.get("PROJECT_ID",  ""))
ENDPOINT_ID = st.secrets.get("ENDPOINT_ID", os.environ.get("ENDPOINT_ID", ""))
LOCATION    = st.secrets.get("LOCATION",    os.environ.get("LOCATION",    "us-central1"))

# ============================================================
# 2. Vertex AI 초기화
#    - Streamlit Cloud: secrets["gcp_service_account"] JSON 사용
#    - 로컬: gcloud ADC 자동 사용
# ============================================================
@st.cache_resource
def init_vertex_ai():
    if "gcp_service_account" in st.secrets:
        # Streamlit Cloud 환경: Secrets의 JSON 키로 인증
        sa_info = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(
            sa_info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        aiplatform.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)
    else:
        # 로컬 환경: gcloud ADC 자동 인증
        aiplatform.init(project=PROJECT_ID, location=LOCATION)
    return aiplatform.Endpoint(ENDPOINT_ID)

# ============================================================
# 페이지 설정
# ============================================================
st.set_page_config(
    page_title="Smart Factory - Welding Inspector",
    page_icon="🏭",
    layout="centered",
)

# ============================================================
# 커스텀 CSS
# ============================================================
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }
    .header-box {
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 16px;
        padding: 2rem 1.5rem;
        text-align: center;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .header-box h1 { color: #e94560; font-size: 1.8rem; margin-bottom: 0.3rem; }
    .header-box p  { color: #a0a0b0; font-size: 0.95rem; }

    .status-row { display: flex; gap: 0.8rem; margin-bottom: 1.5rem; }
    .status-card {
        flex: 1;
        background: #1a1a2e;
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    .status-card .label { color: #a0a0b0; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; }
    .status-card .value { color: #e94560; font-size: 1.4rem; font-weight: bold; margin-top: 0.3rem; }
    .status-card .value.green { color: #4ecca3; }
    .status-card .value.blue  { color: #00b4d8; }

    .result-defect {
        background: linear-gradient(135deg, #2d0a0a 0%, #1a0000 100%);
        border: 2px solid #e94560;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        animation: pulse-red 2s infinite;
    }
    .result-normal {
        background: linear-gradient(135deg, #0a2d1a 0%, #001a0a 100%);
        border: 2px solid #4ecca3;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
    }
    .result-defect h2 { color: #e94560; }
    .result-normal h2 { color: #4ecca3; }
    .result-defect p, .result-normal p { color: #d0d0d0; }

    @keyframes pulse-red {
        0%, 100% { box-shadow: 0 0 10px rgba(233, 69, 96, 0.3); }
        50%       { box-shadow: 0 0 25px rgba(233, 69, 96, 0.6); }
    }
    .footer {
        text-align: center; color: #505060; font-size: 0.8rem;
        margin-top: 2rem; padding: 1rem; border-top: 1px solid #1a1a2e;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 세션 상태 초기화
# ============================================================
if "total_inspected" not in st.session_state:
    st.session_state.total_inspected = 0
if "defect_count" not in st.session_state:
    st.session_state.defect_count = 0
if "normal_count" not in st.session_state:
    st.session_state.normal_count = 0

# ============================================================
# 헤더
# ============================================================
st.markdown("""
<div class="header-box">
    <h1>🏭 Smart Factory</h1>
    <p style="font-size:1.3rem; color:#e94560; font-weight:bold;">
        Welding Defect Detector
    </p>
    <p>Powered by Google Vertex AI &middot; AutoML Vision</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 실시간 대시보드
# ============================================================
total = st.session_state.total_inspected
defects = st.session_state.defect_count
normals = st.session_state.normal_count
defect_rate = f"{(defects / total * 100):.1f}%" if total > 0 else "—"

st.markdown(f"""
<div class="status-row">
    <div class="status-card">
        <div class="label">Total Inspected</div>
        <div class="value blue">{total}</div>
    </div>
    <div class="status-card">
        <div class="label">Defects</div>
        <div class="value">{defects}</div>
    </div>
    <div class="status-card">
        <div class="label">Normal</div>
        <div class="value green">{normals}</div>
    </div>
    <div class="status-card">
        <div class="label">Defect Rate</div>
        <div class="value">{defect_rate}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 이미지 입력 (카메라 / 파일 업로드)
# ============================================================
st.markdown("### 📸 Capture or Upload")
tab_camera, tab_upload = st.tabs(["Camera", "File Upload"])

img_file = None
with tab_camera:
    img_file_cam = st.camera_input("용접 부위를 촬영해주세요")
    if img_file_cam:
        img_file = img_file_cam

with tab_upload:
    img_file_up = st.file_uploader(
        "용접 사진을 업로드하세요",
        type=["jpg", "jpeg", "png", "bmp"],
    )
    if img_file_up:
        img_file = img_file_up

# ============================================================
# 분석 수행
# ============================================================
if img_file is not None:
    st.image(img_file, caption="Input Image", use_container_width=True)

    if st.button("🔍 AI 판독 시작", use_container_width=True):
        with st.spinner("Vertex AI가 분석 중입니다..."):
            try:
                endpoint = init_vertex_ai()

                image_bytes = img_file.getvalue()
                encoded_image = base64.b64encode(image_bytes).decode("utf-8")
                instances = [{"content": encoded_image}]
                response = endpoint.predict(instances=instances)

                predictions = response.predictions[0]
                labels = predictions["displayNames"]
                confidences = predictions["confidences"]

                max_idx = confidences.index(max(confidences))
                best_label = labels[max_idx]
                best_score = confidences[max_idx] * 100

                # 카운터 업데이트
                st.session_state.total_inspected += 1
                is_defect = best_label.lower() in ("defect", "bad weld")
                if is_defect:
                    st.session_state.defect_count += 1
                else:
                    st.session_state.normal_count += 1

                # 결과 표시
                st.divider()
                if is_defect:
                    st.markdown(f"""
                    <div class="result-defect">
                        <h2>🚨 DEFECT DETECTED</h2>
                        <p style="font-size:1.2rem;"><b>{best_label}</b></p>
                        <p>AI 확신도: <b>{best_score:.1f}%</b></p>
                        <hr style="border-color:#e94560;">
                        <p>⚠️ 즉시 라인을 정지하고 관리자를 호출하세요!</p>
                    </div>
                    """, unsafe_allow_html=True)
                    st.toast("DEFECT DETECTED! Line stop required.", icon="🚨")
                else:
                    st.markdown(f"""
                    <div class="result-normal">
                        <h2>✅ NORMAL</h2>
                        <p style="font-size:1.2rem;"><b>{best_label}</b></p>
                        <p>AI 확신도: <b>{best_score:.1f}%</b></p>
                        <hr style="border-color:#4ecca3;">
                        <p>정상 제품입니다. 다음 공정으로 이동합니다.</p>
                    </div>
                    """, unsafe_allow_html=True)

                # 전체 클래스 확률 표시
                with st.expander("📊 Detailed Prediction Results"):
                    for lbl, conf in zip(labels, confidences):
                        st.markdown(f"**{lbl}**")
                        st.progress(conf)
                        st.caption(f"{conf * 100:.2f}%")

            except Exception as e:
                st.error(f"예측 중 에러가 발생했습니다: {e}")

# ============================================================
# 푸터
# ============================================================
st.markdown("""
<div class="footer">
    Smart Factory Welding Inspector v2.0<br>
    Powered by Google Cloud Vertex AI &middot; Built with Streamlit
</div>
""", unsafe_allow_html=True)
