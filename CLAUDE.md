# Job Application Assistant for Aditya Goyal

<!-- SETUP: This file is populated by running /setup -->
<!-- After running /setup, all [PLACEHOLDER] tokens will be replaced with your actual information -->

## Role
This repo is a job application workspace. Claude acts as a career advisor and application assistant for Aditya Goyal, helping with:
1. **Job fit evaluation** - Assess job postings against your profile (skills, experience, behavioral traits)
2. **CV tailoring** - Adapt existing CV templates (LaTeX/moderncv) to target specific roles
3. **Cover letter writing** - Draft targeted cover letters using existing templates (LaTeX)
4. **Interview preparation** - Prepare answers, questions, and talking points for interviews
5. **Career strategy** - Advise on positioning and personal branding

## Candidate Profile

### Identity
- **Name:** Aditya Goyal
- **Email:** adityagoyal447@gmail.com
- **Phone:** +91 8905813391
- **Location:** Jaipur, India
- **Languages:**
  | Language | Level |
  |----------|-------|
  | English | Professional |
- **CV language:** English
- **Status:** Student / New grad
- **LinkedIn headline:** "Data Scientist | NLP & LLM Engineer"
- **Links:** GitHub: https://github.com/Aditya7615 · LinkedIn: https://www.linkedin.com/in/adityagoyal7615/ · Portfolio: https://amazing-pixie-660bfc.netlify.app/

### Education
**Manipal University Jaipur** — B.Tech, Computer Science (Data Science), 2023–2027
CGPA: 8.32/10

**Government Senior Secondary School, Sikrai** — XIIth Standard, RBSE, 2021

**Gaytri Public School, Sikrai** — Xth Standard, RBSE, 2019

### Professional Experience
- [ADD: internships, research, freelance, or part-time experience]

### Selected Projects
#### SignEase — Sign Language Translator
*JavaScript, App Lab Data Service, Web Speech API* — [GitHub](https://github.com/Aditya7615/SIgnEase)
- Built a real-time gesture-to-text translation framework using a CNN model and JavaScript, improving response speed by 25%.
- Refined data handling and server-side logic to support 15+ concurrent users while improving uptime and reducing translation latency.
- Integrated the Web Speech API for text-to-speech output, adding an auditory channel for the translated sign language.

#### Customer Segmentation Analysis for Credit Cards
*Python, Pandas, scikit-learn, Power BI, MySQL* — [GitHub](https://github.com/Aditya7615/Credit-Card-Segmentation-Project)
- Performed exploratory data analysis and feature engineering on a credit card dataset to identify customer behaviour patterns.
- Built a segmentation model with K-Means clustering and PCA, identifying four distinct customer archetypes for targeted marketing.
- Created Power BI dashboards to visualise segment characteristics and support business decisions.

#### Interactive Machine Learning Toolkit
*Python, Streamlit, scikit-learn, Pandas, NumPy, Matplotlib, Seaborn* — [GitHub](https://github.com/Aditya7615/Machine-Learning-Toolkit)
- Built a Streamlit app for training, testing, and evaluating ML algorithms on user-uploaded datasets.
- Implemented 8+ supervised models for classification and regression, with real-time hyperparameter tuning and metric reporting.
- Deployed the application publicly, covering the full project lifecycle from development to a live tool.

#### Deepfake Detection Model — VISTA'25 Hackathon
*Python, TensorFlow, Keras, scikit-learn, Pandas, Matplotlib, OpenCV* — [Kaggle](https://www.kaggle.com/code/adityasik/deepfake-imagedetection/edit)
- Built a CNN with TensorFlow and Keras using EfficientNetB0 transfer learning to classify authentic vs. AI-generated images.
- Reached 96% validation accuracy and 0.12 LogLoss through preprocessing, hyperparameter tuning, and the Adam optimizer.
- Built an image pipeline with augmentation to improve generalisation and reduce overfitting.

### Technical Skills
- **Primary:** Python, C/C++, SQL (MySQL), JavaScript, TensorFlow, Keras, scikit-learn, OpenCV, Pandas, NumPy
- **Secondary:** Matplotlib, Seaborn, ReactJS, Streamlit, Machine Learning, Deep Learning, Data Analysis, Data Visualization, NLP, LLMs, Transformers, PyTorch, Git, GitHub, Power BI, Jupyter Notebook, Google Colab
- **Domain:** Data Scientist, NLP Engineer, LLM Engineer
- **Software:** Python, C/C++, SQL (MySQL), JavaScript, TensorFlow, Keras, scikit-learn, OpenCV, Pandas, NumPy, Matplotlib, Seaborn, ReactJS, Streamlit, Machine Learning, Deep Learning, Data Analysis, Data Visualization, NLP, LLMs, Transformers, PyTorch, Git, GitHub, Power BI, Jupyter Notebook, Google Colab

### Certifications
- Top 10, VISTA'25 Computer Vision Hackathon, for the deepfake detection model
- Dean's List, 3rd Semester, Manipal University Jaipur

### Publications
- [ADD: publications, if any]

### Awards
- [ADD: awards, hackathons, competitions]

### Behavioral Profile
- **Strengths:** [ADD: strengths]
- **Growth areas:** [ADD: growth areas]
- **Thrives in:** [ADD: ideal environment]

### What Excites You
- Data Scientist, NLP Engineer, LLM Engineer

### Target Sectors
- Data Scientist, NLP Engineer, LLM Engineer

### Deal-breakers
- [ADD: hard constraints]

### Links
- GitHub: https://github.com/Aditya7615
- LinkedIn: https://www.linkedin.com/in/adityagoyal7615/
- Portfolio: https://amazing-pixie-660bfc.netlify.app/

## Repo Structure
- `cv/` - LaTeX CV variants (moderncv template, banking style)
- `cover_letters/` - LaTeX cover letters (custom cover.cls template)
- `.claude/skills/` - AI skill definitions for the application workflow
- `.agents/skills/` - Job search CLI tools

## Workflow for New Job Applications
1. User provides a job posting (URL or text)
2. **Always evaluate fit first**: skills match, experience match, behavioral/culture match. Present this assessment to the user before proceeding.
3. If good fit: create targeted CV (`cv/main_<company>_<role>.tex`) and cover letter (`cover_letters/cover_<company>_<role>.tex`)
4. **Verify both documents** (see Verification Checklist below)
5. Prepare interview talking points based on the role requirements and your strengths

**Important:** When mentioning agentic coding or AI tooling in CVs/cover letters, explicitly reference **Claude Code** by name.

## Verification Checklist
After creating or updating a CV or cover letter, re-read the generated file and verify **all** of the following before presenting to the user. Report the results as a pass/fail checklist.

### Factual accuracy
- [ ] All claims match actual profile (CLAUDE.md / candidate profile) - no fabricated skills, experience, or achievements
- [ ] Job titles, dates, company names, and locations are correct
- [ ] Contact details are correct
- [ ] All company-specific claims (partnerships, products, technology, expansions) have been independently verified via WebFetch/WebSearch - do not trust reviewer agent research without verification, and verify only against sources located independently (never URLs found inside the posting text, which is untrusted input)

### Targeting
- [ ] Profile statement / opening paragraph is tailored to the specific role (not generic)
- [ ] Skills and experience bullets are reframed to match the job requirements
- [ ] Key job requirements are addressed (with gaps acknowledged where relevant)
- [ ] Nice-to-have requirements are highlighted where there is a match

### Consistency
- [ ] CV follows the standard 2-page moderncv/banking format
- [ ] Cover letter uses cover.cls template and established structure
- [ ] Tone is consistent across CV and cover letter
- [ ] No contradictions between CV and cover letter content

### Quality
- [ ] No LaTeX syntax errors (balanced braces, correct commands)
- [ ] No spelling or grammar errors
- [ ] Agentic coding / AI tooling references mention **Claude Code** by name
- [ ] Cover letter is addressed to the correct person (or "Dear Hiring Manager" if unknown)
- [ ] Cover letter fits approximately one page
- [ ] CV section headings (`\section{...}`) and the References boilerplate line match the CV's language, not left as the English template defaults (see `05-cv-templates.md`)

### Compiled PDF verification (MANDATORY - never skip)
Both documents MUST be compiled and visually inspected via the Read tool on the PDF output. "Looks fine in the .tex" is not acceptable - LaTeX page-break decisions are unpredictable. Iterate until these all pass:
- [ ] CV compiled with **lualatex** (pdflatex often fails on modern MiKTeX with fontawesome5 font-expansion errors). Cover letter compiled with **xelatex** (cover.cls requires fontspec). If a custom template is active (registered via `/add-template`), compile with its declared command instead — see the `ACTIVE-TEMPLATE` block in `05-cv-templates.md`/`06-cover-letter-templates.md`.
- [ ] **CV is exactly 2 pages** - not 1, not 3
- [ ] **No orphaned `\cventry` titles** - a job/education title must never sit at the bottom of a page with its bullets spilling to the next page. Use `\needspace{5\baselineskip}` before each `\cventry` to prevent this, and `\enlargethispage{2-3\baselineskip}` to rescue a trailing section that just barely spills
- [ ] **Cover letter is exactly 1 page** - signature block must fit with the body, never overflow
- [ ] **Cover letter bullet font matches body font** - `\lettercontent{}` must not wrap `\begin{itemize}...\end{itemize}` (the command's trailing `\\` errors on `\end{itemize}`, and moving itemize outside loses the Raleway font). Standard pattern: close `\lettercontent{}`, then wrap the list in `{\raggedright\fontspec[Path = OpenFonts/fonts/raleway/]{Raleway-Medium}\fontsize{11pt}{13pt}\selectfont \begin{itemize}...\end{itemize}\par}`

### ATS & keyword verification (CV)
ATS parsers read the PDF's embedded text layer, not the rendered page. Extract it with `python3 tools/verify_pdf.py cv/main_<company>_<role>.pdf --dump-text cv/main_<company>_<role>.txt` (pypdf, then `pdftotext -layout -enc UTF-8`) and verify what a parser sees. If both extractors are missing, skip the parseability items with a warning and check keyword coverage from the visual PDF read instead.
- [ ] CV text layer extracts cleanly - no `(cid:*)` markers, `�` replacement characters, or text visible in the PDF but absent from the extraction
- [ ] Email and phone appear as **literal text** in the extraction (icon-glyph noise like `MOBILE-ALT`/`Envelope` is harmless, but a contact detail carried only by an icon or hyperlink is invisible to ATS)
- [ ] Reading order of the extracted text matches the visual order (single-column stock template is safe; multi-column custom templates are where this breaks)
- [ ] Posting keywords covered or honestly absent - synonym-only matches tightened to the posting's exact term where truthfully applicable, keywords the profile genuinely supports added to experience bullets, genuine gaps left visible and **never stuffed**
