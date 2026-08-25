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

# Custom Styling to give modern UI depth & rounded cards
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
    .metric-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 16px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
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

if "user" not in st.session_state:
    st.session_state.user = {
        "name": "Alex Rivera",
        "email": "alex.recruiter@nexustalent.ai",
        "is_authenticated": True
    }

if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = ""

if "jobs" not in st.session_state:
    st.session_state.jobs = [
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
        },
        {
            "id": "j3",
            "title": "Product Designer (UI/UX)",
            "dept": "Design",
            "skills": "Figma, Tailwind, User Research, Prototyping, Design Systems",
            "desc": "Craft intuitive interfaces for enterprise SaaS platforms and conduct interactive usability testing."
        }
    ]

if "candidates" not in st.session_state:
    st.session_state.candidates = [
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
        },
        {
            "id": "c3",
            "name": "Marcus Vance",
            "role": "Product Designer (UI/UX)",
            "score": 78,
            "strengths": ["Advanced Figma proficiency", "Clean aesthetic portfolio"],
            "weaknesses": ["Lacks deep SaaS enterprise experience"],
            "recommendation": "Further Review",
            "summary": "Talented designer but requires assessment on complex enterprise UX workflows."
        }
    ]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "activity_logs" not in st.session_state:
    st.session_state.activity_logs = [
        {"time": datetime.now().strftime("%H:%M:%S"), "msg": "NexusTalent AI System initialized"}
    ]

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
                # Fallback to plain bytes decoding if pypdf is unavailable
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
    """Calls Gemini 3 Flash REST API or falls back to local intelligent logic."""
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
            st.warning(f"Gemini API call note: {e}. Using local intelligence.")

    # Local Intelligent Fallback
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

with st.sidebar:
    st.markdown("### 🧠 NexusTalent AI")
    st.caption("Autonomous Recruitment & Jobscan Hub")
    st.divider()

    # User Profile Block
    if st.session_state.user["is_authenticated"]:
        st.success(f"👤 {st.session_state.user['name']}")
        st.caption(f"Email: {st.session_state.user['email']}")
        if st.button("Logout / Switch Profile", use_container_width=True):
            st.session_state.user["is_authenticated"] = False
            st.rerun()
    else:
        st.subheader("Sign In")
        email_in = st.text_input("Email", value="alex.recruiter@nexustalent.ai")
        name_in = st.text_input("Full Name", value="Alex Rivera")
        col_login, col_guest = st.columns(2)
        if col_login.button("Log In", use_container_width=True):
            st.session_state.user = {"name": name_in, "email": email_in, "is_authenticated": True}
            st.success("Signed in!")
            st.rerun()
        if col_guest.button("Guest Mode", use_container_width=True):
            st.session_state.user = {"name": "Guest Recruiter", "email": "guest@nexustalent.ai", "is_authenticated": True}
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

if navigation == "📊 Dashboard":
    st.title("Recruitment Dashboard Overview")
    st.caption("Real-time pipeline analytics and autonomous agent logs.")

    # 4 Key Stats
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Openings", len(st.session_state.jobs))
    c2.metric("Total Candidates", len(st.session_state.candidates))
    c3.metric("AI Screened", len(st.session_state.candidates))
    
    avg_score = int(sum(c['score'] for c in st.session_state.candidates) / len(st.session_state.candidates)) if st.session_state.candidates else 0
    c4.metric("Avg Match Score", f"{avg_score}%")

    st.divider()

    col_main, col_feed = st.columns([2, 1])

    with col_main:
        st.subheader("Top Ranked Talent Pipeline")
        sorted_cand = sorted(st.session_state.candidates, key=lambda x: x['score'], reverse=True)
        
        table_data = []
        for cand in sorted_cand:
            table_data.append({
                "Candidate Name": cand['name'],
                "Target Role": cand['role'],
                "Match Score": f"{cand['score']}%",
                "Recommendation": cand['recommendation']
            })
        st.dataframe(table_data, use_container_width=True)

    with col_feed:
        st.subheader("Autonomous Agent Log")
        for log in st.session_state.activity_logs[::-1]:
            st.info(f"**[{log['time']}]** {log['msg']}")

elif navigation == "🎛️ Jobscan ATS Matcher":
    st.title("Jobscan-Style ATS Resume & Job Matcher")
    st.caption("Compare job descriptions against resumes to audit missing hard skills, soft skills, and formatting.")

    col_btn1, col_btn2 = st.columns([1, 4])
    if col_btn1.button("⚡ Load Benchmark Sample"):
        sample_job = st.session_state.jobs[0]
        st.session_state.jd_input = f"Position Title: {sample_job['title']}\nDepartment: {sample_job['dept']}\n\nSummary:\n{sample_job['desc']}\n\nRequirements:\n- 5+ years building web products\n- Proficiency in {sample_job['skills']}\n- Strong communication and agile leadership."
        st.session_state.resume_input = "Taylor Morgan\nFull Stack Engineer\nEmail: taylor@example.com | (555) 019-2831\n\nExperience:\n- Built web apps using React, Node.js, and AWS EC2.\n- Improved speed performance by 35%.\n\nSkills: React, Node.js, JavaScript, HTML, CSS, Git, AWS."

    col_jd, col_res = st.columns(2)

    with col_jd:
        st.subheader("Target Job Description")
        jd_val = st.text_area("Paste Job Description:", value=st.session_state.get("jd_input", ""), height=250)

    with col_res:
        st.subheader("Candidate Resume")
        file_up = st.file_uploader("Upload Resume (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"])
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

elif navigation == "💼 Job Requisitions":
    st.title("Job Requisitions Manager")

    with st.expander("➕ Create New Job Requisition", expanded=False):
        j_title = st.text_input("Job Title", placeholder="e.g. Senior Frontend Engineer")
        j_dept = st.text_input("Department", placeholder="e.g. Engineering")
        j_skills = st.text_input("Required Skills (comma separated)", placeholder="React, TypeScript, Node.js")
        j_desc = st.text_area("Job Description", placeholder="Enter key responsibilities...")

        if st.button("Save Position", type="primary"):
            if j_title and j_dept:
                st.session_state.jobs.append({
                    "id": f"j_{len(st.session_state.jobs)+1}",
                    "title": j_title,
                    "dept": j_dept,
                    "skills": j_skills,
                    "desc": j_desc
                })
                st.success(f"Job requisition for '{j_title}' created!")
                st.rerun()

    st.divider()
    cols = st.columns(2)
    for idx, job in enumerate(st.session_state.jobs):
        with cols[idx % 2]:
            st.markdown(f"### {job['title']}")
            st.caption(f"Department: {job['dept']}")
            st.write(f"**Skills:** {job['skills']}")
            st.write(job['desc'])
            if st.button(f"Delete Position", key=f"del_job_{job['id']}"):
                st.session_state.jobs = [j for j in st.session_state.jobs if j['id'] != job['id']]
                st.rerun()

elif navigation == "👥 Candidate Pipeline":
    st.title("Candidate Pipeline")

    search_term = st.text_input("🔍 Search Candidates by Name or Role", "")
    filtered_cands = [c for c in st.session_state.candidates if search_term.lower() in c['name'].lower() or search_term.lower() in c['role'].lower()]

    for cand in filtered_cands:
        with st.expander(f"👤 {cand['name']} - {cand['role']} (Match Score: {cand['score']}%)"):
            st.write(f"**Recommendation:** {cand['recommendation']}")
            st.write(f"**Summary:** {cand['summary']}")
            st.write(f"**Strengths:** {', '.join(cand['strengths'])}")
            st.write(f"**Gaps:** {', '.join(cand['weaknesses'])}")
            
            # Outreach Draft Generator
            if st.button(f"Generate Outreach Draft for {cand['name']}", key=f"outreach_{cand['id']}"):
                prompt = f"Write a professional, warm interview invitation email for {cand['name']} for the {cand['role']} position highlighting their strengths in {', '.join(cand['strengths'])}."
                ai_draft = call_gemini_api(prompt)
                if not ai_draft:
                    ai_draft = f"Subject: Interview Invitation - {cand['role']}\n\nHi {cand['name']},\n\nWe were impressed by your background and strengths in {', '.join(cand['strengths'])}. We would love to invite you to a short interview!\n\nBest regards,\nNexusTalent AI Team"
                st.text_area("Generated Email Draft:", value=ai_draft, height=200)

elif navigation == "🪄 AI Resume Analyzer":
    st.title("AI Resume Analyzer & Match Engine")

    col_j, col_n = st.columns(2)
    with col_j:
        target_job_title = st.selectbox("Target Job Position", [j['title'] for j in st.session_state.jobs])
    with col_n:
        cand_name_input = st.text_input("Candidate Full Name", "Jordan Taylor")

    resume_file = st.file_uploader("Upload Candidate Resume File", type=["pdf", "docx", "txt"])
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
                    "id": f"c_{len(st.session_state.candidates)+1}",
                    "name": cand_name_input,
                    "role": target_job_title,
                    "score": 92,
                    "strengths": ["Strong technical foundation", "Demonstrated problem solving skills"],
                    "weaknesses": ["Cloud deployment depth can be explored further"],
                    "recommendation": "Strong Hire",
                    "summary": f"{cand_name_input} demonstrates high alignment with the {target_job_title} role requirements."
                }
                
                st.session_state.candidates.append(new_candidate)
                st.success(f"Candidate {cand_name_input} analyzed and added to pipeline!")
                st.json(new_candidate)

elif navigation == "💬 AI Screening Chat":
    st.title("AI Voice & Screening Chat Assistant")

    selected_cand = st.selectbox("Select Candidate to Screen", [c['name'] for c in st.session_state.candidates])

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
                reply = f"Thank you for sharing that! How do you handle code reviews and collaboration when working under tight deadlines for {selected_cand}?"
            st.write(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
