from agent_orc.handover import ADVISED, ASKED, DONE, WORKING, follow_course


def test_an_asked_request_runs_its_course() -> None:
    # Typed in, but the agent has not started yet.
    assert follow_course(ASKED, busy=False) == ASKED
    assert follow_course(ASKED, busy=True) == WORKING
    assert follow_course(WORKING, busy=True) == WORKING
    assert follow_course(WORKING, busy=False) == DONE


def test_done_or_advised_stays_whatever_the_agent_does() -> None:
    for progress in (DONE, ADVISED):
        assert follow_course(progress, busy=False) == progress
        assert follow_course(progress, busy=True) == progress
