import pathlib
import pytest
from harness import outer_agent

def test_build_outer_prompt_contains_inputs_and_key():
    prompt = outer_agent.build_outer_prompt("/work/papers", 31,
                                            {"ANTHROPIC_API_KEY": "sk-xyz"})
    assert "/work/papers" in prompt
    assert "31" in prompt
    assert "ANTHROPIC_API_KEY" in prompt and "sk-xyz" in prompt
    assert "venue-matcher" in prompt

def test_stage_extra_skills_copies(tmp_path):
    src = tmp_path / "skA"
    (src).mkdir()
    (src / "SKILL.md").write_text("---\nname: skA\n---\n")
    dest = tmp_path / "dest"
    staged = outer_agent.stage_extra_skills([src], dest)
    assert staged == ["skA"]
    assert (dest / "skA" / "SKILL.md").exists()

def test_build_outer_prompt_forbids_env_knobs():
    prompt = outer_agent.build_outer_prompt("/work/papers", 31, {"ANTHROPIC_API_KEY": "k"})
    assert "MAX_PARALLEL" in prompt
    assert "only" in prompt.lower()

def test_stage_extra_skills_fatal_on_venue_matcher_collision(tmp_path):
    src = tmp_path / "venue-matcher"
    src.mkdir()
    (src / "SKILL.md").write_text("---\nname: venue-matcher\n---\n")
    with pytest.raises(SystemExit):
        outer_agent.stage_extra_skills([src], tmp_path / "dest")

def test_stage_extra_skills_skips_path_without_skill_md(tmp_path):
    src = tmp_path / "notaskill"
    src.mkdir()  # deliberately no SKILL.md
    staged = outer_agent.stage_extra_skills([src], tmp_path / "dest")
    assert staged == []
