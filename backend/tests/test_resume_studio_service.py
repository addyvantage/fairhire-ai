from pathlib import Path

from app.services.resume_studio import ResumeStudioService, default_structured_resume


def test_parse_resume_text_extracts_sections() -> None:
    service = ResumeStudioService()
    text = """
    Jane Doe
    Financial Analyst
    jane@example.com | (555) 111-2222 | New York, NY

    Summary
    Finance analyst focused on KPI reporting and stakeholder updates.

    Skills
    Analytics: SQL, Excel, Tableau
    Finance: Forecasting, Variance Analysis

    Experience
    Financial Analyst at Acme Corp | 2021 - Present
    - Built KPI dashboards for leadership reporting.
    - Automated monthly variance analysis.

    Education
    State University, B.S. Finance
    """
    parsed = service.parse_resume_text(text, title_hint="Jane Doe Resume")
    assert parsed["header"]["name"] == "Jane Doe"
    assert parsed["header"]["email"] == "jane@example.com"
    assert parsed["skills"]["categories"]
    assert parsed["experience"]["items"]
    assert parsed["education"]["items"]
    assert parsed["evidence_map"]


def test_tailor_strict_mode_marks_ungrounded_rewrites() -> None:
    service = ResumeStudioService()
    base = default_structured_resume("Analyst Resume")
    base["summary"] = "Business analyst with reporting and stakeholder collaboration."
    base["experience"]["items"] = [
        {
            "company": "Acme",
            "role": "Analyst",
            "location": "",
            "start": "2022",
            "end": "Present",
            "bullets": [
                "Built KPI dashboards for leadership reviews.",
                "Prepared monthly business reports.",
            ],
            "tech": [],
        }
    ]
    base["evidence_map"] = service._build_evidence_map(base)
    jd_text = """
    Apprentice Financial Analyst
    Responsibilities:
    - Support reporting and monthly variance analysis.
    - Partner with stakeholders across finance and operations.
    Required:
    - SQL and Tableau required.
    - Strong communication skills.
    """
    tailored = service.tailor_resume(base, jd_text=jd_text, strict_mode=True)
    suggestions = tailored["score_snapshot_json"].get("rewrite_suggestions", [])
    assert suggestions
    assert any(
        suggestion.get("example_bullet", "").startswith("[Add if true]")
        for suggestion in suggestions
    )


def test_export_generates_pdf_and_docx(tmp_path: Path) -> None:
    service = ResumeStudioService()
    structured = default_structured_resume("Ava Smith")
    structured["summary"] = "Operations analyst with process improvement focus."
    structured["experience"]["items"] = [
        {
            "company": "Northwind",
            "role": "Operations Analyst",
            "location": "",
            "start": "2021",
            "end": "Present",
            "bullets": ["Reduced reporting cycle time by 30%."],
            "tech": ["Excel"],
        }
    ]
    pdf_path = tmp_path / "resume.pdf"
    docx_path = tmp_path / "resume.docx"

    service.export_pdf(structured, str(pdf_path))
    service.export_docx(structured, str(docx_path))

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 100
    assert docx_path.exists()
    assert docx_path.stat().st_size > 100


def test_structured_diff_detects_added_bullets_and_skills() -> None:
    service = ResumeStudioService()
    base = default_structured_resume("Base Resume")
    base["skills"]["categories"] = [{"name": "Core", "items": ["SQL", "Excel"]}]
    base["experience"]["items"] = [
        {
            "company": "A",
            "role": "Analyst",
            "location": "",
            "start": "2022",
            "end": "Present",
            "bullets": ["Built monthly KPI dashboard."],
            "tech": [],
        }
    ]

    current = default_structured_resume("Tailored Resume")
    current["skills"]["categories"] = [{"name": "Core", "items": ["SQL", "Excel", "Tableau"]}]
    current["experience"]["items"] = [
        {
            "company": "A",
            "role": "Analyst",
            "location": "",
            "start": "2022",
            "end": "Present",
            "bullets": [
                "Built monthly KPI dashboard.",
                "Presented insights to cross-functional stakeholders.",
            ],
            "tech": [],
        }
    ]
    diff = service.compute_structured_diff(base, current)
    assert "tableau" in diff["skills_added"]
    assert diff["bullet_delta"] == 1
    assert "presented insights to cross-functional stakeholders." in diff["added_bullets"]


def test_render_resume_html_is_stable_for_same_input() -> None:
    service = ResumeStudioService()
    structured = default_structured_resume("Ava Smith")
    structured["summary"] = "Operations analyst focused on reporting clarity."
    structured["skills"]["categories"] = [{"name": "Core", "items": ["Excel", "SQL"]}]
    first = service.render_resume_html(structured, template_name="modern_clean")
    second = service.render_resume_html(structured, template_name="modern_clean")
    assert first == second
    assert "Ava Smith" in first
