from app.api.slack_mentions import extract_all_mentions, extract_mention


def test_extract_mention_with_label():
    user_id, remainder = extract_mention("<@U0RAHUL|rahul> what did you complete?")
    assert user_id == "U0RAHUL"
    assert remainder == "what did you complete?"


def test_extract_mention_without_label():
    user_id, remainder = extract_mention("<@U0RAHUL> status please")
    assert user_id == "U0RAHUL"
    assert remainder == "status please"


def test_extract_mention_none_present():
    user_id, remainder = extract_mention("no mention here")
    assert user_id is None
    assert remainder == "no mention here"


def test_extract_all_mentions():
    ids, remainder = extract_all_mentions("<@U0BOB|bob> <@U0CARL|carl> also U0RAW")
    assert ids == ["U0BOB", "U0CARL"]
    assert remainder == "also U0RAW"
