from concurrent.futures import ThreadPoolExecutor

from rolo.jobs import JobStatus, JobStore


def test_job_store_uses_atomic_writes_and_recovers_after_repeated_updates(tmp_path):
    store = JobStore(tmp_path)
    job = store.create("target.inspect", "local:C:/robot")

    def append(index: int):
        current, _, _ = store.load(job.job_id)
        return store.append_event(
            job.job_id,
            f"STEP_{index}",
            JobStatus.RUNNING,
            expected_revision=current.revision,
        )

    # A stale writer must fail rather than overwrite a newer atomic snapshot.
    first = append(1)
    try:
        store.append_event(job.job_id, "STALE", JobStatus.FAILED, expected_revision=0)
    except ValueError as exc:
        assert "revision conflict" in str(exc)
    else:
        raise AssertionError("stale writer unexpectedly replaced the job snapshot")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(append, index) for index in (2, 3)]
        results = [future.result() for future in futures if not future.exception()]
    loaded, events, _ = store.load(job.job_id)
    assert first.sequence == 1
    assert loaded.revision == len(events)
    assert loaded.revision >= 2
    assert len(results) >= 1
