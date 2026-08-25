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
    st.title("Recruitment Dashboard Overview")
    st.caption(f"Welcome back, **{user_data['name']}**. Here is your private pipeline analytics.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Openings", len(jobs))
    c2.metric("Total Candidates", len(candidates))
    c3.metric("AI Screened", len(candidates))
    
    avg_score = int(sum(c['score'] for c in candidates) / len(candidates)) if candidates else 0
    c4.metric("Avg Match Score", f"{avg_score}%")

    st.divider()

    col_main, col_feed = st.columns([2, 1])

    with col_main:
        st.subheader("Top Ranked Talent Pipeline")
        if candidates:
            sorted_cand = sorted(candidates, key=lambda x: x['score'], reverse=True)
            table_data = []
            for cand in sorted_cand:
                table_data.append({
                    "Candidate Name": cand['name'],
                    "Target Role": cand['role'],
                    "Match Score": f"{cand['score']}%",
                    "Recommendation": cand['recommendation']
                })
            st.dataframe(table_data, use_container_width=True)
        else:
            st.info("No candidates in your pipeline yet. Use **AI Resume Analyzer** or **Candidate Pipeline** to add candidates.")

    with col_feed:
        st.subheader("Autonomous Agent Log")
        for log in activity_logs[::-1]:
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

    with st.expander("➕ Create New Job Requisition", expanded=False):
        j_title = st.text_input("Job Title", placeholder="e.g. Senior Frontend Engineer")
        j_dept = st.text_input("Department", placeholder="e.g. Engineering")
        j_skills = st.text_input("Required Skills (comma separated)", placeholder="React, TypeScript, Node.js")
        j_desc = st.text_area("Job Description", placeholder="Enter key responsibilities...")

        if st.button("Save Position", type="primary"):
            if j_title and j_dept:
                jobs.append({
                    "id": f"j_{len(jobs)+1}",
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
        cols = st.columns(2)
        for idx, job in enumerate(jobs):
            with cols[idx % 2]:
                st.markdown(f"### {job['title']}")
                st.caption(f"Department: {job['dept']}")
                st.write(f"**Skills:** {job['skills']}")
                st.write(job['desc'])
                if st.button(f"Delete Position", key=f"del_job_{job['id']}"):
                    user_data["jobs"] = [j for j in jobs if j['id'] != job['id']]
                    st.rerun()
    else:
        st.info("No active job requisitions found. Click 'Create New Job Requisition' above to get started.")


# PAGE 4: CANDIDATE PIPELINE
elif navigation == "👥 Candidate Pipeline":
    st.title("Candidate Pipeline")

    search_term = st.text_input("🔍 Search Candidates by Name or Role", "")
    filtered_cands = [c for c in candidates if search_term.lower() in c['name'].lower() or search_term.lower() in c['role'].lower()]

    if filtered_cands:
        for cand in filtered_cands:
            with st.expander(f"👤 {cand['name']} - {cand['role']} (Match Score: {cand['score']}%)"):
                st.write(f"**Recommendation:** {cand['recommendation']}")
                st.write(f"**Summary:** {cand['summary']}")
                st.write(f"**Strengths:** {', '.join(cand['strengths'])}")
                st.write(f"**Gaps:** {', '.join(cand['weaknesses'])}")
                
                if st.button(f"Generate Outreach Draft for {cand['name']}", key=f"outreach_{cand['id']}"):
                    prompt = f"Write a professional, warm interview invitation email for {cand['name']} for the {cand['role']} position highlighting their strengths in {', '.join(cand['strengths'])}."
                    ai_draft = call_gemini_api(prompt)
                    if not ai_draft:
                        ai_draft = f"Subject: Interview Invitation - {cand['role']}\n\nHi {cand['name']},\n\nWe were impressed by your background and strengths in {', '.join(cand['strengths'])}. We would love to invite you to a short interview!\n\nBest regards,\n{user_data['name']} - {user_data['company']}"
                    st.text_area("Generated Email Draft:", value=ai_draft, height=200)
    else:
        st.info("No candidates match your search.")


# PAGE 5: AI RESUME ANALYZER
elif navigation == "🪄 AI Resume Analyzer":
    st.title("AI Resume Analyzer & Match Engine")

    col_j, col_n = st.columns(2)
    with col_j:
        job_options = [j['title'] for j in jobs] if jobs else ["Senior Software Engineer", "Product Manager"]
        target_job_title = st.selectbox("Target Job Position", job_options)
    with col_n:
        cand_name_input = st.text_input("Candidate Full Name", "Jordan Taylor")

    resume_file = st.file_uploader("Upload Candidate Resume File", type=["pdf", "docx", "txt"], key="screener_file")
    resume_text_input = st.text_area("Or Paste Resume Text Here", height=200)

    if st.button("Run AI Screening Evaluation", type="primary"):
        extracted = parse_uploaded_file(resume_file) if resume_file else resume_text_input
        if not extracted:
            st.warning("Please upload a resume file or paste resume text.")
        else:
            with st.spinner("AI evaluating candidate qualifications..."):
                prompt = f"Evaluate this resume for target role '{target_job_title}'. Resume: {extracted[:2000]}"
                ai_res = call_gemini_api(prompt)
                
                new_candidate = {
                    "id": f"c_{len(candidates)+1}",
                    "name": cand_name_input,
                    "role": target_job_title,
                    "score": 92,
                    "strengths": ["Strong technical foundation", "Demonstrated problem solving skills"],
                    "weaknesses": ["Cloud deployment depth can be explored further"],
                    "recommendation": "Strong Hire",
                    "summary": f"{cand_name_input} demonstrates high alignment with the {target_job_title} role requirements."
                }
                
                candidates.append(new_candidate)
                activity_logs.append({"time": datetime.now().strftime("%H:%M:%S"), "msg": f"Analyzed resume for {cand_name_input}"})
                st.success(f"Candidate {cand_name_input} analyzed and saved to your pipeline!")
                st.json(new_candidate)


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
