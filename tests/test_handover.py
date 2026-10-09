from agent_orc.handover import ADVISED, ASKED, DONE, WORKING, follow_progress


def test_an_asked_handover_runs_its_course_and_ends_with_the_next_input() -> None:
    # Typed in, but the agent has not started yet.
    assert follow_progress(ASKED, busy=False) == ASKED
    assert follow_progress(ASKED, busy=True) == WORKING
    assert follow_progress(WORKING, busy=True) == WORKING
    assert follow_progress(WORKING, busy=False) == DONE
    # Done, it stays so while the agent rests (and its cache goes cold), until the user's input.
    assert follow_progress(DONE, busy=False) == DONE
    assert follow_progress(DONE, busy=True) is None


def test_an_advised_handover_ends_with_the_next_input() -> None:
    assert follow_progress(ADVISED, busy=False) == ADVISED
    assert follow_progress(ADVISED, busy=True) is None
