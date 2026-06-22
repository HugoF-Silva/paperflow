import pathlib
import pytest
import runner

GIB = 1024 ** 3
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

def test_resolve_max_parallel():
    assert runner.resolve_max_parallel(None) == 1
    assert runner.resolve_max_parallel("") == 1
    assert runner.resolve_max_parallel("3") == 3
    assert runner.resolve_max_parallel("auto") == "auto"

def test_compute_pool_size_explicit_caps_by_papers():
    # 4 requested, 2 papers -> 2
    assert runner.compute_pool_size(2, 4, 8, 10.0, 16*GIB, 800*1024*1024) == 2

def test_compute_pool_size_clamped_by_memory():
    # auto, lots of CPU free, but only ~1.6 GiB free, 800 MiB/worker -> ~1
    n = runner.compute_pool_size(10, "auto", 8, 0.0, 1.6*GIB, 800*1024*1024)
    assert n == 1

def test_compute_pool_size_never_below_one():
    assert runner.compute_pool_size(5, "auto", 1, 100.0, 0, 800*1024*1024) == 1

def test_compute_pool_size_explicit_clamped_by_resources():
    # explicit N=50 but ~1 free CPU and ~1.6 GiB free -> clamped far below 50
    n = runner.compute_pool_size(100, 50, 1, 99.0, 1.6*GIB, 800*1024*1024)
    assert n < 50
    assert n == 1

def test_progress_log_and_sentinel(tmp_path):
    p = tmp_path / "_progress.log"
    runner.append_progress(p, 1, 3)
    runner.append_progress(p, 2, 3)
    runner.write_sentinel(p, 3)
    body = p.read_text()
    assert "1/3" in body and "2/3" in body and "BATCH COMPLETE" in body

def test_run_batch_sequential_with_fake(tmp_path):
    papers = [tmp_path / "a.docx", tmp_path / "b.docx"]
    for f in papers:
        f.write_text("x")
    seen = []
    def fake_process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns):
        seen.append(paper.stem)
        (out_dir / paper.stem).mkdir(parents=True, exist_ok=True)
        return True
    summary = runner.run_batch(papers, tmp_path / "results", 31, 8, 60, 1,
                               process_one=fake_process_one)
    assert summary["total"] == 2 and summary["succeeded"] == 2
    assert sorted(seen) == ["a", "b"]
    assert "BATCH COMPLETE" in (tmp_path / "results" / "_progress.log").read_text()

def test_run_batch_starts_with_fresh_progress_log(tmp_path):
    papers = [tmp_path / "a.docx"]
    papers[0].write_text("x")
    results = tmp_path / "results"
    results.mkdir()
    (results / "_progress.log").write_text("OLD RUN\n", encoding="utf-8")

    def fake_process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns):
        return True

    runner.run_batch(papers, results, 31, 8, 60, 1, process_one=fake_process_one)

    body = (results / "_progress.log").read_text(encoding="utf-8")
    assert "OLD RUN" not in body
    assert "1/1 papers done" in body

def test_run_batch_removes_legacy_failures_log(tmp_path):
    papers = [tmp_path / "a.docx"]
    papers[0].write_text("x")
    results = tmp_path / "results"
    results.mkdir()
    failures = results / "_failures.log"
    failures.write_text("old failure\n", encoding="utf-8")

    def fake_process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns):
        return True

    runner.run_batch(papers, results, 31, 8, 60, 1, process_one=fake_process_one)

    assert not failures.exists()

def test_run_batch_removes_stale_paper_results_before_current_failure(tmp_path):
    papers = [tmp_path / "a.docx"]
    papers[0].write_text("x")
    results = tmp_path / "results"
    stale = results / "a" / "ranking.json"
    stale.parent.mkdir(parents=True)
    stale.write_text('{"old": true}', encoding="utf-8")

    def fake_process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns):
        return False, "no promise"

    summary = runner.run_batch(papers, results, 31, 8, 60, 1, process_one=fake_process_one)

    progress = (results / "_progress.log").read_text(encoding="utf-8")
    assert summary == {"total": 1, "succeeded": 0, "failed": 1}
    assert not stale.exists()
    assert "ERROR a.docx: no promise" in progress
    assert not (results / "_failures.log").exists()

def test_run_batch_logs_current_exception_to_progress_and_continues(tmp_path):
    papers = [tmp_path / "a.docx", tmp_path / "b.docx"]
    for paper in papers:
        paper.write_text("x")
    results = tmp_path / "results"
    stale = results / "a" / "ranking.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("old ranking", encoding="utf-8")

    def fake_process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns):
        if paper.name == "a.docx":
            raise RuntimeError("boom")
        return True

    summary = runner.run_batch(papers, results, 31, 8, 60, 1, process_one=fake_process_one)

    progress = (results / "_progress.log").read_text(encoding="utf-8")
    assert summary == {"total": 2, "succeeded": 1, "failed": 1}
    assert not stale.exists()
    assert "ERROR a.docx: RuntimeError: boom" in progress
    assert "BATCH COMPLETE: 2/2" in progress

def test_run_batch_resets_only_the_paper_being_started(tmp_path):
    papers = [tmp_path / "a.docx", tmp_path / "b.docx"]
    for paper in papers:
        paper.write_text("x")
    results = tmp_path / "results"
    stale_a = results / "a" / "ranking.json"
    stale_b = results / "b" / "ranking.json"
    stale_a.parent.mkdir(parents=True)
    stale_b.parent.mkdir(parents=True)
    stale_a.write_text("old a", encoding="utf-8")
    stale_b.write_text("old b", encoding="utf-8")

    def fake_process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        runner.run_batch(papers, results, 31, 8, 60, 1, process_one=fake_process_one)

    assert not stale_a.exists()
    assert stale_b.exists()

def test_run_batch_logs_progress_to_stdout(tmp_path, capsys):
    papers = [tmp_path / "a.docx"]
    papers[0].write_text("x")

    def fake_process_one(paper, out_dir, soon_days, max_ralph, inner_max_turns):
        return True

    runner.run_batch(papers, tmp_path / "results", 31, 8, 60, 1,
                     process_one=fake_process_one)

    out = capsys.readouterr().out
    assert "[venue-matcher]" in out
    assert "batch_start papers=1" in out
    assert "pool_size workers=1" in out
    assert "batch_progress done=1 total=1 succeeded=1" in out
    assert "batch_complete succeeded=1 total=1 failed=0" in out

def test_claude_and_openai_runners_stay_aligned():
    claude_runner = REPO_ROOT / "plugins" / "academia-perks-claude" / "skills" / "venue-matcher" / "scripts" / "venue_matcher" / "runner.py"
    openai_runner = REPO_ROOT / "plugins" / "academia-perks-openai" / "skills" / "venue-matcher" / "scripts" / "venue_matcher" / "runner.py"

    assert claude_runner.read_text(encoding="utf-8") == openai_runner.read_text(encoding="utf-8")
