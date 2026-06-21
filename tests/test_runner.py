import pathlib
import runner

GIB = 1024 ** 3

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
