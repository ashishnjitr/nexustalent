import streamlit as st
import json
import re
import io
import requests
import base64
from datetime import datetime

# Streamlit Page Configuration
st.set_page_config(
    page_title="NexusTalent AI | Autonomous Recruitment & Jobscan ATS",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main { background-color: #f8fafc; }
    .stButton>button {
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.2);
    }
    .auth-card {
        background-color: #ffffff;
        padding: 32px;
        border-radius: 20px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
        max-width: 480px;
        margin: 0 auto;
    }
    .badge-matched {
        background-color: #ecfdf5;
        color: #047857;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid #a7f3d0;
        display: inline-block;
        margin: 2px;
    }
    .badge-missing {
        background-color: #fef2f2;
        color: #dc2626;
        padding: 4px 10px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid #fecaca;
        display: inline-block;
        margin: 2px;
    }
    .metric-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.03);
        transition: all 0.2s ease;
    }
    .hero-banner {
        background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
        color: white;
        padding: 28px;
        border-radius: 20px;
        margin-bottom: 24px;
        box-shadow: 0 10px 20px -5px rgba(79, 70, 229, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# GLOBAL STATE & MULTI-TENANT USER SYSTEM
# -----------------------------------------------------------------------------
if "users_db" not in st.session_state:
    # Pre-seeded users database with isolated default workspace data
    st.session_state.users_db = {
        "alex.recruiter@nexustalent.ai": {
            "password": "password123",
            "name": "Alex Rivera",
            "company": "NexusTalent Corp",
            "jobs": [
                {
                    "id": "j1",
                    "title": "Senior Full Stack Engineer",
                    "dept": "Engineering",
                    "skills": "React, TypeScript, Node.js, AWS, PostgreSQL, Docker",
                    "desc": "Looking for an experienced full stack engineer to build scalable cloud applications, design microservices, and lead technical architecture."
                },
                {
                    "id": "j2",
                    "title": "AI Research Scientist",
                    "dept": "AI Lab",
                    "skills": "Python, PyTorch, LLMs, Transformers, CUDA, Fine-Tuning",
                    "desc": "Lead research in generative models, agentic workflows, multi-modal LLM evaluation, and neural search optimization."
                }
            ],
            "candidates": [
                {
                    "id": "c1",
                    "job_id": "j1",
                    "name": "Alex Chen",
                    "role": "Senior Full Stack Engineer",
                    "score": 94,
                    "strengths": ["5+ years React & Node", "AWS Certified Developer", "Strong system architecture background"],
                    "weaknesses": ["Limited GraphQL production experience"],
                    "recommendation": "Strong Hire",
                    "summary": "Alex exhibits outstanding technical competency and directly matches core backend and frontend requirements."
                },
                {
                    "id": "c2",
                    "job_id": "j2",
                    "name": "Sarah Jenkins",
                    "role": "AI Research Scientist",
                    "score": 89,
                    "strengths": ["PhD in Computer Science", "Published papers on transformers", "Proficient in PyTorch"],
                    "weaknesses": ["Slightly fewer years in commercial production"],
                    "recommendation": "Hire",
                    "summary": "Exceptional academic background with strong foundational AI capabilities."
                }
            ],
            "activity_logs": [
                {"time": datetime.now().strftime("%H:%M:%S"), "msg": "Workspace initialized for Alex Rivera"}
            ]
        }
    }

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "current_user_email" not in st.session_state:
    st.session_state.current_user_email = None

if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = ""

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# Helper functions
def parse_uploaded_file(uploaded_file):
    """Extracts text content from PDF, DOCX, or TXT uploads safely."""
    if uploaded_file is None:
        return ""
    
    file_type = uploaded_file.name.split('.')[-1].lower()
    text_content = ""

    try:
        if file_type == "pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(uploaded_file)
                for page in reader.pages:
                    text_content += page.extract_text() + "\n"
            except Exception:
                text_content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        elif file_type in ["docx", "doc"]:
            try:
                import docx
                doc = docx.Document(uploaded_file)
                text_content = "\n".join([p.text for p in doc.paragraphs])
            except Exception:
                text_content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        else:
            text_content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    except Exception as e:
        st.error(f"Error reading file: {e}")
        text_content = ""

    return text_content.strip()


def call_gemini_api(prompt, system_instruction=None):
    """Calls Gemini 3 Flash REST API or falls back gracefully."""
    api_key = st.session_state.gemini_api_key
    
    if api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
            
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            st.warning(f"Gemini API note: {e}. Using intelligent fallback.")

    return None


def analyze_jobscan_match(jd_text, resume_text):
    """Calculates Jobscan ATS skill gaps, keyword frequency, and formatting scores."""
    jd_clean = jd_text.lower()
    resume_clean = resume_text.lower()

    hard_skills_catalog = ['react', 'typescript', 'javascript', 'node.js', 'node', 'aws', 'python', 'pytorch', 'transformers', 'docker', 'postgresql', 'graphql', 'figma', 'tailwind', 'microservices', 'ci/cd', 'rest apis', 'cuda', 'git', 'sql', 'express', 'vite']
    soft_skills_catalog = ['communication', 'leadership', 'teamwork', 'agile', 'problem solving', 'collaboration', 'adaptability', 'management', 'time management']

    jd_hard = [s for s in hard_skills_catalog if s in jd_clean]
    jd_soft = [s for s in soft_skills_catalog if s in jd_clean]

    matched_hard = [s for s in jd_hard if s in resume_clean]
    missing_hard = [s for s in jd_hard if s not in resume_clean]

    matched_soft = [s for s in jd_soft if s in resume_clean]
    missing_soft = [s for s in jd_soft if s not in resume_clean]

    has_metrics = bool(re.search(r'\b\d+%|\$\d+|\b\d+\s+(years|users|projects|clients|percent)\b', resume_text, re.I))
    has_contact = bool(re.search(r'@|\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', resume_text))
    word_count = len(resume_text.split())
    good_length = 200 <= word_count <= 1000
    has_sections = bool(re.search(r'experience|education|skills|summary', resume_text, re.I))

    hard_score = (len(matched_hard) / len(jd_hard)) * 60 if jd_hard else 45
    soft_score = (len(matched_soft) / len(jd_soft)) * 25 if jd_soft else 20
    audit_score = (sum([has_metrics, has_contact, good_length, has_sections])) * 3.75

    overall = min(98, int(hard_score + soft_score + audit_score))

    # Keyword matrix
    all_keywords = list(set(jd_hard + jd_soft))
    keyword_matrix = []
    for kw in all_keywords:
        jd_c = len(re.findall(re.escape(kw), jd_clean))
        res_c = len(re.findall(re.escape(kw), resume_clean))
        status = "Optimal" if res_c >= jd_c else ("Low" if res_c > 0 else "Missing")
        keyword_matrix.append({"keyword": kw, "jd_count": jd_c, "resume_count": res_c, "status": status})

    return {
        "overall_score": overall,
        "matched_hard": matched_hard,
        "missing_hard": missing_hard,
        "matched_soft": matched_soft,
        "missing_soft": missing_soft,
        "checklist": {
            "metrics": has_metrics,
            "contact": has_contact,
            "length": good_length,
            "word_count": word_count,
            "sections": has_sections
        },
        "keyword_matrix": keyword_matrix
    }


def perform_ai_resume_analysis(target_job_title, target_job_desc, cand_name, resume_text):
    """Generates detailed positive, negative, scoring, and hiring feedback for a resume."""
    resume_clean = resume_text.lower()
    jd_clean = (target_job_title + " " + target_job_desc).lower()

    # Attempt live Gemini AI evaluation if key is available
    prompt = f"""Perform an in-depth candidate recruitment evaluation.
Target Role: {target_job_title}
Job Description Context: {target_job_desc}
Candidate Name: {cand_name}
Resume Text: {resume_text[:3000]}

Respond ONLY in valid JSON format with the following keys:
{{
    "overall_score": <number 0-100>,
    "tech_score": <number 0-100>,
    "exp_score": <number 0-100>,
    "soft_score": <number 0-100>,
    "recommendation": <"Strong Hire" | "Hire" | "Further Review" | "Pass">,
    "positive_feedback": [<array of 3-5 specific positive strengths/pros>],
    "negative_feedback": [<array of 2-4 specific negative weaknesses/gaps/risks>],
    "summary": <string executive rationale paragraph>,
    "interview_questions": [<array of 3 probing interview questions targeting gaps>]
}}"""

    ai_raw = call_gemini_api(prompt, system_instruction="You are an expert executive talent recruiter providing detailed, objective candidate feedback.")
    if ai_raw:
        try:
            cleaned_raw = re.sub(r'```json\s*|\s*```', '', ai_raw).strip()
            data = json.loads(cleaned_raw)
            return data
        except Exception:
            pass

    # High-precision fallback analyzer
    hard_catalog = ['react', 'typescript', 'javascript', 'node.js', 'node', 'aws', 'python', 'pytorch', 'transformers', 'docker', 'postgresql', 'graphql', 'figma', 'tailwind', 'microservices', 'ci/cd', 'rest apis', 'cuda', 'git', 'sql', 'express', 'vite', 'agile', 'leadership']
    found_skills = [s for s in hard_catalog if s in resume_clean]
    missing_skills = [s for s in hard_catalog if s in jd_clean and s not in resume_clean]

    has_metrics = bool(re.search(r'\b\d+%|\$\d+|\b\d+\s+(years|users|projects|clients|percent)\b', resume_text, re.I))
    word_count = len(resume_text.split())

    tech_score = min(96, max(50, 60 + len(found_skills) * 5))
    exp_score = 88 if has_metrics else 72
    soft_score = 85 if 'leadership' in resume_clean or 'agile' in resume_clean or 'team' in resume_clean else 70
    overall_score = int((tech_score * 0.45) + (exp_score * 0.35) + (soft_score * 0.20))

    if overall_score >= 88:
        recommendation = "Strong Hire"
    elif overall_score >= 75:
        recommendation = "Hire"
    elif overall_score >= 60:
        recommendation = "Further Review"
    else:
        recommendation = "Pass"

    positives = []
    if found_skills:
        positives.append(f"Direct match in core tech stack: {', '.join([s.capitalize() for s in found_skills[:5]])}")
    if has_metrics:
        positives.append("Resume contains quantified performance metrics and measurable achievements.")
    if word_count >= 250:
        positives.append("Detailed career history with clear project responsibilities and progression.")
    positives.append("Strong technical background aligning with fundamental role requirements.")

    negatives = []
    if missing_skills:
        negatives.append(f"Lacks explicit production mention of required skills: {', '.join([s.capitalize() for s in missing_skills[:4]])}")
    else:
        negatives.append("Lacks specific production architectural benchmarks for enterprise workloads.")
    if not has_metrics:
        negatives.append("Fewer quantitative business outcomes (percentages or revenue impact) highlighted.")
    negatives.append("Cloud deployment and system scaling depth should be probed in technical round.")

    summary = f"{cand_name} demonstrates a {overall_score}% alignment for the {target_job_title} role. Key technical competencies match target requirements well, though specific areas regarding high-scale deployment require further interview verification."

    questions = [
        f"Can you detail your hands-on experience with {missing_skills[0].capitalize() if missing_skills else 'system architecture'} in a production environment?",
        "How do you measure and optimize project performance and reliability when facing tight delivery deadlines?",
        "Describe a time when you had to make a technical trade-off under resource constraints."
    ]

    return {
        "overall_score": overall_score,
        "tech_score": tech_score,
        "exp_score": exp_score,
        "soft_score": soft_score,
        "recommendation": recommendation,
        "positive_feedback": positives,
        "negative_feedback": negatives,
        "summary": summary,
        "interview_questions": questions
    }


# -----------------------------------------------------------------------------
# AUTHENTICATION GATE (MUST LOG IN / SIGN UP BEFORE ACCESSING APP)
# -----------------------------------------------------------------------------
if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_l, col_m, col_r = st.columns([1, 2, 1])
    
    with col_m:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 24px;">
            <div style="background-color: #4f46e5; width: 56px; height: 56px; border-radius: 16px; display: inline-flex; align-items: center; justify-content: center; color: white; font-size: 28px; box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.3);">
                🧠
            </div>
            <h1 style="margin-top: 12px; margin-bottom: 4px; font-weight: 800; color: #0f172a;">NexusTalent AI</h1>
            <p style="color: #64748b; font-size: 14px;">Autonomous Recruitment & ATS Matcher Platform</p>
        </div>
        """, unsafe_allow_html=True)

        auth_tab1, auth_tab2 = st.tabs(["🔒 Log In", "📝 Create Profile"])

        # TAB 1: LOG IN
        with auth_tab1:
            st.caption("Access your private recruitment workspace")
            login_email = st.text_input("Work Email", value="alex.recruiter@nexustalent.ai", key="login_email_input")
            login_password = st.text_input("Password", value="password123", type="password", key="login_pass_input")

            if st.button("Log In to Workspace", type="primary", use_container_width=True):
                email_clean = login_email.strip().lower()
                if email_clean in st.session_state.users_db:
                    user_record = st.session_state.users_db[email_clean]
                    if user_record["password"] == login_password:
                        st.session_state.authenticated = True
                        st.session_state.current_user_email = email_clean
                        st.success(f"Welcome back, {user_record['name']}!")
                        st.rerun()
                    else:
                        st.error("Incorrect password. Please check your credentials.")
                else:
                    st.error("No account found with this email. Please create a profile.")

            st.divider()
            st.info("💡 **Demo Login Credentials**\n\n**Email:** `alex.recruiter@nexustalent.ai`\n\n**Password:** `password123`")

        # TAB 2: CREATE PROFILE
        with auth_tab2:
            st.caption("Setup a new isolated recruitment profile")
            signup_name = st.text_input("Full Name", placeholder="e.g. Jordan Lee")
            signup_company = st.text_input("Company / Organization", placeholder="e.g. Acme Corp")
            signup_email = st.text_input("Work Email Address", placeholder="jordan@acme.com")
            signup_password = st.text_input("Create Password", type="password", key="signup_pass_input")

            if st.button("Create Profile & Sign In", type="primary", use_container_width=True):
                email_clean = signup_email.strip().lower()
                if not signup_name or not email_clean or not signup_password:
                    st.warning("Please fill out all required fields.")
                elif email_clean in st.session_state.users_db:
                    st.error("An account with this email already exists. Please log in.")
                else:
                    # Create new user record with clean isolated workspace state
                    st.session_state.users_db[email_clean] = {
                        "password": signup_password,
                        "name": signup_name,
                        "company": signup_company or "Organization",
                        "jobs": [],
                        "candidates": [],
                        "activity_logs": [
                            {"time": datetime.now().strftime("%H:%M:%S"), "msg": f"Account created for {signup_name}"}
                        ]
                    }
                    st.session_state.authenticated = True
                    st.session_state.current_user_email = email_clean
                    st.success(f"Profile created! Welcome to NexusTalent AI, {signup_name}!")
                    st.rerun()

    # Stop rendering app content until user is authenticated
    st.stop()


# -----------------------------------------------------------------------------
# MAIN AUTHENTICATED APPLICATION WORKSPACE
# -----------------------------------------------------------------------------
user_email = st.session_state.current_user_email
user_data = st.session_state.users_db[user_email]

# Load active user's private dataset
jobs = user_data["jobs"]
candidates = user_data["candidates"]
activity_logs = user_data["activity_logs"]


# SIDEBAR CONFIGURATION
with st.sidebar:
    st.markdown("### 🧠 NexusTalent AI")
    st.caption("Autonomous Recruitment & Jobscan Hub")
    st.divider()

    # User Profile Info Badge
    st.markdown(f"**👤 {user_data['name']}**")
    st.caption(f"🏢 {user_data['company']}")
    st.caption(f"✉️ {user_email}")

    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.current_user_email = None
        st.rerun()

    st.divider()

    # Gemini API Key Config
    api_key_input = st.text_input("Gemini API Key (Optional)", value=st.session_state.gemini_api_key, type="password")
    if api_key_input != st.session_state.gemini_api_key:
        st.session_state.gemini_api_key = api_key_input
        st.success("API Key updated!")

    st.divider()

    # App Navigation
    navigation = st.radio(
        "Navigation",
        [
            "📊 Dashboard",
            "🎛️ Jobscan ATS Matcher",
            "💼 Job Requisitions",
            "👥 Candidate Pipeline",
            "🪄 AI Resume Analyzer",
            "💬 AI Screening Chat"
        ]
    )


# PAGE 1: DASHBOARD
if navigation == "📊 Dashboard":
    # Hero Welcome Banner
    st.markdown(f"""
    <div class="hero-banner">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div>
                <h1 style="margin: 0; font-size: 28px; font-weight: 800; color: #ffffff;">Welcome back, {user_data['name']}! 👋</h1>
                <p style="margin: 6px 0 0 0; color: #e0e7ff; font-size: 14px;">Here is your real-time recruitment intelligence & pipeline health summary.</p>
            </div>
            <div style="background: rgba(255,255,255,0.15); padding: 8px 16px; border-radius: 12px; backdrop-filter: blur(8px); border: 1px solid rgba(255,255,255,0.2);">
                <span style="font-size: 12px; font-weight: 600; color: #ffffff;">🏢 Workspace: <strong>{user_data['company']}</strong></span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Quick Actions Row
    q1, q2, q3, q4 = st.columns(4)
    if q1.button("⚡ Fast AI Screener", use_container_width=True):
        st.session_state.navigation = "🪄 AI Resume Analyzer"
        st.rerun()
    if q2.button("🎛️ Jobscan ATS Matcher", use_container_width=True):
        st.session_state.navigation = "🎛️ Jobscan ATS Matcher"
        st.rerun()
    if q3.button("💼 New Requisition", use_container_width=True):
        st.session_state.navigation = "💼 Job Requisitions"
        st.rerun()
    if q4.button("👥 Candidate Pipeline", use_container_width=True):
        st.session_state.navigation = "👥 Candidate Pipeline"
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Analytics Metric Cards
    top_talent_count = len([c for c in candidates if c.get('score', 0) >= 85])
    avg_score = int(sum(c.get('score', 0) for c in candidates) / len(candidates)) if candidates else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💼 Active Requisitions", len(jobs), help="Total open positions in workspace")
    m2.metric("👥 Total Talent Pool", len(candidates), help="Total candidates evaluated across positions")
    m3.metric("⭐ Top Match Candidates", top_talent_count, f"{int((top_talent_count/len(candidates))*100) if candidates else 0}% of pipeline")
    m4.metric("📈 Avg Match Score", f"{avg_score}%", help="Average candidate match rating")

    st.divider()

    # Main Grid Layout: Pipeline Breakdown vs Active Requisition Health
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("🎯 Talent Pipeline Leaderboard")
        if candidates:
            sorted_cand = sorted(candidates, key=lambda x: x.get('score', 0), reverse=True)
            for cand in sorted_cand[:6]:
                score = cand.get('score', 0)
                rec = cand.get('recommendation', 'Hire')
                badge_bg = "#ecfdf5" if rec == "Strong Hire" else ("#eff6ff" if rec == "Hire" else ("#fffbeb" if rec == "Further Review" else "#fef2f2"))
                badge_txt = "#047857" if rec == "Strong Hire" else ("#1d4ed8" if rec == "Hire" else ("#b45309" if rec == "Further Review" else "#dc2626"))

                with st.container():
                    st.markdown(f"""
                    <div style="background-color: white; padding: 16px; border-radius: 12px; border: 1px solid #e2e8f0; margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <strong style="font-size: 16px; color: #0f172a;">{cand['name']}</strong>
                                <p style="margin: 2px 0 0 0; font-size: 12px; color: #64748b;">Role: <strong>{cand.get('role', 'General')}</strong></p>
                            </div>
                            <div style="text-align: right;">
                                <span style="background-color: {badge_bg}; color: {badge_txt}; padding: 4px 12px; border-radius: 12px; font-weight: 700; font-size: 12px;">
                                    {rec} ({score}%)
                                </span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.progress(score / 100)
        else:
            st.info("No candidates in your pipeline yet. Click **Fast AI Screener** or **Candidate Pipeline** above to add candidates.")

    with col_right:
        st.subheader("📊 Pipeline Funnel")
        if candidates:
            strong_hires = len([c for c in candidates if c.get('recommendation') == 'Strong Hire'])
            hires = len([c for c in candidates if c.get('recommendation') == 'Hire'])
            reviews = len([c for c in candidates if c.get('recommendation') == 'Further Review'])
            passes = len([c for c in candidates if c.get('recommendation') == 'Pass'])

            st.write(f"**Strong Hire:** `{strong_hires}`")
            st.progress(strong_hires / len(candidates))

            st.write(f"**Hire:** `{hires}`")
            st.progress(hires / len(candidates))

            st.write(f"**Further Review:** `{reviews}`")
            st.progress(reviews / len(candidates))

            st.write(f"**Pass:** `{passes}`")
            st.progress(passes / len(candidates))
        else:
            st.caption("Pipeline distribution metrics will populate once candidates are added.")

        st.divider()

        st.subheader("💼 Active Job Health")
        if jobs:
            for job in jobs:
                linked = [c for c in candidates if c.get('role') == job['title'] or c.get('job_id') == job['id']]
                avg_j_score = int(sum(c.get('score', 0) for c in linked) / len(linked)) if linked else 0
                st.markdown(f"**{job['title']}**")
                st.caption(f"🏢 Dept: {job['dept']} | 👥 Applicants: {len(linked)} | Avg Score: {avg_j_score}%")
                st.progress(avg_j_score / 100 if linked else 0)
        else:
            st.caption("No open job requisitions. Create one to start tracking application health.")

    st.divider()

    # Activity Log Footer
    st.subheader("🤖 Autonomous Agent Log Feed")
    log_cols = st.columns(3)
    for idx, log in enumerate(activity_logs[::-1][:6]):
        with log_cols[idx % 3]:
            st.info(f"**[{log['time']}]** {log['msg']}")


# PAGE 2: JOBSCAN ATS MATCHER
elif navigation == "🎛️ Jobscan ATS Matcher":
    st.title("Jobscan-Style ATS Resume & Job Matcher")
    st.caption("Compare job descriptions against resumes to audit missing hard skills, soft skills, and formatting.")

    col_btn1, col_btn2 = st.columns([1, 4])
    if col_btn1.button("⚡ Load Benchmark Sample"):
        st.session_state.jd_input = "Position Title: Senior Full Stack Engineer\nDepartment: Engineering\n\nSummary:\nLooking for an experienced software engineer to build web apps.\n\nRequirements:\n- 5+ years experience\n- React, Node.js, TypeScript, AWS, PostgreSQL\n- Strong leadership and problem solving."
        st.session_state.resume_input = "Taylor Morgan\nFull Stack Developer\nEmail: taylor@example.com | (555) 019-2831\n\nExperience:\n- Built web applications with React, Node.js, and AWS EC2.\n- Improved page performance by 35%.\n\nSkills: React, Node.js, JavaScript, HTML, CSS, Git, AWS."

    col_jd, col_res = st.columns(2)

    with col_jd:
        st.subheader("Target Job Description")
        jd_val = st.text_area("Paste Job Description:", value=st.session_state.get("jd_input", ""), height=250)

    with col_res:
        st.subheader("Candidate Resume")
        file_up = st.file_uploader("Upload Resume (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"], key="jobscan_file")
        if file_up:
            parsed_text = parse_uploaded_file(file_up)
            if parsed_text:
                st.session_state.resume_input = parsed_text
                st.success("File parsed successfully!")

        res_val = st.text_area("Paste Resume Text:", value=st.session_state.get("resume_input", ""), height=170)

    if st.button("Calculate Jobscan ATS Match", type="primary", use_container_width=True):
        if not jd_val or not res_val:
            st.warning("Please provide both a Job Description and a Resume.")
        else:
            res_match = analyze_jobscan_match(jd_val, res_val)
            st.divider()

            st.subheader(f"Overall Jobscan Match: {res_match['overall_score']}%")
            st.progress(res_match['overall_score'] / 100)

            m1, m2, m3 = st.columns(3)
            m1.metric("Hard Skills Match", f"{len(res_match['matched_hard'])} / {len(res_match['matched_hard']) + len(res_match['missing_hard'])}")
            m2.metric("Soft Skills Match", f"{len(res_match['matched_soft'])} / {len(res_match['matched_soft']) + len(res_match['missing_soft'])}")
            m3.metric("ATS Audit Checks", f"{sum(res_match['checklist'].values()) - 1} / 4 Passed")

            c_skills, c_audit = st.columns(2)
            with c_skills:
                st.markdown("#### Matched Hard Skills")
                st.markdown(" ".join([f'<span class="badge-matched">✓ {s}</span>' for s in res_match['matched_hard']]), unsafe_allow_html=True)

                st.markdown("#### Missing Hard Skills")
                st.markdown(" ".join([f'<span class="badge-missing">✗ {s}</span>' for s in res_match['missing_hard']]), unsafe_allow_html=True)

            with c_audit:
                st.markdown("#### ATS Formatting & Audit Checklist")
                for key, val in res_match['checklist'].items():
                    if key != "word_count":
                        status = "✅ Pass" if val else "⚠️ Warning"
                        st.write(f"**{key.capitalize()}**: {status}")


# PAGE 3: JOB REQUISITIONS
elif navigation == "💼 Job Requisitions":
    st.title("Job Requisitions Manager")
    st.caption("Create positions and attach candidate profiles directly to requisitions in your logged-in workspace.")

    with st.expander("➕ Create New Job Requisition", expanded=False):
        j_title = st.text_input("Job Title", placeholder="e.g. Senior Frontend Engineer")
        j_dept = st.text_input("Department", placeholder="e.g. Engineering")
        j_skills = st.text_input("Required Skills (comma separated)", placeholder="React, TypeScript, Node.js")
        j_desc = st.text_area("Job Description", placeholder="Enter key responsibilities...")

        if st.button("Save Position", type="primary"):
            if j_title and j_dept:
                new_j_id = f"j_{len(jobs)+1}_{int(datetime.now().timestamp())}"
                jobs.append({
                    "id": new_j_id,
                    "title": j_title,
                    "dept": j_dept,
                    "skills": j_skills,
                    "desc": j_desc
                })
                activity_logs.append({"time": datetime.now().strftime("%H:%M:%S"), "msg": f"Created job requisition for {j_title}"})
                st.success(f"Job requisition for '{j_title}' created!")
                st.rerun()

    st.divider()
    if jobs:
        for idx, job in enumerate(jobs):
            linked_cands = [c for c in candidates if c.get('job_id') == job['id'] or c.get('role') == job['title']]
            
            with st.container():
                st.markdown(f"### 💼 {job['title']}")
                st.caption(f"🏢 **Department:** {job['dept']} | 🆔 **Requisition ID:** `{job['id']}` | 👥 **Applicants:** {len(linked_cands)}")
                st.write(f"**Required Skills:** {job['skills']}")
                st.write(job['desc'])

                # List attached candidates
                if linked_cands:
                    st.markdown("**Candidates Linked to this Requisition:**")
                    for lc in linked_cands:
                        st.markdown(f"- **{lc['name']}** — Score: `{lc['score']}%` | Recommendation: **{lc['recommendation']}**")
                else:
                    st.caption("No candidates attached to this job requisition yet.")

                col_add, col_del = st.columns([3, 1])
                with col_add:
                    with st.expander(f"➕ Add Candidate Profile directly to {job['title']}"):
                        c_name = st.text_input("Candidate Full Name", key=f"c_name_{job['id']}")
                        c_score = st.slider("Match Score (%)", 0, 100, 85, key=f"c_score_{job['id']}")
                        c_rec = st.selectbox("Recommendation", ["Strong Hire", "Hire", "Further Review", "Pass"], key=f"c_rec_{job['id']}")
                        c_strengths = st.text_input("Key Strengths (comma separated)", "Strong experience, Great communication", key=f"c_str_{job['id']}")
                        c_gaps = st.text_input("Identified Gaps (comma separated)", "System design depth", key=f"c_gaps_{job['id']}")
                        c_summary = st.text_area("Executive Summary", f"Qualified candidate evaluated for {job['title']}.", key=f"c_sum_{job['id']}")

                        if st.button("Save Candidate to Job", key=f"btn_save_c_{job['id']}"):
                            if c_name:
                                new_cand = {
                                    "id": f"c_{len(candidates)+1}_{int(datetime.now().timestamp())}",
                                    "job_id": job['id'],
                                    "name": c_name,
                                    "role": job['title'],
                                    "score": c_score,
                                    "strengths": [s.strip() for s in c_strengths.split(',') if s.strip()],
                                    "weaknesses": [g.strip() for g in c_gaps.split(',') if g.strip()],
                                    "recommendation": c_rec,
                                    "summary": c_summary
                                }
                                candidates.append(new_cand)
                                activity_logs.append({"time": datetime.now().strftime("%H:%M:%S"), "msg": f"Added candidate {c_name} to {job['title']}"})
                                st.success(f"Candidate {c_name} saved under '{job['title']}'!")
                                st.rerun()
                            else:
                                st.warning("Please enter candidate name.")

                with col_del:
                    if st.button("Delete Position", key=f"del_job_{job['id']}"):
                        user_data["jobs"] = [j for j in jobs if j['id'] != job['id']]
                        st.rerun()
                st.divider()
    else:
        st.info("No active job requisitions found. Click 'Create New Job Requisition' above to get started.")


# PAGE 4: CANDIDATE PIPELINE
elif navigation == "👥 Candidate Pipeline":
    st.title("Candidate Pipeline")
    st.caption("Manage, search, and add candidate profiles linked against your job requisitions.")

    # Expander to add new candidate profile
    with st.expander("➕ Add New Candidate Profile", expanded=False):
        if not jobs:
            st.warning("Please create at least one Job Requisition first under 'Job Requisitions'.")
        else:
            cand_job_title = st.selectbox("Select Target Job Requisition", [j['title'] for j in jobs], key="pipe_job_select")
            selected_req = next((j for j in jobs if j['title'] == cand_job_title), jobs[0])

            col_p1, col_p2 = st.columns(2)
            with col_p1:
                p_name = st.text_input("Candidate Full Name", placeholder="e.g. Jordan Lee", key="p_cand_name")
                p_score = st.slider("Assessment / Match Score (%)", 0, 100, 80, key="p_cand_score")
            with col_p2:
                p_rec = st.selectbox("Hiring Recommendation", ["Strong Hire", "Hire", "Further Review", "Pass"], key="p_cand_rec")
                p_strengths = st.text_input("Strengths (comma separated)", "React, TypeScript, AWS", key="p_cand_str")

            p_gaps = st.text_input("Areas for Improvement / Gaps (comma separated)", "Limited GraphQL experience", key="p_cand_gaps")
            p_summary = st.text_area("Candidate Overview / Summary", "Experienced candidate matching role criteria.", key="p_cand_sum")

            if st.button("Save Candidate to Pipeline", type="primary", key="btn_pipe_add_cand"):
                if p_name:
                    candidates.append({
                        "id": f"c_{len(candidates)+1}_{int(datetime.now().timestamp())}",
                        "job_id": selected_req['id'],
                        "name": p_name,
                        "role": cand_job_title,
                        "score": p_score,
                        "strengths": [s.strip() for s in p_strengths.split(',') if s.strip()],
                        "weaknesses": [g.strip() for g in p_gaps.split(',') if g.strip()],
                        "recommendation": p_rec,
                        "summary": p_summary
                    })
                    activity_logs.append({"time": datetime.now().strftime("%H:%M:%S"), "msg": f"Added {p_name} to {cand_job_title}"})
                    st.success(f"Candidate '{p_name}' successfully added to job '{cand_job_title}'!")
                    st.rerun()
                else:
                    st.warning("Please provide candidate full name.")

    st.divider()

    # Filter by Requisition
    col_filter1, col_filter2 = st.columns([2, 1])
    with col_filter1:
        search_term = st.text_input("🔍 Search Candidates by Name or Role", "")
    with col_filter2:
        job_filter_options = ["All Requisitions"] + [j['title'] for j in jobs]
        selected_job_filter = st.selectbox("Filter by Job Requisition", job_filter_options)

    filtered_cands = candidates
    if selected_job_filter != "All Requisitions":
        filtered_cands = [c for c in filtered_cands if c.get('role') == selected_job_filter or c.get('job_id') == next((j['id'] for j in jobs if j['title'] == selected_job_filter), '')]
    if search_term:
        filtered_cands = [c for c in filtered_cands if search_term.lower() in c['name'].lower() or search_term.lower() in c['role'].lower()]

    if filtered_cands:
        for cand in filtered_cands:
            with st.expander(f"👤 {cand['name']} — {cand['role']} (Match Score: {cand['score']}%)"):
                st.write(f"**Linked Job Requisition:** {cand['role']}")
                st.write(f"**Recommendation:** {cand['recommendation']}")
                st.write(f"**Summary:** {cand['summary']}")
                st.write(f"**Strengths:** {', '.join(cand['strengths']) if isinstance(cand['strengths'], list) else cand['strengths']}")
                st.write(f"**Gaps:** {', '.join(cand['weaknesses']) if isinstance(cand['weaknesses'], list) else cand['weaknesses']}")
                
                col_c_out, col_c_del = st.columns([3, 1])
                with col_c_out:
                    if st.button(f"Generate Outreach Draft for {cand['name']}", key=f"outreach_{cand['id']}"):
                        prompt = f"Write a professional, warm interview invitation email for {cand['name']} for the {cand['role']} position highlighting their strengths in {', '.join(cand['strengths']) if isinstance(cand['strengths'], list) else cand['strengths']}."
                        ai_draft = call_gemini_api(prompt)
                        if not ai_draft:
                            ai_draft = f"Subject: Interview Invitation - {cand['role']}\n\nHi {cand['name']},\n\nWe were impressed by your background and strengths. We would love to invite you to a short interview for the {cand['role']} position!\n\nBest regards,\n{user_data['name']} - {user_data['company']}"
                        st.text_area("Generated Email Draft:", value=ai_draft, height=200)
                with col_c_del:
                    if st.button(f"Delete Candidate", key=f"del_cand_{cand['id']}"):
                        user_data["candidates"] = [c for c in candidates if c['id'] != cand['id']]
                        st.rerun()
    else:
        st.info("No candidates match your filter or search criteria.")


# PAGE 5: AI RESUME ANALYZER
elif navigation == "🪄 AI Resume Analyzer":
    st.title("AI Resume Analyzer & Comprehensive Match Engine")
    st.caption("Perform deep AI candidate evaluations with detailed positive feedback, skill gap analysis, and hiring recommendations.")

    col_j, col_n = st.columns(2)
    with col_j:
        job_options = [j['title'] for j in jobs] if jobs else ["Senior Software Engineer", "AI Research Scientist", "Product Designer (UI/UX)"]
        target_job_title = st.selectbox("Target Job Position", job_options)
        
        # Selected job description context
        selected_job = next((j for j in jobs if j['title'] == target_job_title), None)
        job_desc_context = selected_job['desc'] if selected_job else "Target position responsibilities and requirements."
        if selected_job:
            st.caption(f"**Requisition:** {selected_job['dept']} | **Required Skills:** {selected_job['skills']}")

    with col_n:
        cand_name_input = st.text_input("Candidate Full Name", "Jordan Taylor")

    st.subheader("Candidate Resume Input")
    col_up, col_sample = st.columns([3, 1])
    with col_sample:
        if st.button("📄 Load Benchmark Resume"):
            st.session_state.analyzer_sample_text = """Jordan Taylor
Senior Full Stack Engineer
Email: jordan.taylor@example.com | Phone: (555) 321-9876

Executive Summary:
Results-driven Senior Engineer with 6+ years of experience building high-scale web applications using React, TypeScript, Node.js, and AWS. Proven track record of architecting cloud microservices and accelerating deployment velocity.

Technical Capabilities:
- Frontend: React, TypeScript, Next.js, Redux, Tailwind CSS
- Backend: Node.js, Express, PostgreSQL, REST APIs, GraphQL
- Cloud & DevOps: AWS (EC2, S3, Lambda), Docker, CI/CD, Git

Key Experience:
Senior Software Engineer | TechCorp (2021 - Present)
- Led frontend architecture overhaul using React and TypeScript, reducing load times by 42% and raising Lighthouse scores to 95.
- Designed Node.js microservices handling over 2M daily API requests with 99.98% uptime.
- Mentored 5 junior engineers and established automated CI/CD testing pipelines.

Education:
B.S. in Computer Science, UC Berkeley"""
            st.rerun()

    resume_file = st.file_uploader("Upload Resume Document (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"], key="screener_file")
    
    default_text = st.session_state.get("analyzer_sample_text", "")
    resume_text_input = st.text_area("Or Paste Resume Text Below:", value=default_text, height=200, placeholder="Paste candidate resume content here...")

    if st.button("⚡ Run Comprehensive AI Resume Evaluation", type="primary", use_container_width=True):
        extracted = parse_uploaded_file(resume_file) if resume_file else resume_text_input
        if not extracted.strip():
            st.warning("Please upload a resume file or paste resume content to proceed.")
        else:
            with st.spinner("🤖 NexusTalent AI analyzing candidate background, qualifications, and gaps..."):
                eval_res = perform_ai_resume_analysis(target_job_title, job_desc_context, cand_name_input, extracted)

                st.divider()
                st.subheader("📊 Candidate Evaluation Report")

                # Decision Banner
                score = eval_res.get("overall_score", 85)
                rec = eval_res.get("recommendation", "Hire")
                
                banner_color = "#ecfdf5" if rec == "Strong Hire" else ("#eff6ff" if rec == "Hire" else ("#fffbeb" if rec == "Further Review" else "#fef2f2"))
                text_color = "#047857" if rec == "Strong Hire" else ("#1d4ed8" if rec == "Hire" else ("#b45309" if rec == "Further Review" else "#dc2626"))
                
                st.markdown(f"""
                <div style="background-color: {banner_color}; border: 1px solid {text_color}; border-radius: 16px; padding: 20px; margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h2 style="margin:0; color: #0f172a; font-weight: 800;">{cand_name_input}</h2>
                            <p style="margin: 4px 0 0 0; color: #64748b; font-size: 14px;">Evaluated for <strong>{target_job_title}</strong></p>
                        </div>
                        <div style="text-align: right;">
                            <span style="background-color: {text_color}; color: white; padding: 8px 18px; border-radius: 20px; font-weight: 700; font-size: 16px;">
                                {rec} ({score}% Match)
                            </span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Metric Columns
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Overall Alignment", f"{score}%")
                m2.metric("Technical Fit", f"{eval_res.get('tech_score', 80)}%")
                m3.metric("Experience Depth", f"{eval_res.get('exp_score', 85)}%")
                m4.metric("Soft Skills & Fit", f"{eval_res.get('soft_score', 80)}%")

                st.progress(score / 100)

                # Detailed Positives vs Negatives Feedback
                col_pos, col_neg = st.columns(2)

                with col_pos:
                    st.markdown("### ✅ Positive Feedback & Pros")
                    positives = eval_res.get("positive_feedback", [])
                    for item in positives:
                        st.success(f"**✓** {item}")

                with col_neg:
                    st.markdown("### ⚠️ Identified Gaps & Cons")
                    negatives = eval_res.get("negative_feedback", [])
                    for item in negatives:
                        st.error(f"**✗** {item}")

                # Executive Summary
                st.subheader("💡 Executive Evaluation Summary")
                st.info(eval_res.get("summary", "Candidate exhibits high technical competency."))

                # Probing Questions
                st.subheader("❓ Recommended Probing Interview Questions")
                questions = eval_res.get("interview_questions", [])
                for idx, q in enumerate(questions, 1):
                    st.markdown(f"**{idx}.** {q}")

                # Save Candidate Option
                st.divider()
                if st.button("💾 Save Candidate to Pipeline", use_container_width=True):
                    target_job_obj = next((j for j in jobs if j['title'] == target_job_title), None)
                    new_candidate = {
                        "id": f"c_{len(candidates)+1}_{int(datetime.now().timestamp())}",
                        "job_id": target_job_obj['id'] if target_job_obj else "j1",
                        "name": cand_name_input,
                        "role": target_job_title,
                        "score": score,
                        "strengths": positives[:3],
                        "weaknesses": negatives[:2],
                        "recommendation": rec,
                        "summary": eval_res.get("summary", "")
                    }
                    candidates.append(new_candidate)
                    activity_logs.append({"time": datetime.now().strftime("%H:%M:%S"), "msg": f"Saved {cand_name_input} ({score}% match) to pipeline under {target_job_title}."})
                    st.success(f"Successfully added **{cand_name_input}** to candidate pipeline for **{target_job_title}**!")


# PAGE 6: AI SCREENING CHAT
elif navigation == "💬 AI Screening Chat":
    st.title("AI Voice & Screening Chat Assistant")

    cand_options = [c['name'] for c in candidates] if candidates else ["General Candidate"]
    selected_cand = st.selectbox("Select Candidate to Screen", cand_options)

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_msg = st.chat_input("Type your response or candidate answer...")
    if user_msg:
        st.session_state.chat_history.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.write(user_msg)

        with st.chat_message("assistant"):
            prompt = f"You are NexusTalent AI recruiter screening candidate {selected_cand}. Candidate said: '{user_msg}'. Ask a relevant follow up technical or experience question."
            reply = call_gemini_api(prompt)
            if not reply:
                reply = f"Thank you for sharing that! How do you handle code reviews and technical collaboration when working under tight deadlines for {selected_cand}?"
            st.write(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
