from applypilot.scoring.validator import validate_json_fields, validate_tailored_resume


def _profile():
    return {
        "skills_boundary": {
            "programming_languages": ["Python", "C++", "Swift"],
        },
        "resume_facts": {},
    }


def test_json_validator_allows_watchlisted_profile_skills():
    data = {
        "title": "Software Engineer",
        "summary": "Software engineering student.",
        "skills": {"Languages": ["Python", "C++", "Swift"]},
        "experience": [{"header": "Example", "bullets": ["Built software."]}],
        "projects": [{"header": "Example", "bullets": ["Built a project."]}],
        "education": "Example University",
    }

    result = validate_json_fields(data, _profile(), mode="lenient")

    assert result["passed"] is True
    assert result["errors"] == []


def test_text_validator_allows_watchlisted_profile_skills():
    text = """SUMMARY
Software engineering student.
TECHNICAL SKILLS
Python, C++, Swift
EXPERIENCE
Example
PROJECTS
Example
EDUCATION
Example University
"""

    result = validate_tailored_resume(text, _profile())

    assert not any("FABRICATED SKILL" in error for error in result["errors"])
